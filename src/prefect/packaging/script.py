import warnings
from typing import TYPE_CHECKING, Optional, Union
from uuid import UUID

import fsspec

from prefect.blocks.core import Block
from prefect.blocks.storage import LocalStorageBlock, StorageBlock, TempStorageBlock
from prefect.client import OrionClient, inject_client
from prefect.exceptions import DeploymentValidationError, ObjectAlreadyExists
from prefect.flow_runners import SubprocessFlowRunner
from prefect.orion.schemas.actions import DeploymentCreate
from prefect.orion.schemas.data import DataDocument
from prefect.packaging.base import Packager
from prefect.utilities.asyncio import sync_compatible

if TYPE_CHECKING:
    from prefect.deployments import DeploymentSpec


class ScriptPackager(Packager):
    """
    Pushes the source code for your flow to a remote path.

    This script will be executed again at runtime to retrieve your flow object.

    If a storage block is not provided, the default storage will be retrieved from
    the API. If no default storage is configured, you must provide a storage block to
    use non-local flow runners.

    Args:
        storage: A [prefect.blocks.storage](/api-ref/prefect/blocks/storage/) instance
            providing the [storage](/concepts/storage/) to be used for the flow
            definition and results.
    """

    storage: Optional[Union[StorageBlock, UUID]] = None

    @sync_compatible
    @inject_client
    async def check_compat(self, deployment: "DeploymentSpec", client: OrionClient):
        # Determine the storage block

        # TODO: Some of these checks may be retained in the future, but will use block
        # capabilities instead of types to check for compatibility with flow runners

        if self.storage is None:
            default_block_document = await client.get_default_storage_block_document()
            if default_block_document:
                self.storage = Block._from_block_document(default_block_document)
        no_storage_message = "You have not configured default storage on the server or set a storage to use for this deployment"

        if isinstance(self.storage, UUID):
            storage_block_document = await client.read_block_document(self.storage)
            self.storage = Block._from_block_document(storage_block_document)

        if isinstance(deployment.flow_runner, SubprocessFlowRunner):
            local_machine_message = (
                "this deployment will only be usable from the current machine."
            )
            if not self.storage:
                warnings.warn(f"{no_storage_message}, {local_machine_message}")
                self.storage = LocalStorageBlock()
            elif isinstance(self.storage, (LocalStorageBlock, TempStorageBlock)):
                warnings.warn(
                    f"You have configured local storage, {local_machine_message}."
                )
        else:
            # All other flow runners require remote storage, ensure we've been given one
            flow_runner_message = f"this deployment is using a {deployment.flow_runner.typename.capitalize()} flow runner which requires remote storage"
            if not self.storage:
                raise DeploymentValidationError(
                    f"{no_storage_message} but {flow_runner_message}.",
                    deployment,
                )
            elif isinstance(self.storage, (LocalStorageBlock, TempStorageBlock)):
                raise DeploymentValidationError(
                    f"You have configured local storage but {flow_runner_message}.",
                    deployment,
                )

    @inject_client
    async def package(
        self, deployment: "DeploymentSpec", client: OrionClient
    ) -> DeploymentCreate:
        """
        Build the specification.

        Returns a schema that can be used to register the deployment with the API.
        """
        flow_id = await client.create_flow(deployment.flow)

        # Read the flow file
        with fsspec.open(deployment.flow_location, "rb") as flow_file:
            flow_bytes = flow_file.read()

        # Ensure the storage is a registered block for later retrieval

        if not self.storage._block_document_id:
            block_schema = await client.read_block_schema_by_checksum(
                self.storage._calculate_schema_checksum()
            )

            i = 0
            while not self.storage._block_document_id:
                try:
                    block_document = await client.create_block_document(
                        block_document=self.storage._to_block_document(
                            name=f"{deployment.flow_name}-{deployment.name}-{deployment.flow.version}-{i}",
                            block_schema_id=block_schema.id,
                            block_type_id=block_schema.block_type_id,
                        )
                    )
                    self.storage._block_document_id = block_document.id
                except ObjectAlreadyExists:
                    i += 1

        # Write the flow to storage
        storage_token = await self.storage.write(flow_bytes)
        flow_data = DataDocument.encode(
            encoding="blockstorage",
            data={
                "data": storage_token,
                "block_document_id": self.storage._block_document_id,
            },
        )

        return DeploymentCreate(
            flow_id=flow_id,
            name=deployment.name,
            schedule=deployment.schedule,
            flow_data=flow_data,
            parameters=deployment.parameters,
            tags=deployment.tags,
            flow_runner=deployment.flow_runner.to_settings(),
        )

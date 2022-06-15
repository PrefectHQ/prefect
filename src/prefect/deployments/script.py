import warnings
from typing import Literal, Optional, Union
from uuid import UUID

import fsspec

from prefect.blocks.core import Block
from prefect.blocks.storage import LocalStorageBlock, StorageBlock, TempStorageBlock
from prefect.client import OrionClient, inject_client
from prefect.deployments.base import DeploymentSpecification
from prefect.exceptions import DeploymentValidationError, ObjectAlreadyExists
from prefect.flow_runners import SubprocessFlowRunner
from prefect.orion.schemas.actions import DeploymentCreate
from prefect.orion.schemas.data import DataDocument
from prefect.utilities.asyncio import sync_compatible


class ScriptDeploymentSpecification(DeploymentSpecification):
    """
    Specification for a deployment of a flow.

    This specification type pushes the source code for your flow to a remote path.

    This script will be executed again at runtime to retrieve your flow object.

    The flow object or flow location must be provided.

    If a flow storage block is not provided, the default storage will be retrieved from
    the API. If no default storage is configured, you must provide a storage block to
    use non-local runners.

    Args:
        name: The name of the deployment
        flow: The flow object to associate with the deployment
        flow_location: The path to a script containing the flow to associate with the
            deployment. Inferred from `flow` if provided.
        flow_name: The name of the flow to associated with the deployment. Only required
            if loading the flow from a `flow_location` with multiple flows. Inferred
            from `flow` if provided.
        flow_runner: The [flow runner](/api-ref/prefect/flow-runners/) to be used for
            flow runs.
        flow_storage: A [prefect.blocks.storage](/api-ref/prefect/blocks/storage/) instance
            providing the [storage](/concepts/storage/) to be used for the flow
            definition and results.
        parameters: An optional dictionary of default parameters to set on flow runs
            from this deployment. If defined in Python, the values should be Pydantic
            compatible objects.
        schedule: An optional schedule instance to use with the deployment.
        tags: An optional set of tags to assign to the deployment.
    """

    type: Literal["script"] = "script"

    flow_storage: Optional[Union[StorageBlock, UUID]] = None

    # Validation and inference ---------------------------------------------------------

    @sync_compatible
    @inject_client
    async def validate(self, client: OrionClient):
        await super().validate(client=client)

        # Determine the storage block

        # TODO: Some of these checks may be retained in the future, but will use block
        # capabilities instead of types to check for compatibility with flow runners

        if self.flow_storage is None:
            default_block_document = await client.get_default_storage_block_document()
            if default_block_document:
                self.flow_storage = Block._from_block_document(default_block_document)
        no_storage_message = "You have not configured default storage on the server or set a storage to use for this deployment"

        if isinstance(self.flow_storage, UUID):
            flow_storage_block_document = await client.read_block_document(
                self.flow_storage
            )
            self.flow_storage = Block._from_block_document(flow_storage_block_document)

        if isinstance(self.flow_runner, SubprocessFlowRunner):
            local_machine_message = (
                "this deployment will only be usable from the current machine."
            )
            if not self.flow_storage:
                warnings.warn(f"{no_storage_message}, {local_machine_message}")
                self.flow_storage = LocalStorageBlock()
            elif isinstance(self.flow_storage, (LocalStorageBlock, TempStorageBlock)):
                warnings.warn(
                    f"You have configured local storage, {local_machine_message}."
                )
        else:
            # All other flow runners require remote storage, ensure we've been given one
            flow_runner_message = f"this deployment is using a {self.flow_runner.typename.capitalize()} flow runner which requires remote storage"
            if not self.flow_storage:
                raise DeploymentValidationError(
                    f"{no_storage_message} but {flow_runner_message}.",
                    self,
                )
            elif isinstance(self.flow_storage, (LocalStorageBlock, TempStorageBlock)):
                raise DeploymentValidationError(
                    f"You have configured local storage but {flow_runner_message}.",
                    self,
                )

    # Methods --------------------------------------------------------------------------

    @inject_client
    async def build(self, client: OrionClient) -> DeploymentCreate:
        """
        Build the specification.

        Returns a schema that can be used to register the deployment with the API.
        """
        # Allow validation to be performed separately
        if not self._validated:
            self.validate()

        flow_id = await client.create_flow(self.flow)

        # Read the flow file
        with fsspec.open(self.flow_location, "rb") as flow_file:
            flow_bytes = flow_file.read()

        # Ensure the storage is a registered block for later retrieval

        if not self.flow_storage._block_document_id:
            block_schema = await client.read_block_schema_by_checksum(
                self.flow_storage._calculate_schema_checksum()
            )

            i = 0
            while not self.flow_storage._block_document_id:
                try:
                    block_document = await client.create_block_document(
                        block_document=self.flow_storage._to_block_document(
                            name=f"{self.flow_name}-{self.name}-{self.flow.version}-{i}",
                            block_schema_id=block_schema.id,
                            block_type_id=block_schema.block_type_id,
                        )
                    )
                    self.flow_storage._block_document_id = block_document.id
                except ObjectAlreadyExists:
                    i += 1

        # Write the flow to storage
        storage_token = await self.flow_storage.write(flow_bytes)
        flow_data = DataDocument.encode(
            encoding="blockstorage",
            data={
                "data": storage_token,
                "block_document_id": self.flow_storage._block_document_id,
            },
        )

        return DeploymentCreate(
            flow_id=flow_id,
            name=self.name,
            schedule=self.schedule,
            flow_data=flow_data,
            parameters=self.parameters,
            tags=self.tags,
            flow_runner=self.flow_runner.to_settings(),
        )

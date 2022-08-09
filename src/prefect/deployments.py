"""
Objects for specifying deployments and utilities for loading flows from deployments.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field, parse_obj_as, validator

from prefect.blocks.core import Block
from prefect.client import OrionClient, get_client, inject_client
from prefect.context import PrefectObjectRegistry
from prefect.filesystems import LocalFileSystem
from prefect.flows import Flow
from prefect.infrastructure import DockerContainer, KubernetesJob, Process
from prefect.logging.loggers import flow_run_logger
from prefect.orion import schemas
from prefect.utilities.callables import ParameterSchema
from prefect.utilities.dispatch import lookup_type
from prefect.utilities.filesystem import tmpchdir
from prefect.utilities.importtools import import_object


@inject_client
async def load_flow_from_flow_run(
    flow_run: schemas.core.FlowRun, client: OrionClient
) -> Flow:
    """
    Load a flow from the location/script provided in a deployment's storage document.
    """
    deployment = await client.read_deployment(flow_run.deployment_id)
    if deployment.storage_document_id:
        storage_document = await client.read_block_document(
            deployment.storage_document_id
        )
        storage_block = Block._from_block_document(storage_document)
    else:
        basepath = deployment.path or Path(deployment.manifest_path).parent
        storage_block = LocalFileSystem(basepath=basepath)

    sys.path.insert(0, ".")
    # TODO: append deployment.path
    await storage_block.get_directory(from_path=None, local_path=".")

    flow_run_logger(flow_run).debug(
        f"Loading flow for deployment {deployment.name!r}..."
    )

    # for backwards compat
    import_path = deployment.entrypoint
    if deployment.manifest_path:
        with open(deployment.manifest_path, "r") as f:
            import_path = json.load(f)["import_path"]
    flow = import_object(import_path)
    return flow


def load_deployments_from_yaml(
    path: str,
) -> PrefectObjectRegistry:
    """
    Load deployments from a yaml file.
    """
    with open(path, "r") as f:
        contents = f.read()

    # Parse into a yaml tree to retrieve separate documents
    nodes = yaml.compose_all(contents)

    with PrefectObjectRegistry(capture_failures=True) as registry:
        for node in nodes:
            with tmpchdir(path):
                deployment_dict = yaml.safe_load(yaml.serialize(node))
                # The return value is not necessary, just instantiating the Deployment
                # is enough to get it recorded on the registry
                parse_obj_as(Deployment, deployment_dict)

    return registry


class Deployment(BaseModel):
    class Config:
        validate_assignment = True

    @property
    def editable_fields(self) -> List[str]:
        editable_fields = [
            "name",
            "description",
            "version",
            "tags",
            "parameters",
            "schedule",
            "infra_overrides",
        ]
        if self.infrastructure._block_document_id:
            return editable_fields
        else:
            return editable_fields + ["infrastructure"]

    @property
    def header(self) -> str:
        return f"###\n### A complete description of a Prefect Deployment for flow {self.flow_name!r}\n###\n"

    def yaml_dict(self) -> dict:
        # avoids issues with UUIDs showing up in YAML
        all_fields = json.loads(
            self.json(
                exclude={
                    "storage": {"_filesystem", "filesystem", "_remote_file_system"}
                }
            )
        )
        if all_fields["storage"]:
            all_fields["storage"][
                "_block_type_slug"
            ] = self.storage.get_block_type_slug()
        return all_fields

    def editable_fields_dict(self):
        "Returns YAML compatible dictionary of editable fields, in the correct order"
        all_fields = self.yaml_dict()
        return {field: all_fields[field] for field in self.editable_fields}

    def immutable_fields_dict(self):
        "Returns YAML compatible dictionary of immutable fields, in the correct order"
        all_fields = self.yaml_dict()
        return {k: v for k, v in all_fields.items() if k not in self.editable_fields}

    # top level metadata
    name: str = Field(..., description="The name of the deployment.")
    description: str = Field(
        None, description="An optional description of the deployment."
    )
    version: str = Field(None, description="An optional version for the deployment.")
    tags: List[str] = Field(default_factory=list)
    schedule: schemas.schedules.SCHEDULE_TYPES = None
    flow_name: str = Field(..., description="The name of the flow.")

    # flow data
    parameters: Dict[str, Any] = Field(default_factory=dict)
    manifest_path: str = Field(
        None,
        description="The path to the flow's manifest file, relative to the chosen storage.",
    )
    infrastructure: Union[DockerContainer, KubernetesJob, Process] = Field(
        default_factory=Process
    )
    infra_overrides: Dict[str, Any] = Field(
        default_factory=dict,
        description="Overrides to apply to the base infrastructure block at runtime.",
    )
    storage: Optional[Block] = Field(
        None,
        help="The remote storage to use for this workflow.",
    )
    path: str = Field(
        None,
        description="The path to the working directory for the workflow, relative to remote storage or an absolute path.",
    )
    entrypoint: str = Field(
        None,
        description="The path to the entrypoint for the workflow, relative to the `path`.",
    )
    parameter_openapi_schema: ParameterSchema = Field(
        None, description="The parameter schema of the flow, including defaults."
    )

    @validator("storage", pre=True)
    def cast_storage_to_block_type(cls, value):
        if isinstance(value, dict):
            block = lookup_type(Block, value.pop("_block_type_slug"))
            return block(**value)
        return value

    @classmethod
    def load_from_yaml(cls, path: str):
        with open(str(path), "r") as f:
            data = yaml.safe_load(f)
            return cls(**data)

    async def load(self) -> bool:
        """
        Queries the API for a deployment with this name for this flow, and if found, prepopulates
        settings.  Returns a boolean specifying whether a load was successful or not.
        """
        if not self.name and self.flow_name:
            raise ValueError("Both a deployment name and flow name must be provided.")
        async with get_client() as client:
            try:
                deployment = await client.read_deployment_by_name(
                    f"{self.flow_name}/{self.name}"
                )
                self.description = deployment.description
                self.tags = deployment.tags
                self.version = deployment.version
                self.schedule = deployment.schedule
                self.parameters = deployment.parameters
                self.parameter_openapi_schema = deployment.parameter_openapi_schema
                self.infra_overrides = deployment.infra_overrides
                self.path = deployment.path
                self.entrypoint = deployment.entrypoint
                if deployment.infrastructure_document_id:
                    self.infrastructure = Block._from_block_document(
                        await client.read_block_document(
                            deployment.infrastructure_document_id
                        )
                    )
                if deployment.storage_document_id:
                    self.storage = Block._from_block_document(
                        await client.read_block_document(deployment.storage_document_id)
                    )
            except ObjectNotFound:
                return False
        return True

    def update(self, ignore_none: bool = False, **kwargs):
        """
        Performs an in-place update with the provided settings.
        """
        unknown_keys = set(kwargs.keys()) - set(self.dict().keys())
        if unknown_keys:
            raise ValueError(
                f"Received unexpected attributes: {', '.join(unknown_keys)}"
            )
        for key, value in kwargs.items():
            if ignore_none and value is None:
                continue
            setattr(self, key, value)

    async def upload_to_storage(self, storage_block: Block = None) -> Optional[int]:
        """
        Uploads the workflow this deployment represents using a provided storage block;
        if no block is provided, defaults to configuring self for local storage.
        """
        deployment_path = None
        file_count = None
        if storage_block:
            template = await Block.load(storage_block)
            self.storage = template.copy(
                exclude={"_block_document_id", "_block_document_name", "_is_anonymous"}
            )

            # upload current directory to storage location
            file_count = await self.storage.put_directory(ignore_file=".prefectignore")
        else:
            # default storage, no need to move anything around
            self.storage = None
            deployment_path = str(Path(".").absolute())

        # persists storage now in case it contains secret values
        if self.storage and not self.storage._block_document_id:
            await self.storage._save(is_anonymous=True)

        self.path = deployment_path
        return file_count

    def build_yaml(self, output: str):
        """
        Compiles the current deployment into a YAML file at the given location.
        """
        with open(output, "w") as f:
            f.write(self.header)
            yaml.dump(self.editable_fields_dict(), f, sort_keys=False)
            do_not_edit_msg = " DO NOT EDIT BELOW THIS LINE "
            msg_length = len(do_not_edit_msg)
            f.write(
                f"###{' ' * msg_length}###\n###{do_not_edit_msg}###\n###{' ' * msg_length}###\n"
            )
            yaml.dump(self.immutable_fields_dict(), f, sort_keys=False)

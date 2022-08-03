"""
Objects for specifying deployments and utilities for loading flows from deployments.
"""

import json
import sys
from typing import Any, Dict, List, Union

import yaml
from pydantic import BaseModel, Field, parse_obj_as, validator

from prefect.blocks.core import Block
from prefect.client import OrionClient, inject_client
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


async def load_flow_from_deployment(deployment: schemas.core.Deployment) -> Flow:
    """
    Load a flow from the location/script provided in a deployment's storage document.
    """
    with open(deployment.manifest_path, "r") as f:
        manifest = json.load(f)
    return import_object(manifest["import_path"])


@inject_client
async def load_flow_from_flow_run(
    flow_run: schemas.core.FlowRun, client: OrionClient
) -> Flow:
    """
    Load a flow from the location/script provided in a deployment's storage document.
    """
    deployment = await client.read_deployment(flow_run.deployment_id)
    storage_document = await client.read_block_document(deployment.storage_document_id)
    storage_block = Block._from_block_document(storage_document)

    sys.path.insert(0, ".")
    await storage_block.get_directory(from_path=None, local_path=".")

    flow_run_logger(flow_run).debug(
        f"Loading flow for deployment {deployment.name!r}..."
    )
    flow = await load_flow_from_deployment(deployment)
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


class DeploymentYAML(BaseModel):
    @property
    def editable_fields(self) -> List[str]:
        editable_fields = [
            "name",
            "description",
            "version",
            "tags",
            "parameters",
            "schedule",
            "infrastructure",
        ]
        return editable_fields

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
        all_fields["storage"]["_block_type_slug"] = self.storage.get_block_type_slug()
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
        ...,
        description="The path to the flow's manifest file, relative to the chosen storage.",
    )
    infrastructure: Union[DockerContainer, KubernetesJob, Process] = Field(
        default_factory=Process
    )
    storage: Block = Field(default_factory=LocalFileSystem)
    parameter_openapi_schema: ParameterSchema = Field(
        ..., description="The parameter schema of the flow, including defaults."
    )

    @validator("storage", pre=True)
    def cast_storage_to_block_type(cls, value):
        if isinstance(value, dict):
            block = lookup_type(Block, value.pop("_block_type_slug"))
            return block(**value)
        return value

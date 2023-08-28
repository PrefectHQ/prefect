"""
Objects for specifying deployments and utilities for loading flows from deployments.
"""

import importlib
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

import pendulum
from pydantic import BaseModel, Field, validator

from prefect.client.orchestration import ServerType, get_client
from prefect.client.schemas.schedules import SCHEDULE_TYPES
from prefect.events.schemas import DeploymentTrigger
from prefect.flows import Flow
from prefect.utilities.asyncutils import sync_compatible
from prefect.utilities.callables import ParameterSchema, parameter_schema


class RunnerDeployment(BaseModel):
    """
    A Prefect RunnerDeployment definition, used for specifying and building deployments.

    Args:
        name: A name for the deployment (required).
        version: An optional version for the deployment; defaults to the flow's version
        description: An optional description of the deployment; defaults to the flow's
            description
        tags: An optional list of tags to associate with this deployment; note that tags
            are used only for organizational purposes. For delegating work to agents,
            see `work_queue_name`.
        schedule: A schedule to run this deployment on, once registered
        is_schedule_active: Whether or not the schedule is active
        parameters: A dictionary of parameter values to pass to runs created from this
            deployment
        path: The path to the working directory for the workflow, relative to remote
            storage or, if stored on a local filesystem, an absolute path
        entrypoint: The path to the entrypoint for the workflow, always relative to the
            `path`
        parameter_openapi_schema: The parameter schema of the flow, including defaults.
    """

    name: str = Field(..., description="The name of the deployment.")
    flow_name: Optional[str] = Field(
        None, description="The name of the underlying flow; typically inferred."
    )
    description: Optional[str] = Field(
        default=None, description="An optional description of the deployment."
    )
    version: Optional[str] = Field(
        default=None, description="An optional version for the deployment."
    )
    tags: List[str] = Field(
        default_factory=list,
        description="One of more tags to apply to this deployment.",
    )
    schedule: SCHEDULE_TYPES = None
    is_schedule_active: Optional[bool] = Field(
        default=None, description="Whether or not the schedule is active."
    )
    parameters: Dict[str, Any] = Field(default_factory=dict)
    path: Optional[str] = Field(
        default=None,
        description=(
            "The path to the working directory for the workflow, relative to remote"
            " storage or an absolute path."
        ),
    )
    entrypoint: Optional[str] = Field(
        default=None,
        description=(
            "The path to the entrypoint for the workflow, relative to the `path`."
        ),
    )
    parameter_openapi_schema: ParameterSchema = Field(
        default_factory=ParameterSchema,
        description="The parameter schema of the flow, including defaults.",
    )
    timestamp: datetime = Field(default_factory=partial(pendulum.now, "UTC"))
    triggers: List[DeploymentTrigger] = Field(
        default_factory=list,
        description="The triggers that should cause this deployment to run.",
    )

    @validator("parameter_openapi_schema", pre=True)
    def handle_openapi_schema(cls, value):
        """
        This method ensures setting a value of `None` is handled gracefully.
        """
        if value is None:
            return ParameterSchema()
        return value

    @validator("triggers")
    def validate_automation_names(cls, field_value, values, field, config):
        """Ensure that each trigger has a name for its automation if none is provided."""
        for i, trigger in enumerate(field_value, start=1):
            if trigger.name is None:
                trigger.name = f"{values['name']}__automation_{i}"

        return field_value

    @sync_compatible
    async def apply(self) -> UUID:
        """
        Registers this deployment with the API and returns the deployment's ID.
        """
        async with get_client() as client:
            flow_id = await client.create_flow_from_name(self.flow_name)

            deployment_id = await client.create_deployment(
                flow_id=flow_id,
                name=self.name,
                work_queue_name=None,
                work_pool_name=None,
                version=self.version,
                schedule=self.schedule,
                is_schedule_active=self.is_schedule_active,
                parameters=self.parameters,
                description=self.description,
                tags=self.tags,
                path=self.path,
                entrypoint=self.entrypoint,
                storage_document_id=None,
                infrastructure_document_id=None,
                parameter_openapi_schema=self.parameter_openapi_schema.dict(),
            )

            if client.server_type == ServerType.CLOUD:
                # The triggers defined in the deployment spec are, essentially,
                # anonymous and attempting truly sync them with cloud is not
                # feasible. Instead, we remove all automations that are owned
                # by the deployment, meaning that they were created via this
                # mechanism below, and then recreate them.
                await client.delete_resource_owned_automations(
                    f"prefect.deployment.{deployment_id}"
                )
                for trigger in self.triggers:
                    trigger.set_deployment_id(deployment_id)
                    await client.create_automation(trigger.as_automation())

            return deployment_id

    @classmethod
    @sync_compatible
    async def from_flow(
        cls,
        flow: Flow,
        name: str,
        apply: bool = False,
        **kwargs,
    ) -> "RunnerDeployment":
        """
        Configure a deployment for a given flow.

        Args:
            flow: A flow function to deploy
            name: A name for the deployment
            apply: If True, the deployment is automatically registered with the API
            **kwargs: Other keyword arguments to pass to the constructor for the
                `RunnerDeployment` class
        """
        deployment = cls(name=name, flow_name=flow.name, **kwargs)
        # TODO: better error messages with doc links
        if not deployment.entrypoint:
            ## first see if an entrypoint can be determined
            flow_file = getattr(flow, "__globals__", {}).get("__file__")
            mod_name = getattr(flow, "__module__", None)
            if not flow_file:
                if not mod_name:
                    # todo, check if the file location was manually set already
                    raise ValueError("Could not determine flow's file location.")
                module = importlib.import_module(mod_name)
                flow_file = getattr(module, "__file__", None)
                if not flow_file:
                    raise ValueError("Could not determine flow's file location.")

            # set entrypoint
            entry_path = Path(flow_file).absolute().relative_to(Path(".").absolute())
            deployment.entrypoint = f"{entry_path}:{flow.fn.__name__}"

        # set a few attributes for this flow object
        deployment.parameter_openapi_schema = parameter_schema(flow)

        if not deployment.version:
            deployment.version = flow.version
        if not deployment.description:
            deployment.description = flow.description

        if apply:
            await deployment.apply()

        return deployment

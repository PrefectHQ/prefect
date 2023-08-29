"""
Objects for specifying deployments and utilities for loading flows from deployments.
"""

import importlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, PrivateAttr, validator

from prefect.client.orchestration import ServerType, get_client
from prefect.client.schemas.schedules import (
    SCHEDULE_TYPES,
    CronSchedule,
    IntervalSchedule,
    RRuleSchedule,
)
from prefect.events.schemas import DeploymentTrigger
from prefect.flows import Flow, load_flow_from_entrypoint
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
    schedule: Optional[SCHEDULE_TYPES] = None
    is_schedule_active: Optional[bool] = Field(
        default=None, description="Whether or not the schedule is active."
    )
    parameters: Dict[str, Any] = Field(default_factory=dict)
    entrypoint: Optional[str] = Field(
        default=None,
        description=(
            "The path to the entrypoint for the workflow, relative to the `path`."
        ),
    )
    triggers: List[DeploymentTrigger] = Field(
        default_factory=list,
        description="The triggers that should cause this deployment to run.",
    )

    _path: Optional[str] = PrivateAttr(
        default=None,
    )
    _parameter_openapi_schema: ParameterSchema = PrivateAttr(
        default_factory=ParameterSchema,
    )

    @validator("triggers", allow_reuse=True)
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
                path=self._path,
                entrypoint=self.entrypoint,
                storage_document_id=None,
                infrastructure_document_id=None,
                parameter_openapi_schema=self._parameter_openapi_schema.dict(),
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

    @staticmethod
    def _construct_schedule(
        interval: Optional[Union[int, float, timedelta]] = None,
        anchor_date: Optional[Union[str, datetime]] = None,
        cron: Optional[str] = None,
        rrule: Optional[str] = None,
        timezone: Optional[str] = None,
    ) -> Optional[SCHEDULE_TYPES]:
        schedule = None

        num_schedules = sum(
            1 for schedule in (interval, cron, rrule) if schedule is not None
        )
        if num_schedules > 1:
            raise ValueError("Only one of interval, cron, or rrule can be provided.")

        if anchor_date and not interval:
            raise ValueError(
                "An anchor date can only be provided with an interval schedule"
            )

        schedule = None
        if interval:
            if isinstance(interval, (int, float)):
                interval = timedelta(seconds=interval)
            schedule = IntervalSchedule(
                interval=interval, anchor_date=anchor_date, timezone=timezone
            )
        elif cron:
            schedule = CronSchedule(cron=cron, timezone=timezone)
        elif rrule:
            schedule = RRuleSchedule(rrule=rrule, timezone=timezone)

        return schedule

    def _set_defaults_from_flow(self, flow: Flow):
        self._parameter_openapi_schema = parameter_schema(flow)

        if not self.version:
            self.version = flow.version
        if not self.description:
            self.description = flow.description

    @classmethod
    def from_flow(
        cls,
        flow: Flow,
        name: str,
        interval: Optional[Union[int, float, timedelta]] = None,
        anchor_date: Optional[Union[str, datetime]] = None,
        cron: Optional[str] = None,
        rrule: Optional[str] = None,
        timezone: Optional[str] = None,
        parameters: Optional[dict] = None,
        triggers: Optional[List[DeploymentTrigger]] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        version: Optional[str] = None,
    ) -> "RunnerDeployment":
        """
        Configure a deployment for a given flow.

        Args:
            flow: A flow function to deploy
            name: A name for the deployment
            interval: An interval on which to execute the current flow. Accepts either a number
                or a timedelta object. If a number is given, it will be interpreted as seconds.
            anchor_date: The start date for an interval schedule.
            cron: A cron schedule of when to execute runs of this flow.
            rrule: An rrule schedule of when to execute runs of this flow.
            timezone: Timezone to used scheduling flow runs e.g. 'America/New_York'
            triggers: A list of triggers that should kick of a run of this flow.
            parameters: A dictionary of default parameter values to pass to runs of this flow.
            description: A description for the created deployment. Defaults to the flow's
                description if not provided.
            tags: A list of tags to associate with the created deployment for organizational
                purposes.
            version: A version for the created deployment. Defaults to the flow's version.
        """
        schedule = cls._construct_schedule(
            interval=interval,
            anchor_date=anchor_date,
            cron=cron,
            rrule=rrule,
            timezone=timezone,
        )

        deployment = cls(
            name=Path(name).stem,
            flow_name=flow.name,
            schedule=schedule,
            tags=tags or [],
            triggers=triggers or [],
            parameters=parameters or {},
            description=description,
            version=version,
        )

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

        if not deployment._path:
            deployment._path = str(Path.cwd())

        cls._set_defaults_from_flow(deployment, flow)

        return deployment

    @classmethod
    def from_entrypoint(
        cls,
        entrypoint: str,
        name: str,
        interval: Optional[Union[int, float, timedelta]] = None,
        anchor_date: Optional[Union[str, datetime]] = None,
        cron: Optional[str] = None,
        rrule: Optional[str] = None,
        timezone: Optional[str] = None,
        parameters: Optional[dict] = None,
        triggers: Optional[List[DeploymentTrigger]] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        version: Optional[str] = None,
    ) -> "RunnerDeployment":
        """
        Configure a deployment for a given flow located at a given entrypoint.

        Args:
            entrypoint:  The path to a file containing a flow and the name of the flow function in
                the format `./path/to/file.py:flow_func_name`.
            name: A name for the deployment
            interval: An interval on which to execute the current flow. Accepts either a number
                or a timedelta object. If a number is given, it will be interpreted as seconds.
            anchor_date: The start date for an interval schedule.
            cron: A cron schedule of when to execute runs of this flow.
            rrule: An rrule schedule of when to execute runs of this flow.
            timezone: Timezone to used scheduling flow runs e.g. 'America/New_York'
            triggers: A list of triggers that should kick of a run of this flow.
            parameters: A dictionary of default parameter values to pass to runs of this flow.
            description: A description for the created deployment. Defaults to the flow's
                description if not provided.
            tags: A list of tags to associate with the created deployment for organizational
                purposes.
            version: A version for the created deployment. Defaults to the flow's version.
            apply: If True, the deployment is automatically registered with the API
        """
        flow = load_flow_from_entrypoint(entrypoint)

        schedule = cls._construct_schedule(
            interval=interval,
            anchor_date=anchor_date,
            cron=cron,
            rrule=rrule,
            timezone=timezone,
        )

        deployment = cls(
            name=Path(name).stem,
            flow_name=flow.name,
            schedule=schedule,
            tags=tags or [],
            triggers=triggers or [],
            parameters=parameters or {},
            description=description,
            version=version,
            entrypoint=entrypoint,
            _path=str(Path.cwd()),
        )

        cls._set_defaults_from_flow(deployment, flow)

        return deployment

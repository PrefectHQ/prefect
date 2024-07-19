"""
Objects for specifying deployments and utilities for loading flows from deployments.
"""

import importlib
import json
import os
import sys
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union
from uuid import UUID

import anyio
import pendulum
import yaml

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import BaseModel, Field, parse_obj_as, root_validator, validator
else:
    from pydantic import BaseModel, Field, parse_obj_as, root_validator, validator

from prefect._internal.compatibility.deprecated import (
    DeprecatedInfraOverridesField,
    deprecated_callable,
    deprecated_class,
    deprecated_parameter,
    handle_deprecated_infra_overrides_parameter,
)
from prefect._internal.schemas.validators import (
    handle_openapi_schema,
    infrastructure_must_have_capabilities,
    reconcile_schedules,
    storage_must_have_capabilities,
    validate_automation_names,
    validate_deprecated_schedule_fields,
)
from prefect.blocks.core import Block
from prefect.blocks.fields import SecretDict
from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas.actions import DeploymentScheduleCreate
from prefect.client.schemas.objects import (
    FlowRun,
    MinimalDeploymentSchedule,
)
from prefect.client.schemas.schedules import SCHEDULE_TYPES
from prefect.client.utilities import inject_client
from prefect.context import FlowRunContext, PrefectObjectRegistry, TaskRunContext
from prefect.deployments.schedules import (
    FlexibleScheduleList,
)
from prefect.deployments.steps.core import run_steps
from prefect.events import DeploymentTriggerTypes, TriggerTypes
from prefect.exceptions import (
    BlockMissingCapabilities,
    ObjectAlreadyExists,
    ObjectNotFound,
    PrefectHTTPStatusError,
)
from prefect.filesystems import LocalFileSystem
from prefect.flows import Flow, load_flow_from_entrypoint
from prefect.infrastructure import Infrastructure, Process
from prefect.logging.loggers import flow_run_logger, get_logger
from prefect.states import Scheduled
from prefect.tasks import Task
from prefect.utilities.asyncutils import run_sync_in_worker_thread, sync_compatible
from prefect.utilities.callables import ParameterSchema, parameter_schema
from prefect.utilities.filesystem import relative_path_to_current_platform, tmpchdir
from prefect.utilities.slugify import slugify

logger = get_logger("deployments")


@sync_compatible
@deprecated_parameter(
    "infra_overrides",
    start_date="Apr 2024",
    help="Use `job_variables` instead.",
)
@inject_client
async def run_deployment(
    name: Union[str, UUID],
    client: Optional[PrefectClient] = None,
    parameters: Optional[dict] = None,
    scheduled_time: Optional[datetime] = None,
    flow_run_name: Optional[str] = None,
    timeout: Optional[float] = None,
    poll_interval: Optional[float] = 5,
    tags: Optional[Iterable[str]] = None,
    idempotency_key: Optional[str] = None,
    work_queue_name: Optional[str] = None,
    as_subflow: Optional[bool] = True,
    infra_overrides: Optional[dict] = None,
    job_variables: Optional[dict] = None,
) -> FlowRun:
    """
    Create a flow run for a deployment and return it after completion or a timeout.

    By default, this function blocks until the flow run finishes executing.
    Specify a timeout (in seconds) to wait for the flow run to execute before
    returning flow run metadata. To return immediately, without waiting for the
    flow run to execute, set `timeout=0`.

    Note that if you specify a timeout, this function will return the flow run
    metadata whether or not the flow run finished executing.

    If called within a flow or task, the flow run this function creates will
    be linked to the current flow run as a subflow. Disable this behavior by
    passing `as_subflow=False`.

    Args:
        name: The deployment id or deployment name in the form:
            `"flow name/deployment name"`
        parameters: Parameter overrides for this flow run. Merged with the deployment
            defaults.
        scheduled_time: The time to schedule the flow run for, defaults to scheduling
            the flow run to start now.
        flow_run_name: A name for the created flow run
        timeout: The amount of time to wait (in seconds) for the flow run to
            complete before returning. Setting `timeout` to 0 will return the flow
            run metadata immediately. Setting `timeout` to None will allow this
            function to poll indefinitely. Defaults to None.
        poll_interval: The number of seconds between polls
        tags: A list of tags to associate with this flow run; tags can be used in
            automations and for organizational purposes.
        idempotency_key: A unique value to recognize retries of the same run, and
            prevent creating multiple flow runs.
        work_queue_name: The name of a work queue to use for this run. Defaults to
            the default work queue for the deployment.
        as_subflow: Whether to link the flow run as a subflow of the current
            flow or task run.
        job_variables: A dictionary of dot delimited infrastructure overrides that
            will be applied at runtime; for example `env.CONFIG_KEY=config_value` or
            `namespace='prefect'`
    """
    if timeout is not None and timeout < 0:
        raise ValueError("`timeout` cannot be negative")

    if scheduled_time is None:
        scheduled_time = pendulum.now("UTC")

    jv = handle_deprecated_infra_overrides_parameter(job_variables, infra_overrides)

    parameters = parameters or {}

    deployment_id = None

    if isinstance(name, UUID):
        deployment_id = name
    else:
        try:
            deployment_id = UUID(name)
        except ValueError:
            pass

    if deployment_id:
        deployment = await client.read_deployment(deployment_id=deployment_id)
    else:
        deployment = await client.read_deployment_by_name(name)

    flow_run_ctx = FlowRunContext.get()
    task_run_ctx = TaskRunContext.get()
    if as_subflow and (flow_run_ctx or task_run_ctx):
        # This was called from a flow. Link the flow run as a subflow.
        from prefect.engine import (
            Pending,
            _dynamic_key_for_task_run,
            collect_task_run_inputs,
        )

        task_inputs = {
            k: await collect_task_run_inputs(v) for k, v in parameters.items()
        }

        if deployment_id:
            flow = await client.read_flow(deployment.flow_id)
            deployment_name = f"{flow.name}/{deployment.name}"
        else:
            deployment_name = name

        # Generate a task in the parent flow run to represent the result of the subflow
        dummy_task = Task(
            name=deployment_name,
            fn=lambda: None,
            version=deployment.version,
        )
        # Override the default task key to include the deployment name
        dummy_task.task_key = f"{__name__}.run_deployment.{slugify(deployment_name)}"
        flow_run_id = (
            flow_run_ctx.flow_run.id
            if flow_run_ctx
            else task_run_ctx.task_run.flow_run_id
        )
        dynamic_key = (
            _dynamic_key_for_task_run(flow_run_ctx, dummy_task)
            if flow_run_ctx
            else task_run_ctx.task_run.dynamic_key
        )
        parent_task_run = await client.create_task_run(
            task=dummy_task,
            flow_run_id=flow_run_id,
            dynamic_key=dynamic_key,
            task_inputs=task_inputs,
            state=Pending(),
        )
        parent_task_run_id = parent_task_run.id
    else:
        parent_task_run_id = None

    flow_run = await client.create_flow_run_from_deployment(
        deployment.id,
        parameters=parameters,
        state=Scheduled(scheduled_time=scheduled_time),
        name=flow_run_name,
        tags=tags,
        idempotency_key=idempotency_key,
        parent_task_run_id=parent_task_run_id,
        work_queue_name=work_queue_name,
        job_variables=jv,
    )

    flow_run_id = flow_run.id

    if timeout == 0:
        return flow_run

    with anyio.move_on_after(timeout):
        while True:
            flow_run = await client.read_flow_run(flow_run_id)
            flow_state = flow_run.state
            if flow_state and flow_state.is_final():
                return flow_run
            await anyio.sleep(poll_interval)

    return flow_run


@deprecated_callable(
    start_date="Jun 2024",
    help="Will be moved in Prefect 3 to prefect.flows:load_flow_from_flow_run",
)
@inject_client
async def load_flow_from_flow_run(
    flow_run: FlowRun,
    client: PrefectClient,
    ignore_storage: bool = False,
    storage_base_path: Optional[str] = None,
    use_placeholder_flow: bool = True,
) -> Flow:
    """
    Load a flow from the location/script provided in a deployment's storage document.

    If `ignore_storage=True` is provided, no pull from remote storage occurs.  This flag
    is largely for testing, and assumes the flow is already available locally.
    """
    deployment = await client.read_deployment(flow_run.deployment_id)

    if deployment.entrypoint is None:
        raise ValueError(
            f"Deployment {deployment.id} does not have an entrypoint and can not be run."
        )

    run_logger = flow_run_logger(flow_run)

    runner_storage_base_path = storage_base_path or os.environ.get(
        "PREFECT__STORAGE_BASE_PATH"
    )

    # If there's no colon, assume it's a module path
    if ":" not in deployment.entrypoint:
        run_logger.debug(
            f"Importing flow code from module path {deployment.entrypoint}"
        )
        flow = await run_sync_in_worker_thread(
            load_flow_from_entrypoint, deployment.entrypoint, use_placeholder_flow
        )
        return flow

    if not ignore_storage and not deployment.pull_steps:
        sys.path.insert(0, ".")
        if deployment.storage_document_id:
            storage_document = await client.read_block_document(
                deployment.storage_document_id
            )
            storage_block = Block._from_block_document(storage_document)
        else:
            basepath = deployment.path or Path(deployment.manifest_path).parent
            if runner_storage_base_path:
                basepath = str(basepath).replace(
                    "$STORAGE_BASE_PATH", runner_storage_base_path
                )
            storage_block = LocalFileSystem(basepath=basepath)

        from_path = (
            str(deployment.path).replace("$STORAGE_BASE_PATH", runner_storage_base_path)
            if runner_storage_base_path and deployment.path
            else deployment.path
        )
        run_logger.info(f"Downloading flow code from storage at {from_path!r}")
        await storage_block.get_directory(from_path=from_path, local_path=".")

    if deployment.pull_steps:
        run_logger.debug(f"Running {len(deployment.pull_steps)} deployment pull steps")
        output = await run_steps(deployment.pull_steps)
        if output.get("directory"):
            run_logger.debug(f"Changing working directory to {output['directory']!r}")
            os.chdir(output["directory"])

    import_path = relative_path_to_current_platform(deployment.entrypoint)
    # for backwards compat
    if deployment.manifest_path:
        with open(deployment.manifest_path, "r") as f:
            import_path = json.load(f)["import_path"]
            import_path = (
                Path(deployment.manifest_path).parent / import_path
            ).absolute()
    run_logger.debug(f"Importing flow code from '{import_path}'")

    flow = await run_sync_in_worker_thread(
        load_flow_from_entrypoint, str(import_path), use_placeholder_flow
    )

    return flow


@deprecated_callable(start_date="Mar 2024")
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


@deprecated_class(
    start_date="Mar 2024",
    help="Use `flow.deploy` to deploy your flows instead."
    " Refer to the upgrade guide for more information:"
    " https://docs.prefect.io/latest/guides/upgrade-guide-agents-to-workers/.",
)
class Deployment(DeprecatedInfraOverridesField, BaseModel):
    """
    DEPRECATION WARNING:

    This class is deprecated as of March 2024 and will not be available after September 2024.
    It has been replaced by `flow.deploy`, which offers enhanced functionality and better a better user experience.
    For upgrade instructions, see https://docs.prefect.io/latest/guides/upgrade-guide-agents-to-workers/.

    A Prefect Deployment definition, used for specifying and building deployments.

    Args:
        name: A name for the deployment (required).
        version: An optional version for the deployment; defaults to the flow's version
        description: An optional description of the deployment; defaults to the flow's
            description
        tags: An optional list of tags to associate with this deployment; note that tags
            are used only for organizational purposes. For delegating work to agents,
            see `work_queue_name`.
        schedule: A schedule to run this deployment on, once registered (deprecated)
        is_schedule_active: Whether or not the schedule is active (deprecated)
        schedules: A list of schedules to run this deployment on
        work_queue_name: The work queue that will handle this deployment's runs
        work_pool_name: The work pool for the deployment
        flow_name: The name of the flow this deployment encapsulates
        parameters: A dictionary of parameter values to pass to runs created from this
            deployment
        infrastructure: An optional infrastructure block used to configure
            infrastructure for runs; if not provided, will default to running this
            deployment in Agent subprocesses
        job_variables: A dictionary of dot delimited infrastructure overrides that
            will be applied at runtime; for example `env.CONFIG_KEY=config_value` or
            `namespace='prefect'`
        storage: An optional remote storage block used to store and retrieve this
            workflow; if not provided, will default to referencing this flow by its
            local path
        path: The path to the working directory for the workflow, relative to remote
            storage or, if stored on a local filesystem, an absolute path
        entrypoint: The path to the entrypoint for the workflow, always relative to the
            `path`
        parameter_openapi_schema: The parameter schema of the flow, including defaults.
        enforce_parameter_schema: Whether or not the Prefect API should enforce the
            parameter schema for this deployment.

    Examples:

        Create a new deployment using configuration defaults for an imported flow:

        >>> from my_project.flows import my_flow
        >>> from prefect.deployments import Deployment
        >>>
        >>> deployment = Deployment.build_from_flow(
        ...     flow=my_flow,
        ...     name="example",
        ...     version="1",
        ...     tags=["demo"],
        >>> )
        >>> deployment.apply()

        Create a new deployment with custom storage and an infrastructure override:

        >>> from my_project.flows import my_flow
        >>> from prefect.deployments import Deployment
        >>> from prefect.filesystems import S3

        >>> storage = S3.load("dev-bucket") # load a pre-defined block
        >>> deployment = Deployment.build_from_flow(
        ...     flow=my_flow,
        ...     name="s3-example",
        ...     version="2",
        ...     tags=["aws"],
        ...     storage=storage,
        ...     job_variables=dict("env.PREFECT_LOGGING_LEVEL"="DEBUG"),
        >>> )
        >>> deployment.apply()

    """

    class Config:
        json_encoders = {SecretDict: lambda v: v.dict()}
        validate_assignment = True
        extra = "forbid"

    @property
    def _editable_fields(self) -> List[str]:
        editable_fields = [
            "name",
            "description",
            "version",
            "work_queue_name",
            "work_pool_name",
            "tags",
            "parameters",
            "schedule",
            "schedules",
            "is_schedule_active",
            # The `infra_overrides` field has been renamed to `job_variables`.
            # We will continue writing it in the YAML file as `infra_overrides`
            # instead of `job_variables` for better backwards compat, but we'll
            # accept either `job_variables` or `infra_overrides` when we read
            # the file.
            "infra_overrides",
        ]

        # if infrastructure is baked as a pre-saved block, then
        # editing its fields will not update anything
        if self.infrastructure._block_document_id:
            return editable_fields
        else:
            return editable_fields + ["infrastructure"]

    @property
    def location(self) -> str:
        """
        The 'location' that this deployment points to is given by `path` alone
        in the case of no remote storage, and otherwise by `storage.basepath / path`.

        The underlying flow entrypoint is interpreted relative to this location.
        """
        location = ""
        if self.storage:
            location = (
                self.storage.basepath + "/"
                if not self.storage.basepath.endswith("/")
                else ""
            )
        if self.path:
            location += self.path
        return location

    @sync_compatible
    async def to_yaml(self, path: Path) -> None:
        yaml_dict = self._yaml_dict()
        schema = self.schema()

        with open(path, "w") as f:
            # write header
            f.write(
                "###\n### A complete description of a Prefect Deployment for flow"
                f" {self.flow_name!r}\n###\n"
            )

            # write editable fields
            for field in self._editable_fields:
                # write any comments
                if schema["properties"][field].get("yaml_comment"):
                    f.write(f"# {schema['properties'][field]['yaml_comment']}\n")
                # write the field
                yaml.dump({field: yaml_dict[field]}, f, sort_keys=False)

            # write non-editable fields, excluding `job_variables` because we'll
            # continue writing it as `infra_overrides` for better backwards compat
            # with the existing file format.
            f.write("\n###\n### DO NOT EDIT BELOW THIS LINE\n###\n")
            yaml.dump(
                {
                    k: v
                    for k, v in yaml_dict.items()
                    if k not in self._editable_fields and k != "job_variables"
                },
                f,
                sort_keys=False,
            )

    def _yaml_dict(self) -> dict:
        """
        Returns a YAML-compatible representation of this deployment as a dictionary.
        """
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
        if all_fields["infrastructure"]:
            all_fields["infrastructure"][
                "_block_type_slug"
            ] = self.infrastructure.get_block_type_slug()
        return all_fields

    @classmethod
    def _validate_schedule(cls, value):
        """We do not support COUNT-based (# of occurrences) RRule schedules for deployments."""
        if value:
            rrule_value = getattr(value, "rrule", None)
            if rrule_value and "COUNT" in rrule_value.upper():
                raise ValueError(
                    "RRule schedules with `COUNT` are not supported. Please use `UNTIL`"
                    " or the `/deployments/{id}/schedule` endpoint to schedule a fixed"
                    " number of flow runs."
                )

    # top level metadata
    name: str = Field(..., description="The name of the deployment.")
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
    schedule: Optional[SCHEDULE_TYPES] = Field(default=None)
    schedules: List[MinimalDeploymentSchedule] = Field(
        default_factory=list,
        description="The schedules to run this deployment on.",
    )
    is_schedule_active: Optional[bool] = Field(
        default=None, description="Whether or not the schedule is active."
    )
    flow_name: Optional[str] = Field(default=None, description="The name of the flow.")
    work_queue_name: Optional[str] = Field(
        "default",
        description="The work queue for the deployment.",
        yaml_comment="The work queue that will handle this deployment's runs",
    )
    work_pool_name: Optional[str] = Field(
        default=None, description="The work pool for the deployment"
    )
    # flow data
    parameters: Dict[str, Any] = Field(default_factory=dict)
    manifest_path: Optional[str] = Field(
        default=None,
        description=(
            "The path to the flow's manifest file, relative to the chosen storage."
        ),
    )
    infrastructure: Infrastructure = Field(default_factory=Process)
    job_variables: Dict[str, Any] = Field(
        default_factory=dict,
        description="Overrides to apply to the base infrastructure block at runtime.",
    )
    storage: Optional[Block] = Field(
        None,
        help="The remote storage to use for this workflow.",
    )
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
    triggers: List[Union[DeploymentTriggerTypes, TriggerTypes]] = Field(
        default_factory=list,
        description="The triggers that should cause this deployment to run.",
    )
    # defaults to None to allow for backwards compatibility
    enforce_parameter_schema: Optional[bool] = Field(
        default=None,
        description=(
            "Whether or not the Prefect API should enforce the parameter schema for"
            " this deployment."
        ),
    )

    @validator("infrastructure", pre=True)
    def validate_infrastructure_capabilities(cls, value):
        return infrastructure_must_have_capabilities(value)

    @validator("storage", pre=True)
    def validate_storage(cls, value):
        return storage_must_have_capabilities(value)

    @validator("parameter_openapi_schema", pre=True)
    def validate_parameter_openapi_schema(cls, value):
        return handle_openapi_schema(value)

    @validator("triggers")
    def validate_triggers(cls, field_value, values):
        return validate_automation_names(field_value, values)

    @root_validator(pre=True)
    def validate_schedule(cls, values):
        return validate_deprecated_schedule_fields(values, logger)

    @root_validator(pre=True)
    def validate_backwards_compatibility_for_schedule(cls, values):
        return reconcile_schedules(cls, values)

    @classmethod
    @sync_compatible
    async def load_from_yaml(cls, path: str):
        data = yaml.safe_load(await anyio.Path(path).read_bytes())
        # load blocks from server to ensure secret values are properly hydrated
        if data.get("storage"):
            block_doc_name = data["storage"].get("_block_document_name")
            # if no doc name, this block is not stored on the server
            if block_doc_name:
                block_slug = data["storage"]["_block_type_slug"]
                block = await Block.load(f"{block_slug}/{block_doc_name}")
                data["storage"] = block

        if data.get("infrastructure"):
            block_doc_name = data["infrastructure"].get("_block_document_name")
            # if no doc name, this block is not stored on the server
            if block_doc_name:
                block_slug = data["infrastructure"]["_block_type_slug"]
                block = await Block.load(f"{block_slug}/{block_doc_name}")
                data["infrastructure"] = block

            return cls(**data)

    @sync_compatible
    async def load(self) -> bool:
        """
        Queries the API for a deployment with this name for this flow, and if found,
        prepopulates any settings that were not set at initialization.

        Returns a boolean specifying whether a load was successful or not.

        Raises:
            - ValueError: if both name and flow name are not set
        """
        if not self.name or not self.flow_name:
            raise ValueError("Both a deployment name and flow name must be provided.")
        async with get_client() as client:
            try:
                deployment = await client.read_deployment_by_name(
                    f"{self.flow_name}/{self.name}"
                )
                if deployment.storage_document_id:
                    Block._from_block_document(
                        await client.read_block_document(deployment.storage_document_id)
                    )

                excluded_fields = self.__fields_set__.union(
                    {
                        "infrastructure",
                        "storage",
                        "timestamp",
                        "triggers",
                        "enforce_parameter_schema",
                        "schedules",
                        "schedule",
                        "is_schedule_active",
                    }
                )
                for field in set(self.__fields__.keys()) - excluded_fields:
                    new_value = getattr(deployment, field)
                    setattr(self, field, new_value)

                if "schedules" not in self.__fields_set__:
                    self.schedules = [
                        MinimalDeploymentSchedule(
                            **schedule.dict(include={"schedule", "active"})
                        )
                        for schedule in deployment.schedules
                    ]

                # The API server generates the "schedule" field from the
                # current list of schedules, so if the user has locally set
                # "schedules" to anything, we should avoid sending "schedule"
                # and let the API server generate a new value if necessary.
                if "schedules" in self.__fields_set__:
                    self.schedule = None
                    self.is_schedule_active = None
                else:
                    # The user isn't using "schedules," so we should
                    # populate "schedule" and "is_schedule_active" from the
                    # API's version of the deployment, unless the user gave
                    # us these fields in __init__().
                    if "schedule" not in self.__fields_set__:
                        self.schedule = deployment.schedule
                    if "is_schedule_active" not in self.__fields_set__:
                        self.is_schedule_active = deployment.is_schedule_active

                if "infrastructure" not in self.__fields_set__:
                    if deployment.infrastructure_document_id:
                        self.infrastructure = Block._from_block_document(
                            await client.read_block_document(
                                deployment.infrastructure_document_id
                            )
                        )
                if "storage" not in self.__fields_set__:
                    if deployment.storage_document_id:
                        self.storage = Block._from_block_document(
                            await client.read_block_document(
                                deployment.storage_document_id
                            )
                        )
            except ObjectNotFound:
                return False
        return True

    @sync_compatible
    async def update(self, ignore_none: bool = False, **kwargs):
        """
        Performs an in-place update with the provided settings.

        Args:
            ignore_none: if True, all `None` values are ignored when performing the
                update
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

    @sync_compatible
    async def upload_to_storage(
        self, storage_block: str = None, ignore_file: str = ".prefectignore"
    ) -> Optional[int]:
        """
        Uploads the workflow this deployment represents using a provided storage block;
        if no block is provided, defaults to configuring self for local storage.

        Args:
            storage_block: a string reference a remote storage block slug `$type/$name`;
                if provided, used to upload the workflow's project
            ignore_file: an optional path to a `.prefectignore` file that specifies
                filename patterns to ignore when uploading to remote storage; if not
                provided, looks for `.prefectignore` in the current working directory
        """
        file_count = None
        if storage_block:
            storage = await Block.load(storage_block)

            if "put-directory" not in storage.get_block_capabilities():
                raise BlockMissingCapabilities(
                    f"Storage block {storage!r} missing 'put-directory' capability."
                )

            self.storage = storage

            # upload current directory to storage location
            file_count = await self.storage.put_directory(
                ignore_file=ignore_file, to_path=self.path
            )
        elif self.storage:
            if "put-directory" not in self.storage.get_block_capabilities():
                raise BlockMissingCapabilities(
                    f"Storage block {self.storage!r} missing 'put-directory'"
                    " capability."
                )

            file_count = await self.storage.put_directory(
                ignore_file=ignore_file, to_path=self.path
            )

        # persists storage now in case it contains secret values
        if self.storage and not self.storage._block_document_id:
            await self.storage._save(is_anonymous=True)

        return file_count

    @sync_compatible
    async def apply(
        self, upload: bool = False, work_queue_concurrency: int = None
    ) -> UUID:
        """
        Registers this deployment with the API and returns the deployment's ID.

        Args:
            upload: if True, deployment files are automatically uploaded to remote
                storage
            work_queue_concurrency: If provided, sets the concurrency limit on the
                deployment's work queue
        """
        if not self.name or not self.flow_name:
            raise ValueError("Both a deployment name and flow name must be set.")
        async with get_client() as client:
            # prep IDs
            flow_id = await client.create_flow_from_name(self.flow_name)

            infrastructure_document_id = self.infrastructure._block_document_id
            if not infrastructure_document_id:
                # if not building off a block, will create an anonymous block
                self.infrastructure = self.infrastructure.copy()
                infrastructure_document_id = await self.infrastructure._save(
                    is_anonymous=True,
                )

            if upload:
                await self.upload_to_storage()

            if self.work_queue_name and work_queue_concurrency is not None:
                try:
                    res = await client.create_work_queue(
                        name=self.work_queue_name, work_pool_name=self.work_pool_name
                    )
                except ObjectAlreadyExists:
                    res = await client.read_work_queue_by_name(
                        name=self.work_queue_name, work_pool_name=self.work_pool_name
                    )
                await client.update_work_queue(
                    res.id, concurrency_limit=work_queue_concurrency
                )

            if self.schedule:
                logger.info(
                    "Interpreting the deprecated `schedule` field as an entry in "
                    "`schedules`."
                )
                schedules = [
                    DeploymentScheduleCreate(
                        schedule=self.schedule, active=self.is_schedule_active
                    )
                ]
            elif self.schedules:
                schedules = [
                    DeploymentScheduleCreate(**schedule.dict())
                    for schedule in self.schedules
                ]
            else:
                schedules = None

            # we assume storage was already saved
            storage_document_id = getattr(self.storage, "_block_document_id", None)
            deployment_id = await client.create_deployment(
                flow_id=flow_id,
                name=self.name,
                work_queue_name=self.work_queue_name,
                work_pool_name=self.work_pool_name,
                version=self.version,
                schedules=schedules,
                is_schedule_active=self.is_schedule_active,
                parameters=self.parameters,
                description=self.description,
                tags=self.tags,
                manifest_path=self.manifest_path,  # allows for backwards YAML compat
                path=self.path,
                entrypoint=self.entrypoint,
                job_variables=self.job_variables,
                storage_document_id=storage_document_id,
                infrastructure_document_id=infrastructure_document_id,
                parameter_openapi_schema=self.parameter_openapi_schema.dict(),
                enforce_parameter_schema=self.enforce_parameter_schema,
            )

            if client.server_type.supports_automations():
                try:
                    # The triggers defined in the deployment spec are, essentially,
                    # anonymous and attempting truly sync them with cloud is not
                    # feasible. Instead, we remove all automations that are owned
                    # by the deployment, meaning that they were created via this
                    # mechanism below, and then recreate them.
                    await client.delete_resource_owned_automations(
                        f"prefect.deployment.{deployment_id}"
                    )
                except PrefectHTTPStatusError as e:
                    if e.response.status_code == 404:
                        # This Prefect server does not support automations, so we can safely
                        # ignore this 404 and move on.
                        return deployment_id
                    raise e

                for trigger in self.triggers:
                    trigger.set_deployment_id(deployment_id)
                    await client.create_automation(trigger.as_automation())

            return deployment_id

    @classmethod
    @sync_compatible
    async def build_from_flow(
        cls,
        flow: Flow,
        name: str,
        output: str = None,
        skip_upload: bool = False,
        ignore_file: str = ".prefectignore",
        apply: bool = False,
        load_existing: bool = True,
        schedules: Optional[FlexibleScheduleList] = None,
        **kwargs,
    ) -> "Deployment":
        """
        Configure a deployment for a given flow.

        Args:
            flow: A flow function to deploy
            name: A name for the deployment
            output (optional): if provided, the full deployment specification will be
                written as a YAML file in the location specified by `output`
            skip_upload: if True, deployment files are not automatically uploaded to
                remote storage
            ignore_file: an optional path to a `.prefectignore` file that specifies
                filename patterns to ignore when uploading to remote storage; if not
                provided, looks for `.prefectignore` in the current working directory
            apply: if True, the deployment is automatically registered with the API
            load_existing: if True, load any settings that may already be configured for
                the named deployment server-side (e.g., schedules, default parameter
                values, etc.)
            schedules: An optional list of schedules. Each item in the list can be:
                  - An instance of `MinimalDeploymentSchedule`.
                  - A dictionary with a `schedule` key, and optionally, an
                    `active` key. The `schedule` key should correspond to a
                    schedule type, and `active` is a boolean indicating whether
                    the schedule is active or not.
                  - An instance of one of the predefined schedule types:
                    `IntervalSchedule`, `CronSchedule`, or `RRuleSchedule`.
            **kwargs: other keyword arguments to pass to the constructor for the
                `Deployment` class
        """
        if not name:
            raise ValueError("A deployment name must be provided.")

        # note that `deployment.load` only updates settings that were *not*
        # provided at initialization

        deployment_args = {
            "name": name,
            "flow_name": flow.name,
            **kwargs,
        }

        if schedules is not None:
            deployment_args["schedules"] = schedules

        deployment = cls(**deployment_args)
        deployment.flow_name = flow.name
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

        if load_existing:
            await deployment.load()

        # set a few attributes for this flow object
        deployment.parameter_openapi_schema = parameter_schema(flow)

        # ensure the ignore file exists
        if not Path(ignore_file).exists():
            Path(ignore_file).touch()

        if not deployment.version:
            deployment.version = flow.version
        if not deployment.description:
            deployment.description = flow.description

        # proxy for whether infra is docker-based
        is_docker_based = hasattr(deployment.infrastructure, "image")

        if not deployment.storage and not is_docker_based and not deployment.path:
            deployment.path = str(Path(".").absolute())
        elif not deployment.storage and is_docker_based:
            # only update if a path is not already set
            if not deployment.path:
                deployment.path = "/opt/prefect/flows"

        if not skip_upload:
            if (
                deployment.storage
                and "put-directory" in deployment.storage.get_block_capabilities()
            ):
                await deployment.upload_to_storage(ignore_file=ignore_file)

        if output:
            await deployment.to_yaml(output)

        if apply:
            await deployment.apply()

        return deployment

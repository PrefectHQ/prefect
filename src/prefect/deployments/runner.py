"""
Objects for creating and configuring deployments for flows using `serve` functionality.

Example:
    ```python
    import time
    from prefect import flow, serve


    @flow
    def slow_flow(sleep: int = 60):
        "Sleepy flow - sleeps the provided amount of time (in seconds)."
        time.sleep(sleep)


    @flow
    def fast_flow():
        "Fastest flow this side of the Mississippi."
        return


    if __name__ == "__main__":
        # to_deployment creates RunnerDeployment instances
        slow_deploy = slow_flow.to_deployment(name="sleeper", interval=45)
        fast_deploy = fast_flow.to_deployment(name="fast")

        serve(slow_deploy, fast_deploy)
    ```

"""

import importlib
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union
from uuid import UUID

import pendulum
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, track
from rich.table import Table

from prefect._internal.concurrency.api import create_call, from_async
from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect.runner.storage import RunnerStorage
from prefect.settings import PREFECT_UI_URL
from prefect.utilities.collections import get_from_dict

if HAS_PYDANTIC_V2:
    from pydantic.v1 import BaseModel, Field, PrivateAttr, validator
else:
    from pydantic import BaseModel, Field, PrivateAttr, validator

from prefect.client.orchestration import ServerType, get_client
from prefect.client.schemas.schedules import (
    SCHEDULE_TYPES,
    construct_schedule,
)
from prefect.events.schemas import DeploymentTrigger
from prefect.exceptions import (
    ObjectNotFound,
    PrefectHTTPStatusError,
)
from prefect.utilities.asyncutils import sync_compatible
from prefect.utilities.callables import ParameterSchema, parameter_schema
from prefect.utilities.dockerutils import (
    PushError,
    build_image,
    docker_client,
    generate_default_dockerfile,
    parse_image_tag,
)
from prefect.utilities.slugify import slugify

if TYPE_CHECKING:
    from prefect.flows import Flow

__all__ = ["RunnerDeployment"]


class DeploymentApplyError(RuntimeError):
    """
    Raised when an error occurs while applying a deployment.
    """


class RunnerDeployment(BaseModel):
    """
    A Prefect RunnerDeployment definition, used for specifying and building deployments.

    Attributes:
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
        enforce_parameter_schema: Whether or not the Prefect API should enforce the
            parameter schema for this deployment.
        work_pool_name: The name of the work pool to use for this deployment.
        work_queue_name: The name of the work queue to use for this deployment's scheduled runs.
            If not provided the default work queue for the work pool will be used.
        job_variables: Settings used to override the values specified default base job template
            of the chosen work pool. Refer to the base job template of the chosen work pool for
            available settings.
    """

    class Config:
        arbitrary_types_allowed = True

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
    enforce_parameter_schema: bool = Field(
        default=False,
        description=(
            "Whether or not the Prefect API should enforce the parameter schema for"
            " this deployment."
        ),
    )
    storage: Optional[RunnerStorage] = Field(
        default=None,
        description=(
            "The storage object used to retrieve flow code for this deployment."
        ),
    )
    work_pool_name: Optional[str] = Field(
        default=None,
        description=(
            "The name of the work pool to use for this deployment. Only used when"
            " the deployment is registered with a built runner."
        ),
    )
    work_queue_name: Optional[str] = Field(
        default=None,
        description=(
            "The name of the work queue to use for this deployment. Only used when"
            " the deployment is registered with a built runner."
        ),
    )
    job_variables: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Job variables used to override the default values of a work pool"
            " base job template. Only used when the deployment is registered with"
            " a built runner."
        ),
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
    async def apply(
        self, work_pool_name: Optional[str] = None, image: Optional[str] = None
    ) -> UUID:
        """
        Registers this deployment with the API and returns the deployment's ID.

        Args:
            work_pool_name: The name of the work pool to use for this
                deployment.
            image: The registry, name, and tag of the Docker image to
                use for this deployment. Only used when the deployment is
                deployed to a work pool.

        Returns:
            The ID of the created deployment.
        """
        work_pool_name = work_pool_name or self.work_pool_name

        if image and not work_pool_name:
            raise ValueError(
                "An image can only be provided when registering a deployment with a"
                " work pool."
            )

        if self.work_queue_name and not work_pool_name:
            raise ValueError(
                "A work queue can only be provided when registering a deployment with"
                " a work pool."
            )

        if self.job_variables and not work_pool_name:
            raise ValueError(
                "Job variables can only be provided when registering a deployment"
                " with a work pool."
            )

        async with get_client() as client:
            flow_id = await client.create_flow_from_name(self.flow_name)

            create_payload = dict(
                flow_id=flow_id,
                name=self.name,
                work_queue_name=self.work_queue_name,
                work_pool_name=work_pool_name,
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
                enforce_parameter_schema=self.enforce_parameter_schema,
            )

            if work_pool_name:
                create_payload["infra_overrides"] = {
                    **self.job_variables,
                    "command": "prefect flow-run execute",
                }
                if image:
                    create_payload["infra_overrides"]["image"] = image
                create_payload["path"] = None if self.storage else self._path
                create_payload["pull_steps"] = (
                    [self.storage.to_pull_step()] if self.storage else []
                )

            try:
                deployment_id = await client.create_deployment(**create_payload)
            except Exception as exc:
                if isinstance(exc, PrefectHTTPStatusError):
                    detail = exc.response.json().get("detail")
                    if detail:
                        raise DeploymentApplyError(detail) from exc
                raise DeploymentApplyError(
                    f"Error while applying deployment: {str(exc)}"
                ) from exc

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
        anchor_date: Optional[Union[datetime, str]] = None,
        cron: Optional[str] = None,
        rrule: Optional[str] = None,
        timezone: Optional[str] = None,
        schedule: Optional[SCHEDULE_TYPES] = None,
    ) -> Optional[SCHEDULE_TYPES]:
        """
        Construct a schedule from the provided arguments.

        This is a single path for all serve schedules. If schedule is provided,
        it is returned. Otherwise, the other arguments are used to construct a schedule.

        Args:
            interval: An interval on which to schedule runs. Accepts either a number
                or a timedelta object. If a number is given, it will be interpreted as seconds.
            anchor_date: The start date for an interval schedule.
            cron: A cron schedule for runs.
            rrule: An rrule schedule of when to execute runs of this flow.
            timezone: A timezone to use for the schedule.
            schedule: A schedule object of when to execute runs of this flow. Used for
                advanced scheduling options like timezone.
        """
        num_schedules = sum(
            1 for entry in (interval, cron, rrule, schedule) if entry is not None
        )
        if num_schedules > 1:
            raise ValueError(
                "Only one of interval, cron, rrule, or schedule can be provided."
            )

        if schedule:
            return schedule
        elif interval or cron or rrule:
            return construct_schedule(
                interval=interval,
                cron=cron,
                rrule=rrule,
                timezone=timezone,
                anchor_date=anchor_date,
            )
        else:
            return None

    def _set_defaults_from_flow(self, flow: "Flow"):
        self._parameter_openapi_schema = parameter_schema(flow)

        if not self.version:
            self.version = flow.version
        if not self.description:
            self.description = flow.description

    @classmethod
    def from_flow(
        cls,
        flow: "Flow",
        name: str,
        interval: Optional[Union[int, float, timedelta]] = None,
        cron: Optional[str] = None,
        rrule: Optional[str] = None,
        schedule: Optional[SCHEDULE_TYPES] = None,
        parameters: Optional[dict] = None,
        triggers: Optional[List[DeploymentTrigger]] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        version: Optional[str] = None,
        enforce_parameter_schema: bool = False,
        work_pool_name: Optional[str] = None,
        work_queue_name: Optional[str] = None,
        job_variables: Optional[Dict[str, Any]] = None,
    ) -> "RunnerDeployment":
        """
        Configure a deployment for a given flow.

        Args:
            flow: A flow function to deploy
            name: A name for the deployment
            interval: An interval on which to execute the current flow. Accepts either a number
                or a timedelta object. If a number is given, it will be interpreted as seconds.
            cron: A cron schedule of when to execute runs of this flow.
            rrule: An rrule schedule of when to execute runs of this flow.
            schedule: A schedule object of when to execute runs of this flow. Used for
                advanced scheduling options like timezone.
            triggers: A list of triggers that should kick of a run of this flow.
            parameters: A dictionary of default parameter values to pass to runs of this flow.
            description: A description for the created deployment. Defaults to the flow's
                description if not provided.
            tags: A list of tags to associate with the created deployment for organizational
                purposes.
            version: A version for the created deployment. Defaults to the flow's version.
            enforce_parameter_schema: Whether or not the Prefect API should enforce the
                parameter schema for this deployment.
            work_pool_name: The name of the work pool to use for this deployment.
            work_queue_name: The name of the work queue to use for this deployment's scheduled runs.
                If not provided the default work queue for the work pool will be used.
            job_variables: Settings used to override the values specified default base job template
                of the chosen work pool. Refer to the base job template of the chosen work pool for
                available settings.
        """
        schedule = cls._construct_schedule(
            interval=interval, cron=cron, rrule=rrule, schedule=schedule
        )

        job_variables = job_variables or {}

        deployment = cls(
            name=Path(name).stem,
            flow_name=flow.name,
            schedule=schedule,
            tags=tags or [],
            triggers=triggers or [],
            parameters=parameters or {},
            description=description,
            version=version,
            enforce_parameter_schema=enforce_parameter_schema,
            work_pool_name=work_pool_name,
            work_queue_name=work_queue_name,
            job_variables=job_variables,
        )

        if not deployment.entrypoint:
            no_file_location_error = (
                "Flows defined interactively cannot be deployed. Check out the"
                " quickstart guide for help getting started:"
                " https://docs.prefect.io/latest/getting-started/quickstart"
            )
            ## first see if an entrypoint can be determined
            flow_file = getattr(flow, "__globals__", {}).get("__file__")
            mod_name = getattr(flow, "__module__", None)
            if not flow_file:
                if not mod_name:
                    raise ValueError(no_file_location_error)
                try:
                    module = importlib.import_module(mod_name)
                    flow_file = getattr(module, "__file__", None)
                except ModuleNotFoundError as exc:
                    if "__prefect_loader__" in str(exc):
                        raise ValueError(
                            "Cannot create a RunnerDeployment from a flow that has been"
                            " loaded from an entrypoint. To deploy a flow via"
                            " entrypoint, use RunnerDeployment.from_entrypoint instead."
                        )
                    raise ValueError(no_file_location_error)
                if not flow_file:
                    raise ValueError(no_file_location_error)

            # set entrypoint
            entry_path = Path(flow_file).absolute().relative_to(Path.cwd().absolute())
            deployment.entrypoint = f"{entry_path}:{flow.fn.__name__}"

        if not deployment._path:
            deployment._path = "."

        cls._set_defaults_from_flow(deployment, flow)

        return deployment

    @classmethod
    def from_entrypoint(
        cls,
        entrypoint: str,
        name: str,
        interval: Optional[Union[int, float, timedelta]] = None,
        cron: Optional[str] = None,
        rrule: Optional[str] = None,
        schedule: Optional[SCHEDULE_TYPES] = None,
        parameters: Optional[dict] = None,
        triggers: Optional[List[DeploymentTrigger]] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        version: Optional[str] = None,
        enforce_parameter_schema: bool = False,
        work_pool_name: Optional[str] = None,
        work_queue_name: Optional[str] = None,
        job_variables: Optional[Dict[str, Any]] = None,
    ) -> "RunnerDeployment":
        """
        Configure a deployment for a given flow located at a given entrypoint.

        Args:
            entrypoint:  The path to a file containing a flow and the name of the flow function in
                the format `./path/to/file.py:flow_func_name`.
            name: A name for the deployment
            interval: An interval on which to execute the current flow. Accepts either a number
                or a timedelta object. If a number is given, it will be interpreted as seconds.
            cron: A cron schedule of when to execute runs of this flow.
            rrule: An rrule schedule of when to execute runs of this flow.
            schedule: A schedule object of when to execute runs of this flow. Used for
                advanced scheduling options like timezone.
            triggers: A list of triggers that should kick of a run of this flow.
            parameters: A dictionary of default parameter values to pass to runs of this flow.
            description: A description for the created deployment. Defaults to the flow's
                description if not provided.
            tags: A list of tags to associate with the created deployment for organizational
                purposes.
            version: A version for the created deployment. Defaults to the flow's version.
            enforce_parameter_schema: Whether or not the Prefect API should enforce the
                parameter schema for this deployment.
            work_pool_name: The name of the work pool to use for this deployment.
            work_queue_name: The name of the work queue to use for this deployment's scheduled runs.
                If not provided the default work queue for the work pool will be used.
            job_variables: Settings used to override the values specified default base job template
                of the chosen work pool. Refer to the base job template of the chosen work pool for
                available settings.
        """
        from prefect.flows import load_flow_from_entrypoint

        job_variables = job_variables or {}
        flow = load_flow_from_entrypoint(entrypoint)

        schedule = cls._construct_schedule(
            interval=interval,
            cron=cron,
            rrule=rrule,
            schedule=schedule,
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
            enforce_parameter_schema=enforce_parameter_schema,
            work_pool_name=work_pool_name,
            work_queue_name=work_queue_name,
            job_variables=job_variables,
        )
        deployment._path = str(Path.cwd())

        cls._set_defaults_from_flow(deployment, flow)

        return deployment

    @classmethod
    @sync_compatible
    async def from_storage(
        cls,
        storage: RunnerStorage,
        entrypoint: str,
        name: str,
        interval: Optional[Union[int, float, timedelta]] = None,
        cron: Optional[str] = None,
        rrule: Optional[str] = None,
        schedule: Optional[SCHEDULE_TYPES] = None,
        parameters: Optional[dict] = None,
        triggers: Optional[List[DeploymentTrigger]] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        version: Optional[str] = None,
        enforce_parameter_schema: bool = False,
        work_pool_name: Optional[str] = None,
        work_queue_name: Optional[str] = None,
        job_variables: Optional[Dict[str, Any]] = None,
    ):
        """
        Create a RunnerDeployment from a flow located at a given entrypoint and stored in a
        local storage location.

        Args:
            entrypoint:  The path to a file containing a flow and the name of the flow function in
                the format `./path/to/file.py:flow_func_name`.
            name: A name for the deployment
            storage: A storage object to use for retrieving flow code. If not provided, a
                URL must be provided.
            interval: An interval on which to execute the current flow. Accepts either a number
                or a timedelta object. If a number is given, it will be interpreted as seconds.
            cron: A cron schedule of when to execute runs of this flow.
            rrule: An rrule schedule of when to execute runs of this flow.
            schedule: A schedule object of when to execute runs of this flow. Used for
                advanced scheduling options like timezone.
            triggers: A list of triggers that should kick of a run of this flow.
            parameters: A dictionary of default parameter values to pass to runs of this flow.
            description: A description for the created deployment. Defaults to the flow's
                description if not provided.
            tags: A list of tags to associate with the created deployment for organizational
                purposes.
            version: A version for the created deployment. Defaults to the flow's version.
            enforce_parameter_schema: Whether or not the Prefect API should enforce the
                parameter schema for this deployment.
            work_pool_name: The name of the work pool to use for this deployment.
            work_queue_name: The name of the work queue to use for this deployment's scheduled runs.
                If not provided the default work queue for the work pool will be used.
            job_variables: Settings used to override the values specified default base job template
                of the chosen work pool. Refer to the base job template of the chosen work pool for
                available settings.
        """
        from prefect.flows import load_flow_from_entrypoint

        schedule = cls._construct_schedule(
            interval=interval, cron=cron, rrule=rrule, schedule=schedule
        )
        job_variables = job_variables or {}

        with tempfile.TemporaryDirectory() as tmpdir:
            storage.set_base_path(Path(tmpdir))
            await storage.pull_code()

            full_entrypoint = str(storage.destination / entrypoint)
            flow = await from_async.wait_for_call_in_new_thread(
                create_call(load_flow_from_entrypoint, full_entrypoint)
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
            enforce_parameter_schema=enforce_parameter_schema,
            storage=storage,
            work_pool_name=work_pool_name,
            work_queue_name=work_queue_name,
            job_variables=job_variables,
        )
        deployment._path = str(storage.destination).replace(
            tmpdir, "$STORAGE_BASE_PATH"
        )

        cls._set_defaults_from_flow(deployment, flow)

        return deployment


class DeploymentImage:
    """
    Configuration used to build and push a Docker image for a deployment.

    Attributes:
        name: The name of the Docker image to build, including the registry and
            repository.
        tag: The tag to apply to the built image.
        dockerfile: The path to the Dockerfile to use for building the image. If
            not provided, a default Dockerfile will be generated.
        **build_kwargs: Additional keyword arguments to pass to the Docker build request.
            See the [`docker-py` documentation](https://docker-py.readthedocs.io/en/stable/images.html#docker.models.images.ImageCollection.build)
            for more information.

    """

    def __init__(self, name, tag=None, dockerfile="auto", **build_kwargs):
        self.name = name
        self.tag = tag or slugify(pendulum.now("utc").isoformat())
        self.dockerfile = dockerfile
        self.build_kwargs = build_kwargs

    @property
    def reference(self):
        return f"{self.name}:{self.tag}"

    def build(self):
        full_image_name = self.reference
        build_kwargs = self.build_kwargs.copy()
        build_kwargs["context"] = Path.cwd()
        build_kwargs["tag"] = full_image_name
        build_kwargs["pull"] = build_kwargs.get("pull", True)

        if self.dockerfile == "auto":
            with generate_default_dockerfile():
                build_image(**build_kwargs)
        else:
            build_kwargs["dockerfile"] = self.dockerfile
            build_image(**build_kwargs)

    def push(self):
        with docker_client() as client:
            events = client.api.push(
                repository=self.name, tag=self.tag, stream=True, decode=True
            )
            for event in events:
                if "error" in event:
                    raise PushError(event["error"])


@sync_compatible
async def deploy(
    *deployments: RunnerDeployment,
    work_pool_name: str,
    image: Union[str, DeploymentImage],
    push: bool = True,
    print_next_steps_message: bool = True,
) -> List[UUID]:
    """
    Deploy the provided list of deployments to dynamic infrastructure via a
    work pool.

    Calling this function will build a Docker image for the deployments, push it to a
    registry, and create each deployment via the Prefect API that will run the corresponding
    flow on the given schedule.

    Args:
        *deployments: A list of deployments to deploy.
        work_pool_name: The name of the work pool to use for these deployments.
        image: The name of the Docker image to build, including the registry and
            repository. Pass a DeploymentImage instance to customize the Dockerfile used
            and build arguments.
        push: Whether or not to skip pushing the built image to a registry.
        print_next_steps_message: Whether or not to print a message with next steps
            after deploying the deployments.

    Returns:
        A list of deployment IDs for the created/updated deployments.

    Examples:
        Deploy a group of flows to a work pool:

        ```python
        from prefect import deploy, flow

        @flow(log_prints=True)
        def local_flow():
            print("I'm a locally defined flow!")

        if __name__ == "__main__":
            deploy(
                local_flow.to_deployment(name="example-deploy-local-flow"),
                flow.from_source(
                    source="https://github.com/org/repo.git",
                    entrypoint="flows.py:my_flow",
                ).to_deployment(
                    name="example-deploy-remote-flow",
                ),
                work_pool_name="my-work-pool",
                image="my-registry/my-image:dev",
            )
        ```
    """
    if isinstance(image, str):
        image_name, image_tag = parse_image_tag(image)
        image = DeploymentImage(name=image_name, tag=image_tag)

    try:
        async with get_client() as client:
            work_pool = await client.read_work_pool(work_pool_name)
    except ObjectNotFound as exc:
        raise ValueError(
            f"Could not find work pool {work_pool_name!r}. Please create it before"
            " deploying this flow."
        ) from exc

    is_docker_based_work_pool = get_from_dict(
        work_pool.base_job_template, "variables.properties.image", False
    )
    if not is_docker_based_work_pool:
        raise ValueError(
            f"Work pool {work_pool_name!r} does not support custom Docker images. "
            "Please use a work pool with an `image` variable in its base job template."
        )

    console = Console()
    with Progress(
        SpinnerColumn(),
        TextColumn(f"Building image {image.reference}..."),
        transient=True,
        console=console,
    ) as progress:
        docker_build_task = progress.add_task("docker_build", total=1)
        image.build()

        progress.update(docker_build_task, completed=1)
        console.print(f"Successfully built image {image.reference!r}", style="green")

    if push:
        with Progress(
            SpinnerColumn(),
            TextColumn("Pushing image..."),
            transient=True,
            console=console,
        ) as progress:
            docker_push_task = progress.add_task("docker_push", total=1)

            image.push()

            progress.update(docker_push_task, completed=1)

        console.print(f"Successfully pushed image {image.reference!r}", style="green")

    deployment_exceptions = []
    deployment_ids = []
    for deployment in track(
        deployments,
        description="Creating/updating deployments...",
        console=console,
        transient=True,
    ):
        try:
            deployment_ids.append(
                await deployment.apply(
                    image=image.reference, work_pool_name=work_pool_name
                )
            )
        except Exception as exc:
            if len(deployments) == 1:
                raise
            deployment_exceptions.append({"deployment": deployment, "exc": exc})

    if deployment_exceptions:
        console.print(
            "Encountered errors while creating/updating deployments:\n",
            style="orange_red1",
        )
    else:
        console.print("Successfully created/updated all deployments!\n", style="green")

    complete_failure = len(deployment_exceptions) == len(deployments)

    table = Table(
        title="Deployments",
        show_lines=True,
    )

    table.add_column(header="Name", style="blue", no_wrap=True)
    table.add_column(header="Status", style="blue", no_wrap=True)
    table.add_column(header="Details", style="blue")

    for deployment in deployments:
        errored_deployment = next(
            (d for d in deployment_exceptions if d["deployment"] == deployment),
            None,
        )
        if errored_deployment:
            table.add_row(
                f"{deployment.flow_name}/{deployment.name}",
                "failed",
                str(errored_deployment["exc"]),
                style="red",
            )
        else:
            table.add_row(f"{deployment.flow_name}/{deployment.name}", "applied")
    console.print(table)

    if print_next_steps_message and not complete_failure:
        if not work_pool.is_push_pool:
            console.print(
                "\nTo execute flow runs from these deployments, start a worker in a"
                " separate terminal that pulls work from the"
                f" {work_pool_name!r} work pool:"
            )
            console.print(
                f"\n\t$ prefect worker start --pool {work_pool_name!r}",
                style="blue",
            )
        console.print(
            "\nTo trigger any of these deployments, use the"
            " following command:\n[blue]\n\t$ prefect deployment run"
            " [DEPLOYMENT_NAME]\n[/]"
        )

        if PREFECT_UI_URL:
            console.print(
                "\nYou can also trigger your deployments via the Prefect UI:"
                f" [blue]{PREFECT_UI_URL.value()}/deployments[/]\n"
            )

    return deployment_ids

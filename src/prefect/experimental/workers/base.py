import abc
from pathlib import Path
from typing import List, Optional, Type, Union
from uuid import uuid4

import anyio
import anyio.abc
import httpx
import pendulum
from pydantic import BaseModel, Field, ValidationError, validator

from prefect._internal.compatibility.experimental import experimental
from prefect.client.orion import OrionClient, get_client
from prefect.client.schemas import FlowRun
from prefect.deployments import Deployment
from prefect.engine import propose_state
from prefect.exceptions import Abort, ObjectNotFound
from prefect.logging.loggers import get_logger
from prefect.orion import schemas
from prefect.orion.schemas.actions import WorkPoolUpdate
from prefect.orion.schemas.responses import WorkerFlowRunResponse
from prefect.settings import (
    PREFECT_WORKER_PREFETCH_SECONDS,
    PREFECT_WORKER_WORKFLOW_STORAGE_PATH,
)
from prefect.states import Crashed, Pending, exception_to_failed_state
from prefect.utilities.dispatch import register_base_type


class BaseJobConfiguration(BaseModel):
    command: Optional[List[str]] = Field(template="{{ command }}")

    @validator("command")
    def validate_command(cls, v):
        """Make sure that empty strings are treated as None"""
        if not v:
            return None
        return v

    @staticmethod
    def _get_base_config_defaults(variables: dict) -> dict:
        """Get default values from base config for all variables that have them."""
        defaults = dict()
        for variable_name, attrs in variables.items():
            if "default" in attrs:
                defaults[variable_name] = attrs["default"]

        return defaults

    @classmethod
    def from_template_and_overrides(
        cls, base_job_template: dict, deployment_overrides: dict
    ):
        """Creates a valid worker configuration object from the provided base
        configuration and overrides.

        Important: this method expects that the base_job_template was already
        validated server-side.
        """
        job_config = base_job_template["job_configuration"]
        variables_schema = base_job_template["variables"]
        variables = cls._base_variables_from_variable_properties(
            variables_schema["properties"]
        )
        variables.update(deployment_overrides)

        populated_configuration = cls._apply_variables(job_config, variables)
        return cls(**populated_configuration)

    @classmethod
    def json_template(cls) -> dict:
        """Returns a dict with job configuration as keys and the corresponding templates as values

        Defaults to using the job configuration parameter name as the template variable name.

        e.g.
        {
            key1: '{{ key1 }}',     # default variable template
            key2: '{{ template2 }}', # `template2` specifically provide as template
        }
        """
        configuration = {}
        properties = cls.schema()["properties"]
        for k, v in properties.items():
            if v.get("template"):
                template = v["template"]
            else:
                template = "{{ " + k + " }}"
            configuration[k] = template

        return configuration

    @staticmethod
    def _apply_variables(job_config, variables):
        """Apply variables to configuration template."""
        job_config.update(variables)
        return job_config

    @classmethod
    def _base_variables_from_variable_properties(cls, variable_properties):
        """Get base template variables."""
        default_variables = cls._get_base_config_defaults(variable_properties)
        variables = {key: None for key in variable_properties.keys()}
        variables.update(default_variables)
        return variables


class BaseVariables(BaseModel):
    command: Optional[List[str]] = None


class BaseWorkerResult(BaseModel, abc.ABC):
    identifier: str
    status_code: int

    def __bool__(self):
        return self.status_code == 0


@register_base_type
class BaseWorker(abc.ABC):
    type: str
    job_configuration: Type[BaseJobConfiguration]
    job_configuration_variables: Optional[Type[BaseVariables]] = None

    @experimental(feature="The workers feature", group="workers")
    def __init__(
        self,
        work_pool_name: str,
        name: Optional[str] = None,
        prefetch_seconds: Optional[float] = None,
        workflow_storage_path: Optional[Path] = None,
        create_pool_if_not_found: bool = True,
        limit: Optional[int] = None,
    ):
        """
        Base class for all Prefect workers.

        Args:
            name: The name of the worker. If not provided, a random one
                will be generated. If provided, it cannot contain '/' or '%'.
                The name is used to identify the worker in the UI; if two
                processes have the same name, they will be treated as the same
                worker.
            work_pool_name: The name of the work pool to use. If not
                provided, the default will be used.
            prefetch_seconds: The number of seconds to prefetch flow runs for.
            workflow_storage_path: The filesystem path to workflow storage for
                this worker.
            create_pool_if_not_found: Whether to create the work pool
                if it is not found. Defaults to `True`, but can be set to `False` to
                ensure that work pools are not created accidentally.
            limit: The maximum number of flow runs this worker should be running at
                a given time.
        """
        if name and ("/" in name or "%" in name):
            raise ValueError("Worker name cannot contain '/' or '%'")
        self.name = name or f"{self.__class__.__name__} {uuid4()}"
        self._logger = get_logger(f"worker.{self.__class__.type}.{self.name.lower()}")

        self.is_setup = False
        self._create_pool_if_not_found = create_pool_if_not_found
        self._work_pool_name = work_pool_name

        self._prefetch_seconds: float = (
            prefetch_seconds or PREFECT_WORKER_PREFETCH_SECONDS.value()
        )
        self._workflow_storage_path: Path = (
            workflow_storage_path or PREFECT_WORKER_WORKFLOW_STORAGE_PATH.value()
        )

        self._work_pool: Optional[schemas.core.WorkPool] = None
        self._runs_task_group: Optional[anyio.abc.TaskGroup] = None
        self._client: Optional[OrionClient] = None
        self._limit = limit
        self._limiter: Optional[anyio.CapacityLimiter] = None
        self._submitting_flow_run_ids = set()

    @abc.abstractmethod
    async def run(
        self,
        flow_run: FlowRun,
        configuration: BaseJobConfiguration,
        task_status: Optional[anyio.abc.TaskStatus] = None,
    ) -> BaseWorkerResult:
        """
        Runs a given flow run on the current worker.
        """
        raise NotImplementedError(
            "Workers must implement a method for running submitted flow runs"
        )

    @abc.abstractmethod
    async def verify_submitted_deployment(self, deployment: Deployment):
        """
        Checks that scheduled flow runs for a submitted deployment can be run by the
        current worker.

        Should be implemented by `BaseWorker` implementations. Implementation of this
        method should raise if any of the checks performed by the worker fail. If all
        checks pass, then this method does not need to return anything.
        """
        raise NotImplementedError(
            "Workers must implement a method for verifying submitted deployments"
        )

    @classmethod
    def __dispatch_key__(cls):
        if cls.__name__ == "BaseWorker":
            return None  # The base class is abstract
        return cls.type

    async def setup(self):
        """Prepares the worker to run."""
        self._logger.debug("Setting up worker...")
        self._runs_task_group = anyio.create_task_group()
        self._limiter = (
            anyio.CapacityLimiter(self._limit) if self._limit is not None else None
        )
        self._client = get_client()
        await self._client.__aenter__()
        await self._runs_task_group.__aenter__()
        # Setup workflows directory
        self._workflow_storage_path.mkdir(parents=True, exist_ok=True)

        self.is_setup = True

    async def teardown(self, *exc_info):
        """Cleans up resources after the worker is stopped."""
        self._logger.debug("Tearing down worker...")
        self.is_setup = False
        if self._runs_task_group:
            await self._runs_task_group.__aexit__(*exc_info)
        if self._client:
            await self._client.__aexit__(*exc_info)
        self._runs_task_group = None
        self._client = None

    async def get_and_submit_flow_runs(self):
        runs_response = await self._get_scheduled_flow_runs()
        return await self._submit_scheduled_flow_runs(flow_run_response=runs_response)

    async def _update_local_work_pool_info(self):
        try:
            work_pool = await self._client.read_work_pool(
                work_pool_name=self._work_pool_name
            )
        except ObjectNotFound:
            if self._create_pool_if_not_found:
                work_pool = await self._client.create_work_pool(
                    work_pool=schemas.actions.WorkPoolCreate(
                        name=self._work_pool_name, type=self.type
                    )
                )
                self._logger.info(f"Worker pool {self._work_pool_name!r} created.")
            else:
                self._logger.warning(f"Worker pool {self._work_pool_name!r} not found!")
                return

        # if the remote config type changes (or if it's being loaded for the
        # first time), check if it matches the local type and warn if not
        if getattr(self._work_pool, "type", 0) != work_pool.type:
            if work_pool.type != self.__class__.type:
                self._logger.warning(
                    f"Worker type mismatch! This worker process expects type "
                    f"{self.type!r} but received {work_pool.type!r}"
                    " from the server. Unexpected behavior may occur."
                )

        # once the work pool is loaded, verify that it has a `base_job_template` and
        # set it if not
        if not work_pool.base_job_template:
            job_template = self._create_job_template()
            await self._set_work_pool_template(work_pool, job_template)
            work_pool.base_job_template = job_template

        self._work_pool = work_pool

    async def _send_worker_heartbeat(self):
        if self._work_pool:
            await self._client.send_worker_heartbeat(
                work_pool_name=self._work_pool_name, worker_name=self.name
            )

    async def sync_with_backend(self):
        """
        Updates the worker's local information about it's current work pool and
        queues. Sends a worker heartbeat to the API.
        """
        await self._update_local_work_pool_info()

        await self._send_worker_heartbeat()

        self._logger.debug("Worker synchronized with Orion server.")

    async def scan_storage_for_deployments(self):
        """
        Performs a scan of the worker's configured workflow storage location. If any
        .yaml files are found in the workflow storage location, the worker will attempt
        to apply the deployments defined in the discovered manifests.
        """
        self._logger.debug("Scanning %s for deployments", self._workflow_storage_path)
        possible_deployment_files = self._workflow_storage_path.glob("*.yaml")
        for possible_deployment_file in possible_deployment_files:
            if possible_deployment_file.is_file:
                await self._attempt_to_apply_deployment(possible_deployment_file)

    async def _attempt_to_apply_deployment(self, deployment_manifest_path: Path):
        """
        Attempts to apply a deployment from a discovered .yaml file. Will not apply
        if validation fails when loading the deployment from the discovered .yaml file.
        """
        try:
            deployment = await Deployment.load_from_yaml(str(deployment_manifest_path))
            # Update path to match worker's file system instead of submitters so that
            # deployment will run successfully when scheduled
            # TODO: Revisit once deployment experience is created
            deployment.path = str(deployment_manifest_path.parent)

            await self.verify_submitted_deployment(deployment)
            try:
                api_deployment = await self._client.read_deployment_by_name(
                    f"{deployment.flow_name}/{deployment.name}"
                )
                updated = api_deployment.updated
            except ObjectNotFound:
                updated = None
            if updated is None:
                await deployment.apply()
                self._logger.info(
                    "Created new deployment %s/%s",
                    deployment.flow_name,
                    deployment.name,
                )
            elif deployment.timestamp > updated:
                await deployment.apply()
                self._logger.info(
                    "Applied update to deployment %s/%s",
                    deployment.flow_name,
                    deployment.name,
                )
        except ValidationError:
            self._logger.exception(
                "Validation of deployment manifest %s failed.",
                deployment_manifest_path,
            )
        except httpx.HTTPStatusError as exc:
            self._logger.exception(
                "Failed to apply deployment %s/%s: %s",
                deployment.flow_name,
                deployment.name,
                exc.response.json().get("detail"),
            )
        except Exception as exc:
            self._logger.exception(
                "Unexpected error occurred while attempting to register discovered deployment."
            )

    async def _get_scheduled_flow_runs(
        self,
    ) -> List[schemas.responses.WorkerFlowRunResponse]:
        """
        Retrieve scheduled flow runs from the work pool's queues.
        """
        scheduled_before = pendulum.now("utc").add(seconds=int(self._prefetch_seconds))
        self._logger.debug(
            f"Querying for flow runs scheduled before {scheduled_before}"
        )
        try:
            scheduled_flow_runs = (
                await self._client.get_scheduled_flow_runs_for_work_pool_queues(
                    work_pool_name=self._work_pool_name,
                    scheduled_before=scheduled_before,
                )
            )
            self._logger.debug(
                f"Discovered {len(scheduled_flow_runs)} scheduled_flow_runs"
            )
            return scheduled_flow_runs
        except ObjectNotFound:
            # the pool doesn't exist; it will be created on the next
            # heartbeat (or an appropriate warning will be logged)
            return []

    async def _submit_scheduled_flow_runs(
        self, flow_run_response: List[WorkerFlowRunResponse]
    ) -> List[FlowRun]:
        """
        Takes a list of WorkerFlowRunResponses and submits the referenced flow runs
        for execution by the worker.
        """
        submittable_flow_runs = [entry.flow_run for entry in flow_run_response]
        submittable_flow_runs.sort(key=lambda run: run.next_scheduled_start_time)
        for flow_run in submittable_flow_runs:
            if flow_run.id in self._submitting_flow_run_ids:
                continue

            try:
                if self._limiter:
                    self._limiter.acquire_on_behalf_of_nowait(flow_run.id)
            except anyio.WouldBlock:
                self._logger.info(
                    f"Flow run limit reached; {self._limiter.borrowed_tokens} flow runs in progress."
                )
                break
            else:
                self._logger.info(f"Submitting flow run '{flow_run.id}'")
                self._submitting_flow_run_ids.add(flow_run.id)
                self._runs_task_group.start_soon(
                    self._submit_run,
                    flow_run,
                )

        return list(
            filter(
                lambda run: run.id in self._submitting_flow_run_ids,
                submittable_flow_runs,
            )
        )

    async def _submit_run(self, flow_run: FlowRun) -> None:
        """
        Submits a given flow run for execution by the worker.
        """
        ready_to_submit = await self._propose_pending_state(flow_run)

        if ready_to_submit:
            readiness_result = await self._runs_task_group.start(
                self._submit_run_and_capture_errors, flow_run
            )

            if readiness_result and not isinstance(readiness_result, Exception):
                try:
                    await self._client.update_flow_run(
                        flow_run_id=flow_run.id,
                        infrastructure_pid=str(readiness_result),
                    )
                except Exception:
                    self._logger.exception(
                        "An error occurred while setting the `infrastructure_pid` on "
                        f"flow run {flow_run.id!r}. The flow run will "
                        "not be cancellable."
                    )

            self._logger.info(f"Completed submission of flow run '{flow_run.id}'")

        else:
            # If the run is not ready to submit, release the concurrency slot
            if self._limiter:
                self._limiter.release_on_behalf_of(flow_run.id)

        self._submitting_flow_run_ids.remove(flow_run.id)

    async def _submit_run_and_capture_errors(
        self, flow_run: FlowRun, task_status: anyio.abc.TaskStatus = None
    ) -> Union[BaseWorkerResult, Exception]:
        try:
            # TODO: Add functionality to handle base job configuration and
            # job configuration variables when kicking off a flow run
            result = await self.run(
                flow_run=flow_run,
                task_status=task_status,
                configuration=await self._get_configuration(flow_run),
            )
        except Exception as exc:
            if not task_status._future.done():
                # This flow run was being submitted and did not start successfully
                self._logger.exception(
                    f"Failed to submit flow run '{flow_run.id}' to infrastructure."
                )
                # Mark the task as started to prevent agent crash
                task_status.started(exc)
                await self._propose_failed_state(flow_run, exc)
            else:
                self._logger.exception(
                    f"An error occurred while monitoring flow run '{flow_run.id}'. "
                    "The flow run will not be marked as failed, but an issue may have "
                    "occurred."
                )
            return exc
        finally:
            if self._limiter:
                self._limiter.release_on_behalf_of(flow_run.id)

        if not task_status._future.done():
            self._logger.error(
                f"Infrastructure returned without reporting flow run '{flow_run.id}' "
                "as started or raising an error. This behavior is not expected and "
                "generally indicates improper implementation of infrastructure. The "
                "flow run will not be marked as failed, but an issue may have occurred."
            )
            # Mark the task as started to prevent agent crash
            task_status.started()

        if result.status_code != 0:
            await self._propose_crashed_state(
                flow_run,
                f"Flow run infrastructure exited with non-zero status code {result.status_code}.",
            )

        return result

    def get_status(self):
        """
        Retrieves the status of the current worker including its name, current worker
        pool, the work pool queues it is polling, and its local settings.
        """
        return {
            "name": self.name,
            "work_pool": self._work_pool.dict(json_compatible=True)
            if self._work_pool is not None
            else None,
            "settings": {
                "prefetch_seconds": self._prefetch_seconds,
                "workflow_storage_path": self._workflow_storage_path,
            },
        }

    async def _get_configuration(self, flow_run: FlowRun) -> BaseJobConfiguration:
        deployment = await self._client.read_deployment(flow_run.deployment_id)
        configuration = self.job_configuration.from_template_and_overrides(
            base_job_template=self._work_pool.base_job_template,
            deployment_overrides=deployment.infra_overrides,
        )
        return configuration

    async def _propose_pending_state(self, flow_run: FlowRun) -> bool:
        state = flow_run.state
        try:
            state = await propose_state(
                self._client, Pending(), flow_run_id=flow_run.id
            )
        except Abort as exc:
            self._logger.info(
                f"Aborted submission of flow run '{flow_run.id}'. "
                f"Server sent an abort signal: {exc}",
            )
            return False
        except Exception:
            self._logger.exception(
                f"Failed to update state of flow run '{flow_run.id}'",
            )
            return False

        if not state.is_pending():
            self._logger.info(
                f"Aborted submission of flow run '{flow_run.id}': "
                f"Server returned a non-pending state {state.type.value!r}",
            )
            return False

        return True

    async def _propose_failed_state(self, flow_run: FlowRun, exc: Exception) -> None:
        try:
            await propose_state(
                self._client,
                await exception_to_failed_state(message="Submission failed.", exc=exc),
                flow_run_id=flow_run.id,
            )
        except Abort:
            # We've already failed, no need to note the abort but we don't want it to
            # raise in the agent process
            pass
        except Exception:
            self._logger.error(
                f"Failed to update state of flow run '{flow_run.id}'",
                exc_info=True,
            )

    async def _propose_crashed_state(self, flow_run: FlowRun, message: str) -> None:
        try:
            state = await propose_state(
                self._client,
                Crashed(message=message),
                flow_run_id=flow_run.id,
            )
        except Abort:
            # Flow run already marked as failed
            pass
        except Exception:
            self._logger.exception(
                f"Failed to update state of flow run '{flow_run.id}'"
            )
        else:
            if state.is_crashed():
                self._logger.info(
                    f"Reported flow run '{flow_run.id}' as crashed: {message}"
                )

    async def _set_work_pool_template(self, work_pool, job_template):
        """Updates the `base_job_template` for the worker's workerpool server side."""
        await self._client.update_work_pool(
            work_pool_name=work_pool.name,
            work_pool=WorkPoolUpdate(
                base_job_template=job_template,
            ),
        )

    def _create_job_template(self) -> dict:
        """Create a job template from a worker's configuration components."""
        if self.job_configuration_variables is None:
            schema = self.job_configuration.schema()
            # remove "template" key from all dicts in schema['properties'] because it is not a
            # relevant field
            for key, value in schema["properties"].items():
                if isinstance(value, dict):
                    schema["properties"][key].pop("template", None)
            variables = schema
        else:
            variables = self.job_configuration_variables.schema()
        return {
            "job_configuration": self.job_configuration.json_template(),
            "variables": {
                "properties": variables["properties"],
                "required": variables.get("required", []),
            },
        }

    async def __aenter__(self):
        self._logger.debug("Entering worker context...")
        await self.setup()
        return self

    async def __aexit__(self, *exc_info):
        self._logger.debug("Exiting worker context...")
        await self.teardown(*exc_info)

    def __repr__(self):
        return f"Worker(pool={self._work_pool_name!r}, name={self.name!r})"

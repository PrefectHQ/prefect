import abc
import shutil
from functools import partial
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4
from zipfile import ZipFile

import anyio
import anyio.abc
import jinja2
import pendulum
import yaml
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile, status
from pydantic import BaseModel, ValidationError

from prefect._internal.compatibility.experimental import experimental
from prefect.client.orion import OrionClient, get_client
from prefect.client.schemas import FlowRun
from prefect.deployments import Deployment
from prefect.engine import propose_state
from prefect.exceptions import Abort, ObjectNotFound
from prefect.orion import schemas
from prefect.orion.schemas.responses import WorkerFlowRunResponse
from prefect.orion.services.loop_service import LoopService
from prefect.settings import (
    PREFECT_WORKER_HEARTBEAT_SECONDS,
    PREFECT_WORKER_PREFETCH_SECONDS,
    PREFECT_WORKER_QUERY_SECONDS,
    PREFECT_WORKER_WORKFLOW_STORAGE_PATH,
    PREFECT_WORKER_WORKFLOW_STORAGE_SCAN_SECONDS,
)
from prefect.states import Crashed, Pending, exception_to_failed_state
from prefect.utilities.dispatch import register_base_type
from prefect.utilities.services import critical_service_loop


class BaseWorkerResult(BaseModel, abc.ABC):
    identifier: str
    status_code: int

    def __bool__(self):
        return self.status_code == 0


class BaseJobConfiguration(BaseModel):
    command: Optional[List[str]] = None

    @staticmethod
    def _get_base_config_defaults(variables: dict) -> dict:
        """Get default values from base config for all variables that have them."""
        defaults = dict()
        for variable_name, attrs in variables.items():
            if "default" in attrs:
                defaults[variable_name] = attrs["default"]

        return defaults

    @staticmethod
    def _jinja_template(job_config: dict) -> jinja2.Template:
        """Create jinja template for job configuration."""
        job_config_str = str(job_config)
        template = jinja2.Environment().from_string(job_config_str)
        return template

    @classmethod
    def from_configurations(cls, base_job_template: dict, deployment_overrides: dict):
        """Creates a valid worker configuration object from the provided base
        configuration and overrides.
        """
        job_config = base_job_template["job_configuration"]
        variables_schema = base_job_template["variables"]

        variables = cls._get_base_config_defaults(variables_schema)
        variables.update(deployment_overrides)

        job_config_template = cls._jinja_template(job_config)

        populated_configuration_str = job_config_template.render(**variables)
        populated_configuration = yaml.safe_load(populated_configuration_str)

        return cls(**populated_configuration)

    @classmethod
    def json_template(cls):
        configuration = {}
        properties = cls.schema()["properties"]
        for k, v in properties.items():
            if v.get("template"):
                template = v["template"]
            else:
                template = "{{ " + k + " }}"
            configuration[k] = template

        return configuration


class BaseVariables(BaseModel):
    command: Optional[List[str]] = None


@register_base_type
class BaseWorker(LoopService, abc.ABC):
    type: str
    loop_seconds = PREFECT_WORKER_QUERY_SECONDS.value()
    prefetch_seconds = PREFECT_WORKER_PREFETCH_SECONDS.value()
    heartbeat_seconds = PREFECT_WORKER_HEARTBEAT_SECONDS.value()
    workflow_storage_scan_seconds = PREFECT_WORKER_WORKFLOW_STORAGE_SCAN_SECONDS.value()
    workflow_storage_path = PREFECT_WORKER_WORKFLOW_STORAGE_PATH.value()
    default_pool_name = "Default Pool"
    job_configuration: Optional[BaseJobConfiguration] = None
    job_configuration_variables: Optional[BaseVariables] = None

    @experimental(feature="The workers feature", group="workers")
    def __init__(
        self,
        name: str,
        worker_pool_name: str,
        loop_seconds: Optional[float] = None,
        prefetch_seconds: Optional[float] = None,
        heartbeat_seconds: Optional[float] = None,
        workflow_storage_scan_seconds: Optional[float] = None,
        workflow_storage_path: Optional[Path] = None,
        create_pool_if_not_found: bool = True,
        limit: Optional[int] = None,
    ):
        """
        Base worker class for all Prefect workers.

        Args:
            worker_pool_name: The name of the worker pool to use. If not
                provided, the default will be used.
            name: The name of the worker. If not provided, a random one
                will be generated. If provided, it cannot contain '/' or '%'.
                The name is used to identify the worker in the UI; if two
                processes have the same name, they will be treated as the same
                worker.
            loop_seconds: The number of seconds to wait between each loop
                of the worker.
            prefetch_seconds: The number of seconds to prefetch flow runs for.
            heartbeat_seconds: The number of seconds between each heartbeat.
            workflow_storage_scan_seconds: The number of seconds between each
                workflow storage scan for deployments.
            workflow_storage_path: The filesystem path to workflow storage for
                this worker.
            create_pool_if_not_found: Whether to create the worker pool
                if it is not found. Defaults to `True`, but can be set to `False` to
                ensure that worker pools are not created accidentally.
        """
        if name and ("/" in name or "%" in name):
            raise ValueError("Worker name cannot contain '/' or '%'")
        name = name or f"{self.__class__.__name__} {uuid4()}"

        super().__init__(loop_seconds=loop_seconds or self.__class__.loop_seconds)

        self.is_setup = False
        self.create_pool_if_not_found = create_pool_if_not_found
        self.worker_pool_name = worker_pool_name or self.default_pool_name

        self.heartbeat_seconds = heartbeat_seconds or self.__class__.heartbeat_seconds
        self.prefetch_seconds = prefetch_seconds or self.__class__.prefetch_seconds
        self.storage_scan_seconds = (
            workflow_storage_scan_seconds
            or self.__class__.workflow_storage_scan_seconds
        )
        self.workflow_storage_path = (
            workflow_storage_path or self.__class__.workflow_storage_path
        )
        # Setup workflows directory
        self.workflow_storage_path.mkdir(parents=True, exist_ok=True)

        if self.prefetch_seconds < self.loop_seconds:
            self.logger.warning(
                "Prefetch seconds is less than loop seconds, "
                "which could lead to unexpected delays scheduling flow runs."
            )

        self.worker_pool: Optional[schemas.core.WorkerPool] = None
        self.worker_pool_queues: List[schemas.core.WorkerPoolQueue] = []
        self._runs_task_group: Optional[anyio.abc.TaskGroup] = None
        self._loop_task_group: Optional[anyio.abc.TaskGroup] = None
        self._client: Optional[OrionClient] = None
        self.limit = limit
        self._limiter: Optional[anyio.CapacityLimiter] = None
        self._submitting_flow_run_ids = set()

    @abc.abstractmethod
    async def run(
        self, flow_run: FlowRun, task_status: Optional[anyio.abc.TaskStatus] = None
    ):
        raise NotImplementedError("Workers must implement a run command")

    @classmethod
    @abc.abstractmethod
    async def verify_submitted_deployment(cls, deployment: Deployment):
        raise NotImplementedError(
            "Workers must implement a method for verifying submitted deployments"
        )

    @classmethod
    def __dispatch_key__(cls):
        if cls.__name__ == "BaseWorker":
            return None  # The base class is abstract
        return cls.type

    async def setup(self):
        self.logger.debug("Setting up worker...")
        self._runs_task_group = anyio.create_task_group()
        self._loop_task_group = anyio.create_task_group()
        self.limiter = (
            anyio.CapacityLimiter(self.limit) if self.limit is not None else None
        )
        self._client = get_client()
        await self._client.__aenter__()
        await self._loop_task_group.__aenter__()
        await self._runs_task_group.__aenter__()
        self.is_setup = True

    async def teardown(self, *exc_info):
        self.logger.debug("Tearing down worker...")
        self.is_setup = False
        if self._runs_task_group:
            self._runs_task_group.cancel_scope.cancel()
            await self._runs_task_group.__aexit__(*exc_info)
        if self._loop_task_group:
            self._loop_task_group.cancel_scope.cancel()
            await self._loop_task_group.__aexit__(*exc_info)
        if self._client:
            await self._client.__aexit__(*exc_info)
        self._runs_task_group = None
        self._client = None

    async def _set_worker_pool_template(self, worker_pool, job_template):
        await self._client.update_worker_pool(
            worker_pool=worker_pool, base_job_template=job_template
        )

    async def _on_start(self):
        """
        Start the heartbeat loop when the worker starts
        """
        if not self.is_setup or not self._loop_task_group:
            raise RuntimeError(
                f"Worker has not been setup. Use `async with {self.__class__.__name__}()...`"
            )
        await super()._on_start()
        # wait for an initial heartbeat to configure the worker
        await self.heartbeat_worker()
        # perform initial scan of storage

        await self.scan_storage_for_deployments()
        # schedule the heartbeat loop to run every `heartbeat_seconds`
        self._loop_task_group.start_soon(
            partial(
                critical_service_loop,
                workload=self.heartbeat_worker,
                interval=self.heartbeat_seconds,
                printer=self.logger.debug,
            )
        )
        # schedule the storage scan loop to run
        self._loop_task_group.start_soon(
            partial(
                critical_service_loop,
                workload=self.scan_storage_for_deployments,
                interval=self.storage_scan_seconds,
                printer=self.logger.debug,
            )
        )

    async def _on_stop(self) -> None:
        await super()._on_stop()

    def __repr__(self):
        return f"Worker(pool={self.worker_pool_name!r}, name={self.name!r})"

    async def run_once(self):
        # if the pool is paused or has a 0 concurrency limit, don't bother polling
        if self.worker_pool and (
            self.worker_pool.is_paused or self.worker_pool.concurrency_limit == 0
        ):
            return

        runs_response = await self.get_scheduled_flow_runs()
        await self._submit_scheduled_flow_runs(flow_run_response=runs_response)

    async def heartbeat_worker(self):
        """
        Refreshes the worker's config and queues, and sends a heartbeat to the server.
        """

        # ----------------------------------------------
        # refresh config
        # ----------------------------------------------

        try:
            worker_pool = await self._client.read_worker_pool(
                worker_pool_name=self.worker_pool_name
            )
        except ObjectNotFound:
            if self.create_pool_if_not_found:
                worker_pool = await self._client.create_worker_pool(
                    worker_pool=schemas.actions.WorkerPoolCreate(
                        name=self.worker_pool_name, type=self.type
                    )
                )
                self.logger.info(f"Worker pool {self.worker_pool_name!r} created.")
            else:
                self.logger.warning(f"Worker pool {self.worker_pool_name!r} not found!")
                return

        # if the remote config type changes (or if it's being loaded for the
        # first time), check if it matches the local type and warn if not
        if getattr(self.worker_pool, "type", 0) != worker_pool.type:
            if worker_pool.type != self.__class__.type:
                self.logger.warning(
                    f"Worker type mismatch! This worker process expects type "
                    f"{self.type!r} but received {worker_pool.type!r}"
                    " from the server. Unexpected behavior may occur."
                )

        if not worker_pool.base_job_template:
            job_template = self._create_job_template()
            await self._set_worker_pool_template(worker_pool, job_template)
            worker_pool.base_job_template = job_template

        self.worker_pool = worker_pool

        # ----------------------------------------------
        # refresh queues
        # ----------------------------------------------
        worker_pool_queues = await self._client.read_worker_pool_queues(
            worker_pool_name=self.worker_pool_name
        )
        for new_queue in set(q.name for q in worker_pool_queues).difference(
            q.name for q in self.worker_pool_queues
        ):
            self.logger.info(f"Found new queue {new_queue!r}")

        self.worker_pool_queues = worker_pool_queues

        # ----------------------------------------------
        # heartbeat
        # ----------------------------------------------
        await self._client.send_worker_heartbeat(
            worker_pool_name=self.worker_pool_name, worker_name=self.name
        )
        self.logger.debug(f"{self} refreshed")

    async def _run_heartbeat_loop(self):
        """
        Utility function to run the heartbeat loop forever
        """
        while self._is_running:
            await anyio.sleep(self.heartbeat_seconds)
            await self.heartbeat_worker()

    async def _run_storage_scan_loop(self):
        while self._is_running:
            await anyio.sleep(self.storage_scan_seconds)
            await self.scan_storage_for_deployments()

    async def scan_storage_for_deployments(self):
        self.logger.debug("Scanning %s for deployments", self.workflow_storage_path)
        possible_deployment_files = self.workflow_storage_path.glob("*.yaml")
        for possible_deployment_file in possible_deployment_files:
            if possible_deployment_file.is_file:
                await self._attempt_to_register_deployment(possible_deployment_file)

    async def _attempt_to_register_deployment(self, deployment_manifest_path: Path):
        try:
            deployment = await Deployment.load_from_yaml(str(deployment_manifest_path))
            # Update path to match worker's file system instead of submitters
            deployment.path = str(deployment_manifest_path.parent)

            await self.verify_submitted_deployment(deployment)

            updated = None
            async with get_client() as client:
                try:
                    api_deployment = await client.read_deployment_by_name(
                        f"{deployment.flow_name}/{deployment.name}"
                    )
                    updated = api_deployment.updated
                except ObjectNotFound:
                    pass
            if updated is None:
                await deployment.apply()
                self.logger.info(
                    "Created new deployment %s/%s",
                    deployment.flow_name,
                    deployment.name,
                )
            elif deployment.timestamp > updated:
                await deployment.apply()
                self.logger.info(
                    "Applied update to deployment %s/%s",
                    deployment.flow_name,
                    deployment.name,
                )
        except ValidationError:
            self.logger.exception(
                "Validation of deployment manifest %s failed.",
                deployment_manifest_path,
            )
        except Exception:
            self.logger.exception(
                "Unexpected error occurred while attempting to register discovered deployment."
            )

    def _unzip_deployments(self, data: UploadFile):
        self.logger.info(
            "Unzipping deployments in %s to %s",
            data.filename,
            self.workflow_storage_path,
        )
        # UploadFile.file claims to be a BinaryIO, but doesn't implement seekable
        data.file.seekable = lambda: False
        ZipFile(data.file).extractall(self.workflow_storage_path)

    async def get_scheduled_flow_runs(
        self,
    ) -> List[schemas.responses.WorkerFlowRunResponse]:
        """
        Retrieve scheduled flow runs from the worker pool's queues.
        """
        async with get_client() as client:
            scheduled_before = pendulum.now("utc").add(
                seconds=int(self.prefetch_seconds)
            )
            try:
                return await client.get_scheduled_flow_runs_for_worker(
                    worker_pool_name=self.worker_pool_name,
                    worker_pool_queue_names=[q.name for q in self.worker_pool_queues],
                    scheduled_before=scheduled_before,
                )
            except ObjectNotFound:
                # the pool doesn't exist; it will be created on the next
                # heartbeat (or an appropriate warning will be logged)
                return []

    async def _submit_scheduled_flow_runs(
        self, flow_run_response: List[WorkerFlowRunResponse]
    ):
        for entry in flow_run_response:
            try:
                if self.limiter:
                    self.limiter.acquire_on_behalf_of_nowait(entry.flow_run.id)
            except anyio.WouldBlock:
                self.logger.info(
                    f"Flow run limit reached; {self.limiter.borrowed_tokens} flow runs in progress."
                )
                break
            else:
                self.logger.info(f"Submitting flow run '{entry.flow_run.id}'")
                self._submitting_flow_run_ids.add(entry.flow_run.id)
                self._runs_task_group.start_soon(
                    self._submit_run,
                    entry.flow_run,
                )

    async def _submit_run(self, flow_run: FlowRun) -> None:
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
                    self.logger.exception(
                        "An error occured while setting the `infrastructure_pid` on "
                        f"flow run {flow_run.id!r}. The flow run will not be cancellable."
                    )

            self.logger.info(f"Completed submission of flow run '{flow_run.id}'")

    def _create_job_template(self) -> dict:
        if self.job_configuration_variables is None:
            variables = self.job_configuration.schema()
        else:
            variables = self.job_configuration_variables.schema()
        return {
            "job_configuration": self.job_configuration.json_template(),
            "variables": variables["properties"],
            "required": variables["required"],
        }

    async def _submit_run_and_capture_errors(
        self, flow_run: FlowRun, task_status: anyio.abc.TaskStatus = None
    ):
        try:
            result = await self.run(flow_run=flow_run, task_status=task_status)
        except Exception as exc:
            if not task_status._future.done():
                # This flow run was being submitted and did not start successfully
                self.logger.exception(
                    f"Failed to submit flow run '{flow_run.id}' to infrastructure."
                )
                # Mark the task as started to prevent agent crash
                task_status.started(exc)
                await self._propose_failed_state(flow_run, exc)
            else:
                self.logger.exception(
                    f"An error occured while monitoring flow run '{flow_run.id}'. "
                    "The flow run will not be marked as failed, but an issue may have "
                    "occurred."
                )
            return exc
        finally:
            if self.limiter:
                self.limiter.release_on_behalf_of(flow_run.id)

        if not task_status._future.done():
            self.logger.error(
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
        return {
            "name": self.name,
            "worker_pool": self.worker_pool.dict(json_compatible=True)
            if self.worker_pool is not None
            else None,
            "worker_pool_queues": [
                worker_pool_queue.dict(json_compatible=True)
                for worker_pool_queue in self.worker_pool_queues
            ],
            "settings": {
                "loop_seconds": self.loop_seconds,
                "prefetch_seconds": self.prefetch_seconds,
                "heartbeat_seconds": self.heartbeat_seconds,
                "storage_scan_seconds": self.storage_scan_seconds,
                "workflow_storage_path": self.workflow_storage_path,
            },
        }

    async def _propose_pending_state(self, flow_run: FlowRun) -> bool:
        state = flow_run.state
        try:
            state = await propose_state(
                self._client, Pending(), flow_run_id=flow_run.id
            )
        except Abort as exc:
            self.logger.info(
                f"Aborted submission of flow run '{flow_run.id}'. "
                f"Server sent an abort signal: {exc}",
            )
            return False
        except Exception:
            self.logger.exception(
                f"Failed to update state of flow run '{flow_run.id}'",
            )
            return False

        if not state.is_pending():
            self.logger.info(
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
            self.logger.error(
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
            self.logger.exception(f"Failed to update state of flow run '{flow_run.id}'")
        else:
            if state.is_crashed():
                self.logger.info(
                    f"Reported flow run '{flow_run.id}' as crashed: {message}"
                )

    def create_app(self) -> FastAPI:

        app = FastAPI()

        @app.on_event("startup")
        async def start_worker():
            self.logger.debug("Triggering startup action...")
            if not self.is_setup or not self._loop_task_group:
                raise RuntimeError(
                    "Worker has not been setup. "
                    f"Use `async with {self.__class__.__name__}()...`"
                )
            self._loop_task_group.start_soon(self.start)

        @app.on_event("shutdown")
        async def stop_worker():
            if not self.is_setup or not self._loop_task_group:
                raise RuntimeError(
                    "Worker has not been setup. "
                    f"Use `async with {self.__class__.__name__}()...`"
                )
            self._loop_task_group.start_soon(self.stop)

        @app.get("/health")
        async def health() -> bool:
            return True

        @app.get("/status")
        async def get_status() -> Dict:
            return self.get_status()

        @app.post("/submit_deployments", status_code=status.HTTP_202_ACCEPTED)
        async def accept_deployment_zip(
            background_tasks: BackgroundTasks, zip_file: UploadFile = File(...)
        ):
            try:
                background_tasks.add_task(self._unzip_deployments, zip_file)
                return {"message": "Successfully received submitted deployments"}
            except shutil.ReadError:
                raise HTTPException(
                    status_code=400, detail="Please upload deployments as a zip file."
                )
            except Exception:
                self.logger.exception(
                    "Failed to receive and unzip submitted deployments."
                )
                raise HTTPException(
                    status_code=500, detail="Failed to receive submitted deployments."
                )

        return app

    async def __aenter__(self):
        self.logger.debug("Entering worker context...")
        await self.setup()
        return self

    async def __aexit__(self, *exc_info):
        self.logger.debug("Exiting worker context...")
        await self.teardown(*exc_info)

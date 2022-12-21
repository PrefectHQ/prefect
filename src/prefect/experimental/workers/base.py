import abc
import asyncio
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

import pendulum
from fastapi import FastAPI, File, UploadFile
from pydantic import ValidationError

from prefect.client.orion import get_client
from prefect.deployments import Deployment
from prefect.exceptions import ObjectNotFound
from prefect.orion import schemas
from prefect.orion.services.loop_service import LoopService
from prefect.settings import (
    PREFECT_WORKER_HEARTBEAT_SECONDS,
    PREFECT_WORKER_PREFETCH_SECONDS,
    PREFECT_WORKER_QUERY_SECONDS,
    PREFECT_WORKER_WORKFLOW_STORAGE_PATH,
    PREFECT_WORKER_WORKFLOW_STORAGE_SCAN_SECONDS,
)
from prefect.utilities.dispatch import register_base_type


@register_base_type
class BaseWorker(LoopService, abc.ABC):
    type: str
    loop_seconds = PREFECT_WORKER_QUERY_SECONDS.value()
    prefetch_seconds = PREFECT_WORKER_PREFETCH_SECONDS.value()
    heartbeat_seconds = PREFECT_WORKER_HEARTBEAT_SECONDS.value()
    workflow_storage_scan_seconds = PREFECT_WORKER_WORKFLOW_STORAGE_SCAN_SECONDS.value()
    workflow_storage_path = PREFECT_WORKER_WORKFLOW_STORAGE_PATH.value()
    default_pool_name = "Default Pool"

    @abc.abstractmethod
    async def submit_scheduled_flow_runs(
        self, flow_run_response: List[schemas.responses.WorkerFlowRunResponse]
    ):
        """
        Submit scheduled flow runs for execution.

        This method should be implemented by subclasses.
        """
        raise NotImplementedError(
            "Workers must implement logic for submitting scheduled flow runs."
        )

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
    ):
        """
        Base worker class for all Prefect workers.

        Args:
            worker_pool_name (str): The name of the worker pool to use. If not
                provided, the default will be used.
            name (str): The name of the worker. If not provided, a random one
                will be generated. If provided, it cannot contain '/' or '%'.
                The name is used to identify the worker in the UI; if two
                processes have the same name, they will be treated as the same
                worker.
            loop_seconds (int): The number of seconds to wait between each loop
                of the worker.
            prefetch_seconds (int): The number of seconds to prefetch flow runs for.
            heartbeat_seconds (int): The number of seconds between each heartbeat.
            create_pool_if_not_found (bool): Whether to create the worker pool
                if it is not found. Defaults to `True`, but can be set to `False` to
                ensure that worker pools are not created accidentally.
        """
        if name and ("/" in name or "%" in name):
            raise ValueError("Worker name cannot contain '/' or '%'")
        name = name or f"{self.__class__.__name__} {uuid4()}"

        super().__init__(loop_seconds=loop_seconds or self.__class__.loop_seconds)

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

    @classmethod
    def __dispatch_key__(cls):
        if cls.__name__ == "BaseWorker":
            return None  # The base class is abstract
        return cls.type

    async def _on_start(self):
        """
        Start the heartbeat loop when the worker starts
        """
        await super()._on_start()
        # wait for an initial heartbeat to configure the worker
        await self.heartbeat_worker()
        # schedule the heartbeat loop to run every `heartbeat_seconds`
        self._heartbeat_task = asyncio.create_task(self._run_heartbeat_loop())
        self._storage_scan_task = asyncio.create_task(self._run_storage_scan_loop())

    async def _on_stop(self) -> None:
        # cancel the heartbeat task in case it hasn't started
        self._heartbeat_task.cancel()
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
        await self.submit_scheduled_flow_runs(flow_run_response=runs_response)

    async def heartbeat_worker(self):
        """
        Refreshes the worker's config and queues, and sends a heartbeat to the server.
        """
        async with get_client() as client:

            # ----------------------------------------------
            # refresh config
            # ----------------------------------------------

            try:
                worker_pool = await client.read_worker_pool(
                    worker_pool_name=self.worker_pool_name
                )
            except ObjectNotFound:
                if self.create_pool_if_not_found:
                    worker_pool = await client.create_worker_pool(
                        worker_pool=schemas.actions.WorkerPoolCreate(
                            name=self.worker_pool_name, type=self.type
                        )
                    )
                    self.logger.info(f"Worker pool {self.worker_pool_name!r} created.")
                else:
                    self.logger.warning(
                        f"Worker pool {self.worker_pool_name!r} not found!"
                    )
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
            self.worker_pool = worker_pool

            # ----------------------------------------------
            # refresh queues
            # ----------------------------------------------
            worker_pool_queues = await client.read_worker_pool_queues(
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
            await client.send_worker_heartbeat(
                worker_pool_name=self.worker_pool_name, worker_name=self.name
            )
            self.logger.debug(f"{self} refreshed")

    async def _run_heartbeat_loop(self):
        """
        Utility function to run the heartbeat loop forever
        """
        while self._is_running:
            await asyncio.sleep(self.heartbeat_seconds)
            await self.heartbeat_worker()

    async def _run_storage_scan_loop(self):
        while self._is_running:
            await asyncio.sleep(self.storage_scan_seconds)
            await self.scan_storage_for_deployments()

    async def scan_storage_for_deployments(self):
        self.logger.debug("Scanning %s for deployments", self.workflow_storage_path)
        possible_deployment_files = self.workflow_storage_path.glob("*.yaml")
        for possible_deployment_file in possible_deployment_files:
            await self._attempt_to_register_deployment(possible_deployment_file)

    async def _attempt_to_register_deployment(self, deployment_manifest_path):
        try:
            deployment = await Deployment.load_from_yaml(str(deployment_manifest_path))
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

    async def _unzip_deployments(self, zip_file: UploadFile):
        self.logger.info(
            "Unzipping deployments in %s to %s",
            zip_file.filename,
            self.workflow_storage_path,
        )
        shutil.unpack_archive(zip_file.filename, self.workflow_storage_path)

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

    def create_app(self) -> FastAPI:

        app = FastAPI()

        @app.on_event("startup")
        async def start_worker():
            asyncio.create_task(self.start())

        @app.on_event("shutdown")
        async def stop_worker():
            asyncio.create_task(self.stop())

        @app.get("/health")
        async def health() -> bool:
            return True

        @app.get("/status")
        async def get_status() -> Dict:
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

        @app.post("/submit_deployments")
        async def accept_deployment_zip(zip_file: UploadFile = File(...)) -> bool:
            asyncio.create_task(self._unzip_deployments(zip_file))
            return True

        return app

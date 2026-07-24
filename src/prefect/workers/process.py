"""
Module containing the Process worker used for executing flow runs as subprocesses.

To start a Process worker, run the following command:

```bash
prefect worker start --pool 'my-work-pool' --type process
```

Replace `my-work-pool` with the name of the work pool you want the worker
to poll for flow runs.

For more information about work pools and workers,
checkout out the [Prefect docs](https://docs.prefect.io/v3/concepts/work-pools/).
"""

from __future__ import annotations

import contextlib
import os
import tempfile
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, TypeVar

import anyio
import anyio.abc
from pydantic import Field, field_validator

from prefect._internal.schemas.validators import validate_working_dir
from prefect.client.schemas.objects import Flow as APIFlow
from prefect.runner.runner import Runner
from prefect.states import Pending
from prefect.utilities.processutils import command_to_string, get_sys_executable
from prefect.workers.base import (
    BaseJobConfiguration,
    BaseVariables,
    BaseWorker,
    BaseWorkerResult,
)

if TYPE_CHECKING:
    from uuid import UUID

    from prefect.client.schemas.objects import FlowRun, WorkPool
    from prefect.client.schemas.responses import DeploymentResponse
    from prefect.flows import Flow

FR = TypeVar("FR")  # used to capture the return type of a flow


class ProcessJobConfiguration(BaseJobConfiguration):
    stream_output: bool = Field(default=True)
    working_dir: Optional[Path] = Field(default=None)

    @field_validator("working_dir")
    @classmethod
    def validate_working_dir(cls, v: Path | str | None) -> Path | None:
        if isinstance(v, str):
            return validate_working_dir(v)
        return v

    def prepare_for_flow_run(
        self,
        flow_run: "FlowRun",
        deployment: "DeploymentResponse | None" = None,
        flow: "APIFlow | None" = None,
        work_pool: "WorkPool | None" = None,
        worker_name: str | None = None,
        worker_id: "UUID | None" = None,
    ) -> None:
        super().prepare_for_flow_run(
            flow_run,
            deployment,
            flow,
            work_pool,
            worker_name,
            worker_id=worker_id,
        )

        self.env: dict[str, str | None] = {**os.environ, **self.env}
        self.command: str | None = (
            command_to_string([get_sys_executable(), "-m", "prefect.engine"])
            if self.command == self._base_flow_run_command()
            else self.command
        )

    @staticmethod
    def _base_flow_run_command() -> str:
        """
        Override the base worker command because process workers still execute
        runs through `Runner.execute_flow_run` / `python -m prefect.engine`
        instead of the newer `prefect flow-run execute` path.
        """
        return "python -m prefect.engine"


class ProcessVariables(BaseVariables):
    stream_output: bool = Field(
        default=True,
        description=(
            "If enabled, workers will stream output from flow run processes to "
            "local standard output."
        ),
    )
    working_dir: Optional[Path] = Field(
        default=None,
        title="Working Directory",
        description=(
            "If provided, workers will open flow run processes within the "
            "specified path as the working directory. Otherwise, a temporary "
            "directory will be created."
        ),
    )


class ProcessWorkerResult(BaseWorkerResult):
    """Contains information about the final state of a completed process"""


class ProcessWorker(
    BaseWorker[ProcessJobConfiguration, ProcessVariables, ProcessWorkerResult]
):
    type = "process"
    job_configuration: type[ProcessJobConfiguration] = ProcessJobConfiguration
    job_configuration_variables: type[ProcessVariables] | None = ProcessVariables

    _description = (
        "Execute flow runs as subprocesses on a worker. Works well for local execution"
        " when first getting started."
    )
    _display_name = "Process"
    _documentation_url = "https://docs.prefect.io/latest/get-started/quickstart"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/356e6766a91baf20e1d08bbe16e8b5aaef4d8643-48x48.png"

    async def run(
        self,
        flow_run: "FlowRun",
        configuration: ProcessJobConfiguration,
        task_status: Optional[anyio.abc.TaskStatus[int]] = None,
    ) -> ProcessWorkerResult:
        if task_status is None:
            task_status = anyio.TASK_STATUS_IGNORED

        working_dir_ctx = (
            tempfile.TemporaryDirectory(suffix="prefect")
            if not configuration.working_dir
            else contextlib.nullcontext(configuration.working_dir)
        )
        with working_dir_ctx as working_dir, warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            process = await self._runner.execute_flow_run(
                flow_run_id=flow_run.id,
                command=configuration.command,
                cwd=working_dir,
                env=configuration.env,
                stream_output=configuration.stream_output,
                task_status=task_status,
            )

        status_code = (
            getattr(process, "returncode", None)
            if getattr(process, "returncode", None) is not None
            else getattr(process, "exitcode", None)
        )

        if process is None or status_code is None:
            raise RuntimeError("Failed to start flow run process.")

        return ProcessWorkerResult(status_code=status_code, identifier=str(process.pid))

    async def _submit_adhoc_run(
        self,
        flow: "Flow[..., FR]",
        parameters: dict[str, Any] | None = None,
        job_variables: dict[str, Any] | None = None,
        task_status: anyio.abc.TaskStatus["FlowRun"] | None = None,
        flow_run: "FlowRun | None" = None,
    ):
        from prefect.bundles import (
            create_bundle_for_flow_run,
        )

        if flow_run is None:
            flow_run = await self.client.create_flow_run(
                flow,
                parameters=parameters,
                state=Pending(),
                job_variables=job_variables,
                work_pool_name=self.work_pool.name,
            )
        else:
            # Reuse existing flow run - set state to Pending for retry
            await self.client.set_flow_run_state(
                flow_run.id,
                Pending(),
                force=True,
            )
        if task_status is not None:
            # Emit the flow run object to .submit to allow it to return a future as soon as possible
            task_status.started(flow_run)

        api_flow = APIFlow(id=flow_run.flow_id, name=flow.name, labels={})
        logger = self.get_flow_run_logger(flow_run)

        configuration = await self.job_configuration.from_template_and_values(
            base_job_template=self.work_pool.base_job_template,
            values=job_variables or {},
            client=self._client,
        )
        configuration.prepare_for_flow_run(
            flow_run=flow_run,
            flow=api_flow,
            work_pool=self.work_pool,
            worker_name=self.name,
            worker_id=self.backend_id,
        )

        result = create_bundle_for_flow_run(flow=flow, flow_run=flow_run)

        logger.debug("Executing flow run bundle in subprocess...")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                await self._runner.execute_bundle(
                    bundle=result["bundle"],
                    cwd=configuration.working_dir,
                    env=configuration.env,
                )
        except Exception:
            logger.exception("Error executing flow run bundle in subprocess")
            await self._propose_crashed_state(flow_run, "Flow run execution failed")
        finally:
            logger.debug("Flow run bundle execution complete")

    async def __aenter__(self) -> ProcessWorker:
        await super().__aenter__()
        self._runner = await self._exit_stack.enter_async_context(
            Runner(pause_on_shutdown=False, limit=None)
        )
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await super().__aexit__(*exc_info)

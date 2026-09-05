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
from pydantic import Field, PrivateAttr, field_validator

from prefect._internal.schemas.validators import validate_working_dir
from prefect.client.schemas.objects import Flow as APIFlow
from prefect.flows import load_flow_from_flow_run
from prefect.runner._flow_run_executor import (
    FlowRunExecutionResult,
    FlowRunExecutorContext,
)
from prefect.runner._process_manager import ProcessHandle
from prefect.runner._starter_engine import EngineCommandStarter
from prefect.runner._workspace_starter import WorkspaceResolvingEngineCommandStarter
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

    _command_configured: bool = PrivateAttr(default=False)

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
        # The base implementation fills in `_base_flow_run_command()` when no command
        # is configured, so provenance must be captured before delegating.
        self._command_configured = self.command is not None

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
            self.command
            if self._command_configured
            else command_to_string([get_sys_executable(), "-m", "prefect.engine"])
        )

    @staticmethod
    def _base_flow_run_command() -> str:
        """
        Process workers use the engine command as their fallback when prepared
        workspace dependency installation does not select another launcher.
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
            async with FlowRunExecutorContext() as ctx:
                workspace_root = Path(working_dir).resolve()
                if configuration._command_configured:
                    starter = EngineCommandStarter(
                        command=configuration.command,
                        cwd=workspace_root,
                        env=configuration.env,
                        stream_output=configuration.stream_output,
                        control_channel=ctx.control_channel,
                    )
                    executor = ctx.create_executor(
                        flow_run,
                        starter,
                        resolve_flow=load_flow_from_flow_run,
                        propose_submitting=False,
                    )
                else:
                    workspace_starter = WorkspaceResolvingEngineCommandStarter(
                        workspace_root=workspace_root,
                        command=None,
                        stream_output=configuration.stream_output,
                        control_channel=ctx.control_channel,
                        source_cwd=workspace_root,
                        environment=configuration.env,
                    )
                    ctx.call_after_exit(workspace_starter.close)
                    executor = ctx.create_executor(
                        flow_run,
                        workspace_starter,
                        propose_submitting=False,
                        hook_runner=workspace_starter.hook_runner,
                    )
                execution: FlowRunExecutionResult | None = None

                async def execute(
                    *,
                    task_status: anyio.abc.TaskStatus[
                        ProcessHandle
                    ] = anyio.TASK_STATUS_IGNORED,
                ) -> None:
                    nonlocal execution
                    execution = await executor.submit(task_status=task_status)

                async with anyio.create_task_group() as task_group:
                    handle = await task_group.start(execute)
                    if handle.pid is None:
                        raise RuntimeError("Flow run process has no PID")
                    task_status.started(handle.pid)

        if execution is None or execution.status_code is None:
            raise RuntimeError("Failed to start flow run process.")

        return ProcessWorkerResult(
            status_code=execution.status_code,
            identifier=str(execution.handle.pid),
        )

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

        try:
            result = create_bundle_for_flow_run(flow=flow, flow_run=flow_run)
        except Exception as exc:
            logger.exception(
                "Failed to create execution bundle for flow run '%s'.", flow_run.id
            )
            message = (
                f"Flow run bundle could not be created: {type(exc).__name__}: {exc}"
            )
            await self._propose_crashed_state(flow_run, message)
            return

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
        runner = Runner(pause_on_shutdown=False, limit=None)
        self._runner = await runner.__aenter__()
        try:
            await super().__aenter__()
        except BaseException as exc:
            await runner.__aexit__(type(exc), exc, exc.__traceback__)
            raise
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        try:
            # The worker task group owns ad-hoc submissions. Let those finish
            # while the runner is still available to supervise their children.
            await super().__aexit__(*exc_info)
        finally:
            await self._runner.__aexit__(*exc_info)

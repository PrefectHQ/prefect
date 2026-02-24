from __future__ import annotations

import datetime
from functools import partial
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

import anyio
import anyio.abc

from prefect.logging import get_logger
from prefect.runner._flow_run_executor import FlowRunExecutor, ProcessStarter
from prefect.types._datetime import now
from prefect.utilities.services import critical_service_loop

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient
    from prefect.client.schemas.objects import FlowRun
    from prefect.runner._cancellation_manager import CancellationManager
    from prefect.runner._deployment_registry import DeploymentRegistry
    from prefect.runner._hook_runner import HookRunner
    from prefect.runner._limit_manager import LimitManager
    from prefect.runner._process_manager import ProcessManager
    from prefect.runner._state_proposer import StateProposer
    from prefect.runner.storage import RunnerStorage


class StarterResolver(Protocol):
    """Factory producing a `ProcessStarter` for a given FlowRun.

    Injected into `ScheduledRunPoller` as a constructor argument.
    The Runner closes over `DeploymentRegistry` when building this callable.
    Raise `RuntimeError` for unknown deployments -- unknown is a programming error.
    """

    def __call__(self, flow_run: FlowRun) -> ProcessStarter: ...


class ScheduledRunPoller:
    """Orchestrates the poll-submit loop for scheduled flow runs.

    Owns the scheduling poll cycle, storage pull loops, `run_once` single-execution
    mode, and delegates per-run execution to `FlowRunExecutor` via a
    `resolve_starter` factory.
    """

    def __init__(
        self,
        *,
        query_seconds: float,
        prefetch_seconds: float,
        client: PrefectClient,
        limit_manager: LimitManager,
        deployment_registry: DeploymentRegistry,
        resolve_starter: StarterResolver,
        runs_task_group: anyio.abc.TaskGroup,
        storage_objs: list[RunnerStorage],
        process_manager: ProcessManager,
        state_proposer: StateProposer,
        hook_runner: HookRunner,
        cancellation_manager: CancellationManager,
    ) -> None:
        self._query_seconds = query_seconds
        self._prefetch_seconds = prefetch_seconds
        self._client = client
        self._limit_manager = limit_manager
        self._deployment_registry = deployment_registry
        self._resolve_starter = resolve_starter
        self._runs_task_group = runs_task_group
        self._storage_objs = storage_objs
        self._process_manager = process_manager
        self._state_proposer = state_proposer
        self._hook_runner = hook_runner
        self._cancellation_manager = cancellation_manager

        self._submitting_flow_run_ids: set[UUID] = set()
        self.last_polled: datetime.datetime | None = None
        self.stopping: bool = False
        self._logger = get_logger("runner")

    async def _get_scheduled_flow_runs(self) -> list[FlowRun]:
        """Query the API for scheduled flow runs across all registered deployments."""
        scheduled_before = now("UTC") + datetime.timedelta(
            seconds=int(self._prefetch_seconds)
        )
        self._logger.debug(
            "Querying for flow runs scheduled before %s", scheduled_before
        )
        runs = await self._client.get_scheduled_flow_runs_for_deployments(
            deployment_ids=list(self._deployment_registry.get_deployment_ids()),
            scheduled_before=scheduled_before,
        )
        self._logger.debug("Discovered %d scheduled flow runs", len(runs))
        return runs

    async def _get_and_submit_flow_runs(
        self,
        task_group: anyio.abc.TaskGroup | None = None,
    ) -> None:
        """Poll for scheduled runs and submit them for execution.

        When `task_group` is provided (e.g. from `run_once`), submissions are
        spawned into that group. Otherwise the instance-level `_runs_task_group`
        is used.
        """
        if self.stopping:
            return
        tg = task_group if task_group is not None else self._runs_task_group
        runs_response = await self._get_scheduled_flow_runs()
        self.last_polled = now("UTC")
        await self._submit_scheduled_flow_runs(
            flow_run_response=runs_response, task_group=tg
        )

    async def _submit_scheduled_flow_runs(
        self,
        flow_run_response: list[FlowRun],
        task_group: anyio.abc.TaskGroup,
    ) -> None:
        """Sort runs by schedule time and submit as many as capacity allows."""
        submittable_flow_runs = sorted(
            flow_run_response,
            key=lambda run: (
                run.next_scheduled_start_time is None,
                run.next_scheduled_start_time,
            ),
        )

        submitted_ids: set[UUID] = set()
        for flow_run in submittable_flow_runs:
            if flow_run.id in self._submitting_flow_run_ids:
                continue
            if self._limit_manager.has_slots_available():
                self._submitting_flow_run_ids.add(flow_run.id)
                submitted_ids.add(flow_run.id)
                task_group.start_soon(self._submit_run, flow_run, task_group)
            else:
                break  # sorted: no earlier run fits

        skipped_count = sum(
            1
            for r in submittable_flow_runs
            if r.id not in self._submitting_flow_run_ids and r.id not in submitted_ids
        )
        if skipped_count > 0:
            self._logger.info("%d scheduled runs skipped (at capacity)", skipped_count)

    async def _submit_run(
        self,
        flow_run: FlowRun,
        task_group: anyio.abc.TaskGroup,
    ) -> None:
        """Resolve a starter and delegate to `FlowRunExecutor` for a single run.

        ID was added by `_submit_scheduled_flow_runs` before `start_soon`.
        Remove it in finally -- whether submission succeeds or fails or is cancelled.
        """
        try:
            starter = self._resolve_starter(flow_run)
            executor = FlowRunExecutor(
                flow_run=flow_run,
                starter=starter,
                process_manager=self._process_manager,
                limit_manager=self._limit_manager,
                state_proposer=self._state_proposer,
                hook_runner=self._hook_runner,
                cancellation_manager=self._cancellation_manager,
                runs_task_group=task_group,
                client=self._client,
            )
            await task_group.start(executor.submit)
        except Exception:
            self._logger.exception("Failed to submit flow run '%s'", flow_run.id)
        finally:
            self._submitting_flow_run_ids.discard(flow_run.id)

    async def run(self) -> None:
        """Start storage pull loops and the scheduling poll loop.

        Loops run indefinitely inside a local task group until cancelled.
        """
        async with anyio.create_task_group() as loops_task_group:
            for storage in self._storage_objs:
                if storage.pull_interval:
                    loops_task_group.start_soon(
                        partial(
                            critical_service_loop,
                            workload=storage.pull_code,
                            interval=storage.pull_interval,
                            run_once=False,
                            jitter_range=0.3,
                        )
                    )
                else:
                    loops_task_group.start_soon(storage.pull_code)
            loops_task_group.start_soon(
                partial(
                    critical_service_loop,
                    workload=self._get_and_submit_flow_runs,
                    interval=self._query_seconds,
                    run_once=False,
                    jitter_range=0.3,
                )
            )

    async def run_once(self) -> None:
        """Execute a single poll-submit cycle and wait for all runs to complete.

        No storage loops -- locked decision. Opens a scoped task group so that
        all `executor.submit` tasks complete before `run_once` returns, meaning
        all processes have exited (terminal state reached).
        """
        async with anyio.create_task_group() as local_tg:
            await self._get_and_submit_flow_runs(task_group=local_tg)

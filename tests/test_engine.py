import asyncio
import statistics
import sys
import time
from contextlib import contextmanager
import threading
from typing import List
from unittest.mock import MagicMock
from uuid import uuid4

import anyio
import pendulum
import pytest
from pydantic import BaseModel
from prefect.task_runners import BaseTaskRunner, TaskConcurrencyType

import prefect.flows
from prefect import engine, flow, task
from prefect.client.orchestration import get_client
from prefect.client.schemas import OrchestrationResult
from prefect.context import FlowRunContext, get_run_context
from prefect.engine import (
    API_HEALTHCHECKS,
    begin_flow_run,
    check_api_reachable,
    create_and_begin_subflow_run,
    create_then_begin_flow_run,
    link_state_to_result,
    orchestrate_flow_run,
    orchestrate_task_run,
    pause_flow_run,
    propose_state,
    resume_flow_run,
    retrieve_flow_then_begin_flow_run,
)
from prefect.exceptions import (
    Abort,
    CrashedRun,
    FailedRun,
    ParameterTypeError,
    Pause,
    PausedRun,
    SignatureMismatchError,
)
from prefect.server.schemas.core import FlowRun
from prefect.futures import PrefectFuture
from prefect.results import ResultFactory
from prefect.server.schemas.filters import FlowRunFilter
from prefect.server.schemas.responses import (
    SetStateStatus,
    StateAcceptDetails,
    StateWaitDetails,
)
from prefect.server.schemas.states import StateDetails, StateType
from prefect.settings import (
    PREFECT_TASK_DEFAULT_RETRY_DELAY_SECONDS,
    PREFECT_FLOW_DEFAULT_RETRY_DELAY_SECONDS,
    temporary_settings,
)
from prefect.states import Cancelled, Failed, Pending, Running, State
from prefect.task_runners import SequentialTaskRunner
from prefect.tasks import exponential_backoff
from prefect.testing.utilities import AsyncMock, exceptions_equal
from prefect.utilities.annotations import quote
from prefect.utilities.pydantic import PartialModel


@pytest.fixture
async def result_factory(prefect_client):
    return await ResultFactory.default_factory(
        client=prefect_client,
    )


@pytest.fixture
async def patch_manifest_load(monkeypatch):
    async def patch_manifest(f):
        async def anon(*args, **kwargs):
            return f

        monkeypatch.setattr(
            engine,
            "load_flow_from_flow_run",
            anon,
        )
        return f

    return patch_manifest


@pytest.fixture
def parameterized_flow():
    @flow
    def flow_for_tests(dog: str, cat: int):
        """Flow for testing functions"""

    return flow_for_tests


@pytest.fixture
async def get_flow_run_context(prefect_client, result_factory, local_filesystem):
    partial_ctx = PartialModel(FlowRunContext)

    @flow
    def foo():
        pass

    test_task_runner = SequentialTaskRunner()
    flow_run = await prefect_client.create_flow_run(foo)

    async def _get_flow_run_context():
        async with anyio.create_task_group() as tg:
            partial_ctx.background_tasks = tg
            return partial_ctx.finalize(
                flow=foo,
                flow_run=flow_run,
                client=prefect_client,
                task_runner=test_task_runner,
                result_factory=result_factory,
                parameters={},
            )

    return _get_flow_run_context


class TestBlockingPause:
    async def test_tasks_cannot_be_paused(self):
        @task
        async def the_little_task_that_pauses():
            await pause_flow_run()
            return True

        @flow(task_runner=SequentialTaskRunner())
        async def the_mountain():
            return await the_little_task_that_pauses()

        with pytest.raises(RuntimeError, match="Cannot pause task runs.*"):
            await the_mountain()

    async def test_paused_flows_fail_if_not_resumed(self):
        @task
        async def doesnt_pause():
            return 42

        @flow(task_runner=SequentialTaskRunner())
        async def pausing_flow():
            x = await doesnt_pause.submit()
            await pause_flow_run(timeout=0.1)
            y = await doesnt_pause.submit()
            await doesnt_pause(wait_for=[x])
            await doesnt_pause(wait_for=[y])
            await doesnt_pause(wait_for=[x, y])

        with pytest.raises(FailedRun):
            # the sleeper mock will exhaust its side effects after 6 calls
            await pausing_flow()

    async def test_first_polling_interval_doesnt_grow_arbitrarily_large(
        self, monkeypatch
    ):
        sleeper = AsyncMock(side_effect=[None, None, None, None, None])
        monkeypatch.setattr("prefect.engine.anyio.sleep", sleeper)

        @task
        async def doesnt_pause():
            return 42

        @flow(task_runner=SequentialTaskRunner())
        async def pausing_flow():
            x = await doesnt_pause.submit()
            await pause_flow_run(timeout=20, poll_interval=100)
            y = await doesnt_pause.submit()
            await doesnt_pause(wait_for=[x])
            await doesnt_pause(wait_for=[y])
            await doesnt_pause(wait_for=[x, y])

        with pytest.raises(StopAsyncIteration):
            # the sleeper mock will exhaust its side effects after 6 calls
            await pausing_flow()

        sleep_intervals = [c.args[0] for c in sleeper.await_args_list]
        assert min(sleep_intervals) <= 20  # Okay if this is zero
        assert max(sleep_intervals) == 100

    @pytest.mark.flaky
    async def test_first_polling_is_smaller_than_the_timeout(self, monkeypatch):
        sleeper = AsyncMock(side_effect=[None, None, None, None, None])
        monkeypatch.setattr("prefect.engine.anyio.sleep", sleeper)

        @task
        async def doesnt_pause():
            return 42

        @flow(task_runner=SequentialTaskRunner())
        async def pausing_flow():
            x = await doesnt_pause.submit()
            await pause_flow_run(timeout=4, poll_interval=5)
            y = await doesnt_pause.submit()
            await doesnt_pause(wait_for=[x])
            await doesnt_pause(wait_for=[y])
            await doesnt_pause(wait_for=[x, y])

        with pytest.raises(StopAsyncIteration):
            # the sleeper mock will exhaust its side effects after 6 calls
            await pausing_flow()

        sleep_intervals = [c.args[0] for c in sleeper.await_args_list]
        assert sleep_intervals[0] == 2
        assert sleep_intervals[1:] == [5, 5, 5, 5, 5]

    @pytest.mark.flaky(max_runs=4)
    async def test_paused_flows_block_execution_in_sync_flows(self, prefect_client):
        @task
        def foo():
            return 42

        @flow(task_runner=SequentialTaskRunner())
        def pausing_flow():
            x = foo.submit()
            y = foo.submit()
            pause_flow_run(timeout=0.1)
            foo(wait_for=[x])
            foo(wait_for=[y])
            foo(wait_for=[x, y])

        flow_run_state = pausing_flow(return_state=True)
        flow_run_id = flow_run_state.state_details.flow_run_id
        task_runs = await prefect_client.read_task_runs(
            flow_run_filter=FlowRunFilter(id={"any_": [flow_run_id]})
        )
        assert len(task_runs) == 2, "only two tasks should have completed"

    async def test_paused_flows_block_execution_in_async_flows(self, prefect_client):
        @task
        async def foo():
            return 42

        @flow(task_runner=SequentialTaskRunner())
        async def pausing_flow():
            x = await foo.submit()
            y = await foo.submit()
            await pause_flow_run(timeout=0.1)
            await foo(wait_for=[x])
            await foo(wait_for=[y])
            await foo(wait_for=[x, y])

        flow_run_state = await pausing_flow(return_state=True)
        flow_run_id = flow_run_state.state_details.flow_run_id
        task_runs = await prefect_client.read_task_runs(
            flow_run_filter=FlowRunFilter(id={"any_": [flow_run_id]})
        )
        assert len(task_runs) == 2, "only two tasks should have completed"

    async def test_paused_flows_can_be_resumed(self, prefect_client):
        @task
        async def foo():
            return 42

        @flow(task_runner=SequentialTaskRunner())
        async def pausing_flow():
            x = await foo.submit()
            y = await foo.submit()
            await pause_flow_run(timeout=10, poll_interval=2, key="do-not-repeat")
            await foo(wait_for=[x])
            await pause_flow_run(timeout=10, poll_interval=2, key="do-not-repeat")
            await foo(wait_for=[y])
            await foo(wait_for=[x, y])

        async def flow_resumer():
            await anyio.sleep(3)
            flow_runs = await prefect_client.read_flow_runs(limit=1)
            active_flow_run = flow_runs[0]
            await resume_flow_run(active_flow_run.id)

        flow_run_state, the_answer = await asyncio.gather(
            pausing_flow(return_state=True),
            flow_resumer(),
        )
        flow_run_id = flow_run_state.state_details.flow_run_id
        task_runs = await prefect_client.read_task_runs(
            flow_run_filter=FlowRunFilter(id={"any_": [flow_run_id]})
        )
        assert len(task_runs) == 5, "all tasks should finish running"


class TestNonblockingPause:
    async def test_paused_flows_do_not_block_execution_with_reschedule_flag(
        self, prefect_client, deployment, session
    ):
        flow_run_id = None

        @task
        async def foo():
            return 42

        @flow(task_runner=SequentialTaskRunner())
        async def pausing_flow_without_blocking():
            nonlocal flow_run_id
            flow_run_id = get_run_context().flow_run.id

            # Add the deployment id to the flow run to allow a pause
            from prefect.server.models.flow_runs import update_flow_run

            await update_flow_run(
                session,
                flow_run_id,
                FlowRun.construct(deployment_id=deployment.id),
            )
            await session.commit()

            x = await foo.submit()
            y = await foo.submit()
            await pause_flow_run(timeout=20, reschedule=True)
            await foo(wait_for=[x])
            await foo(wait_for=[y])
            await foo(wait_for=[x, y])
            assert False, "This line should not be reached"

        with pytest.raises(Pause):
            await pausing_flow_without_blocking(return_state=True)

        flow_run = await prefect_client.read_flow_run(flow_run_id)
        assert flow_run.state.is_paused()
        task_runs = await prefect_client.read_task_runs(
            flow_run_filter=FlowRunFilter(id={"any_": [flow_run_id]})
        )
        assert len(task_runs) == 2, "only two tasks should have completed"

    async def test_paused_flows_gracefully_exit_with_reschedule_flag(
        self, session, deployment
    ):
        @task
        async def foo():
            return 42

        @flow(task_runner=SequentialTaskRunner())
        async def pausing_flow_without_blocking():
            # Add the deployment id to the flow run to allow a pause
            from prefect.server.models.flow_runs import update_flow_run

            await update_flow_run(
                session,
                prefect.runtime.flow_run.id,
                FlowRun.construct(deployment_id=deployment.id),
            )
            await session.commit()

            x = await foo.submit()
            y = await foo.submit()
            await pause_flow_run(timeout=20, reschedule=True)
            await foo(wait_for=[x])
            await foo(wait_for=[y])
            await foo(wait_for=[x, y])

        with pytest.raises(Pause):
            await pausing_flow_without_blocking()

    async def test_paused_flows_can_be_resumed_then_rescheduled(
        self, prefect_client, deployment, session
    ):
        flow_run_id = None

        @task
        async def foo():
            return 42

        @flow(task_runner=SequentialTaskRunner())
        async def pausing_flow_without_blocking():
            nonlocal flow_run_id
            flow_run_id = get_run_context().flow_run.id

            # Add the deployment id to the flow run to allow a pause
            from prefect.server.models.flow_runs import update_flow_run

            await update_flow_run(
                session,
                flow_run_id,
                FlowRun.construct(deployment_id=deployment.id),
            )
            await session.commit()

            x = await foo.submit()
            y = await foo.submit()
            await pause_flow_run(timeout=20, reschedule=True)
            await foo(wait_for=[x])
            await foo(wait_for=[y])
            await foo(wait_for=[x, y])

        with pytest.raises(Pause):
            await pausing_flow_without_blocking()

        flow_run = await prefect_client.read_flow_run(flow_run_id)
        assert flow_run.state.is_paused()

        await resume_flow_run(flow_run_id)
        flow_run = await prefect_client.read_flow_run(flow_run_id)
        assert flow_run.state.is_scheduled()

    async def test_subflows_cannot_be_paused_with_reschedule_flag(
        self, deployment, session
    ):
        @task
        async def foo():
            return 42

        @flow(task_runner=SequentialTaskRunner())
        async def pausing_flow_without_blocking():
            x = await foo.submit()
            y = await foo.submit()
            await pause_flow_run(timeout=20, reschedule=True)
            await foo(wait_for=[x])
            await foo(wait_for=[y])
            await foo(wait_for=[x, y])

        @flow(task_runner=SequentialTaskRunner())
        async def wrapper_flow():
            return await pausing_flow_without_blocking()

        with pytest.raises(RuntimeError, match="Cannot pause subflows"):
            await wrapper_flow()

    async def test_flows_without_deployments_cannot_be_paused_with_reschedule_flag(
        self,
    ):
        @task
        async def foo():
            return 42

        @flow(task_runner=SequentialTaskRunner())
        async def pausing_flow_without_blocking():
            x = await foo.submit()
            y = await foo.submit()
            await pause_flow_run(timeout=20, reschedule=True)
            await foo(wait_for=[x])
            await foo(wait_for=[y])
            await foo(wait_for=[x, y])

        with pytest.raises(
            RuntimeError, match="Cannot pause flows without a deployment"
        ):
            await pausing_flow_without_blocking()


class TestOutOfProcessPause:
    async def test_flows_can_be_paused_out_of_process(
        self, prefect_client, deployment, session
    ):
        @task
        async def foo():
            return 42

        # when pausing the flow run with a specific flow run id, `pause_flow_run`
        # attempts an out-of-process pause; this continues execution until the NEXT
        # task run attempts to start, then gracefully exits

        @flow(task_runner=SequentialTaskRunner())
        async def pausing_flow_without_blocking():
            # Add the deployment id to the flow run to allow a pause
            from prefect.server.models.flow_runs import update_flow_run

            await update_flow_run(
                session,
                prefect.runtime.flow_run.id,
                FlowRun.construct(deployment_id=deployment.id),
            )
            await session.commit()

            context = FlowRunContext.get()
            x = await foo.submit()
            y = await foo.submit()
            await pause_flow_run(flow_run_id=context.flow_run.id, timeout=20)
            await foo(wait_for=[x])
            await foo(wait_for=[y])
            await foo(wait_for=[x, y])

        flow_run_state = await pausing_flow_without_blocking(return_state=True)
        with pytest.raises(PausedRun):
            await flow_run_state.result()

        flow_run_id = flow_run_state.state_details.flow_run_id
        task_runs = await prefect_client.read_task_runs(
            flow_run_filter=FlowRunFilter(id={"any_": [flow_run_id]})
        )
        completed_task_runs = list(
            filter(lambda tr: tr.state.is_completed(), task_runs)
        )
        paused_task_runs = list(filter(lambda tr: tr.state.is_paused(), task_runs))
        assert len(task_runs) == 3, "only three tasks should have tried to run"
        assert len(completed_task_runs) == 2, "only two task runs should have completed"
        assert (
            len(paused_task_runs) == 1
        ), "one task run should have exited with a paused state"

    async def test_out_of_process_pauses_exit_gracefully(self, deployment, session):
        @task
        async def foo():
            return 42

        @flow(task_runner=SequentialTaskRunner())
        async def pausing_flow_without_blocking():
            # Add the deployment id to the flow run to allow a pause
            from prefect.server.models.flow_runs import update_flow_run

            await update_flow_run(
                session,
                prefect.runtime.flow_run.id,
                FlowRun.construct(deployment_id=deployment.id),
            )
            await session.commit()

            context = FlowRunContext.get()
            x = await foo.submit()
            y = await foo.submit()
            await pause_flow_run(flow_run_id=context.flow_run.id, timeout=20)
            await foo(wait_for=[x])
            await foo(wait_for=[y])
            await foo(wait_for=[x, y])

        with pytest.raises(PausedRun):
            await pausing_flow_without_blocking()


class TestOrchestrateTaskRun:
    async def test_propose_state_does_not_recurse(
        self, monkeypatch, prefect_client, mock_anyio_sleep, flow_run
    ):
        """
        Regression test for https://github.com/PrefectHQ/prefect/issues/8825.
        Previously propose_state would make a recursive call. In extreme cases
        the server would instruct propose_state to wait almost indefinitely
        leading to propose_state to hit max recursion depth
        """
        # the flow run must be running prior to running tasks
        await prefect_client.set_flow_run_state(
            flow_run_id=flow_run.id,
            state=Running(),
        )

        @task
        def foo():
            return 1

        task_run = await prefect_client.create_task_run(
            task=foo,
            flow_run_id=flow_run.id,
            dynamic_key="0",
            state=State(
                type=StateType.PENDING,
            ),
        )

        delay_seconds = 30
        num_waits = sys.getrecursionlimit() + 50

        prefect_client.set_task_run_state = AsyncMock(
            side_effect=[
                *[
                    OrchestrationResult(
                        status=SetStateStatus.WAIT,
                        details=StateWaitDetails(delay_seconds=delay_seconds),
                    )
                    for _ in range(num_waits)
                ],
                OrchestrationResult(
                    status=SetStateStatus.ACCEPT,
                    details=StateAcceptDetails(),
                    state=Running(),
                ),
            ]
        )

        with mock_anyio_sleep.assert_sleeps_for(delay_seconds * num_waits):
            await propose_state(
                prefect_client, State(type=StateType.RUNNING), task_run_id=task_run.id
            )

    async def test_waits_until_scheduled_start_time(
        self,
        prefect_client,
        flow_run,
        mock_anyio_sleep,
        local_filesystem,
        result_factory,
        monkeypatch,
    ):
        # the flow run must be running prior to running tasks
        await prefect_client.set_flow_run_state(
            flow_run_id=flow_run.id,
            state=Running(),
        )

        @task
        def foo():
            return 1

        task_run = await prefect_client.create_task_run(
            task=foo,
            flow_run_id=flow_run.id,
            dynamic_key="0",
            state=State(
                type=StateType.SCHEDULED,
                state_details=StateDetails(
                    scheduled_time=pendulum.now("utc").add(minutes=5)
                ),
            ),
        )

        with mock_anyio_sleep.assert_sleeps_for(5 * 60):
            state = await orchestrate_task_run(
                task=foo,
                task_run=task_run,
                parameters={},
                wait_for=None,
                result_factory=result_factory,
                interruptible=False,
                client=prefect_client,
                log_prints=False,
            )

        assert state.is_completed()
        assert await state.result() == 1

    async def test_does_not_wait_for_scheduled_time_in_past(
        self,
        prefect_client,
        flow_run,
        mock_anyio_sleep,
        result_factory,
        local_filesystem,
    ):
        # the flow run must be running prior to running tasks
        await prefect_client.set_flow_run_state(
            flow_run_id=flow_run.id,
            state=Running(),
        )

        @task
        def foo():
            return 1

        task_run = await prefect_client.create_task_run(
            task=foo,
            flow_run_id=flow_run.id,
            dynamic_key="0",
            state=State(
                type=StateType.SCHEDULED,
                state_details=StateDetails(
                    scheduled_time=pendulum.now("utc").subtract(minutes=5)
                ),
            ),
        )

        state = await orchestrate_task_run(
            task=foo,
            task_run=task_run,
            parameters={},
            wait_for=None,
            result_factory=result_factory,
            interruptible=False,
            client=prefect_client,
            log_prints=False,
        )

        mock_anyio_sleep.assert_not_called()
        assert state.is_completed()
        assert await state.result() == 1

    async def test_waits_for_awaiting_retry_scheduled_time(
        self,
        mock_anyio_sleep,
        prefect_client,
        flow_run,
        result_factory,
        local_filesystem,
    ):
        # the flow run must be running prior to running tasks
        await prefect_client.set_flow_run_state(
            flow_run_id=flow_run.id,
            state=Running(),
        )

        # Define a task that fails once and then succeeds
        mock = MagicMock()

        @task(retries=1, retry_delay_seconds=43)
        def flaky_function():
            mock()

            if mock.call_count == 2:
                return 1

            raise ValueError("try again, but only once")

        # Create a task run to test
        task_run = await prefect_client.create_task_run(
            task=flaky_function,
            flow_run_id=flow_run.id,
            state=Pending(),
            dynamic_key="0",
        )

        # Actually run the task
        with mock_anyio_sleep.assert_sleeps_for(43):
            state = await orchestrate_task_run(
                task=flaky_function,
                task_run=task_run,
                parameters={},
                wait_for=None,
                result_factory=result_factory,
                interruptible=False,
                client=prefect_client,
                log_prints=False,
            )

        # Check for a proper final result
        assert await state.result() == 1

        # Check expected state transitions
        states = await prefect_client.read_task_run_states(str(task_run.id))
        state_names = [state.type for state in states]
        assert state_names == [
            StateType.PENDING,
            StateType.RUNNING,
            StateType.SCHEDULED,
            StateType.RUNNING,
            StateType.COMPLETED,
        ]

    async def test_waits_for_configurable_sleeps(
        self,
        mock_anyio_sleep,
        prefect_client,
        flow_run,
        result_factory,
        local_filesystem,
    ):
        # the flow run must be running prior to running tasks
        await prefect_client.set_flow_run_state(
            flow_run_id=flow_run.id,
            state=Running(),
        )

        # Define a task that fails once and then succeeds
        mock = MagicMock()

        @task(retries=3, retry_delay_seconds=[3, 5, 9])
        def flaky_function():
            mock()

            if mock.call_count == 4:
                return 1

            raise ValueError("try again")

        # Create a task run to test
        task_run = await prefect_client.create_task_run(
            task=flaky_function,
            flow_run_id=flow_run.id,
            state=Pending(),
            dynamic_key="0",
        )

        # Actually run the task
        # this task should sleep for a total of 17 seconds across all conifgured retries
        with mock_anyio_sleep.assert_sleeps_for(17):
            state = await orchestrate_task_run(
                task=flaky_function,
                task_run=task_run,
                parameters={},
                wait_for=None,
                result_factory=result_factory,
                interruptible=False,
                client=prefect_client,
                log_prints=False,
            )

        assert mock_anyio_sleep.await_count == 3

        # Check for a proper final result
        assert await state.result() == 1

    async def test_waits_configured_with_callable(
        self,
        mock_anyio_sleep,
        prefect_client,
        flow_run,
        result_factory,
        local_filesystem,
    ):
        # the flow run must be running prior to running tasks
        await prefect_client.set_flow_run_state(
            flow_run_id=flow_run.id,
            state=Running(),
        )

        # Define a task that fails once and then succeeds
        mock = MagicMock()

        @task(retries=3, retry_delay_seconds=exponential_backoff(10))
        def flaky_function():
            mock()

            if mock.call_count == 4:
                return 1

            raise ValueError("try again")

        # Create a task run to test
        task_run = await prefect_client.create_task_run(
            task=flaky_function,
            flow_run_id=flow_run.id,
            state=Pending(),
            dynamic_key="0",
        )

        # exponential backoff will automatically configure increasing sleeps
        with mock_anyio_sleep.assert_sleeps_for(70):
            state = await orchestrate_task_run(
                task=flaky_function,
                task_run=task_run,
                parameters={},
                wait_for=None,
                result_factory=result_factory,
                interruptible=False,
                client=prefect_client,
                log_prints=False,
            )

        assert mock_anyio_sleep.await_count == 3

        # Check for a proper final result
        assert await state.result() == 1

    @pytest.mark.parametrize("jitter_factor", [0.1, 1, 10, 100])
    @pytest.mark.flaky(max_runs=3)
    async def test_waits_jittery_sleeps(
        self,
        mock_anyio_sleep,
        prefect_client,
        flow_run,
        result_factory,
        local_filesystem,
        jitter_factor,
    ):
        # the flow run must be running prior to running tasks
        await prefect_client.set_flow_run_state(
            flow_run_id=flow_run.id,
            state=Running(),
        )

        # Define a task that fails once and then succeeds
        mock = MagicMock()

        @task(retries=10, retry_delay_seconds=100, retry_jitter_factor=jitter_factor)
        async def flaky_function():
            mock()

            if mock.call_count == 11:
                return 1

            raise ValueError("try again")

        # Create a task run to test
        task_run = await prefect_client.create_task_run(
            task=flaky_function,
            flow_run_id=flow_run.id,
            state=Pending(),
            dynamic_key="0",
        )

        # Actually run the task
        state = await orchestrate_task_run(
            task=flaky_function,
            task_run=task_run,
            parameters={},
            wait_for=None,
            result_factory=result_factory,
            interruptible=False,
            client=prefect_client,
            log_prints=False,
        )

        assert mock_anyio_sleep.await_count == 10
        sleeps = [c.args[0] for c in mock_anyio_sleep.await_args_list]
        assert statistics.variance(sleeps) > 0
        assert max(sleeps) < 100 * (1 + jitter_factor)

        # Check for a proper final result
        assert await state.result() == 1

    @pytest.mark.parametrize(
        "upstream_task_state", [Pending(), Running(), Cancelled(), Failed()]
    )
    async def test_returns_not_ready_when_any_upstream_futures_resolve_to_incomplete(
        self,
        prefect_client,
        flow_run,
        upstream_task_state,
        result_factory,
        local_filesystem,
    ):
        # Define a mock to ensure the task was not run
        mock = MagicMock()

        @task
        def my_task(x):
            mock()

        # Create an upstream task run
        upstream_task_run = await prefect_client.create_task_run(
            task=my_task,
            flow_run_id=flow_run.id,
            state=upstream_task_state,
            dynamic_key="upstream",
        )
        upstream_task_state.state_details.task_run_id = upstream_task_run.id

        # Create a future to wrap the upstream task, have it resolve to the given
        # incomplete state
        future = PrefectFuture(
            key=str(upstream_task_run.id),
            name="foo",
            task_runner=None,
            _final_state=upstream_task_state,
        )
        # simulate assigning task run to the future
        future.task_run = upstream_task_run
        future._submitted.set()

        # Create a task run to test
        task_run = await prefect_client.create_task_run(
            task=my_task,
            flow_run_id=flow_run.id,
            state=Pending(),
            dynamic_key="downstream",
        )

        # Actually run the task
        state = await orchestrate_task_run(
            task=my_task,
            task_run=task_run,
            # Nest the future in a collection to ensure that it is found
            parameters={"x": {"nested": [future]}},
            wait_for=None,
            result_factory=result_factory,
            interruptible=False,
            client=prefect_client,
            log_prints=False,
        )

        # The task did not run
        mock.assert_not_called()

        # Check that the state is 'NotReady'
        assert state.is_pending()
        assert state.name == "NotReady"
        assert (
            state.message
            == f"Upstream task run '{upstream_task_run.id}' did not reach a 'COMPLETED'"
            " state."
        )

    async def test_quoted_parameters_are_resolved(
        self, prefect_client, flow_run, result_factory, local_filesystem
    ):
        # the flow run must be running prior to running tasks
        await prefect_client.set_flow_run_state(
            flow_run_id=flow_run.id,
            state=Running(),
        )

        # Define a mock to ensure the task was not run
        mock = MagicMock()

        @task
        def my_task(x):
            mock(x)

        # Create a task run to test
        task_run = await prefect_client.create_task_run(
            task=my_task,
            flow_run_id=flow_run.id,
            state=Pending(),
            dynamic_key="downstream",
        )

        # Actually run the task
        state = await orchestrate_task_run(
            task=my_task,
            task_run=task_run,
            # Quote some data
            parameters={"x": quote(1)},
            wait_for=None,
            result_factory=result_factory,
            interruptible=False,
            client=prefect_client,
            log_prints=False,
        )

        # The task ran with the unqoted data
        mock.assert_called_once_with(1)

        # Check that the state completed happily
        assert state.is_completed()

    @pytest.mark.parametrize(
        "upstream_task_state", [Pending(), Running(), Cancelled(), Failed()]
    )
    async def test_states_in_parameters_can_be_incomplete_if_quoted(
        self,
        prefect_client,
        flow_run,
        upstream_task_state,
        result_factory,
        local_filesystem,
    ):
        # the flow run must be running prior to running tasks
        await prefect_client.set_flow_run_state(
            flow_run_id=flow_run.id,
            state=Running(),
        )

        # Define a mock to ensure the task was not run
        mock = MagicMock()

        @task
        def my_task(x):
            mock(x)

        # Create a task run to test
        task_run = await prefect_client.create_task_run(
            task=my_task,
            flow_run_id=flow_run.id,
            state=Pending(),
            dynamic_key="downstream",
        )

        # Actually run the task
        state = await orchestrate_task_run(
            task=my_task,
            task_run=task_run,
            parameters={"x": quote(upstream_task_state)},
            wait_for=None,
            result_factory=result_factory,
            interruptible=False,
            client=prefect_client,
            log_prints=False,
        )

        # The task ran with the state as its input
        mock.assert_called_once_with(upstream_task_state)

        # Check that the task completed happily
        assert state.is_completed()

    async def test_global_task_retry_delay_seconds(
        self, mock_anyio_sleep, prefect_client, flow_run, result_factory
    ):
        with temporary_settings(
            updates={PREFECT_TASK_DEFAULT_RETRY_DELAY_SECONDS: "43"}
        ):
            # the flow run must be running prior to running tasks
            await prefect_client.set_flow_run_state(
                flow_run_id=flow_run.id,
                state=Running(),
            )

            # Define a task that fails once and then succeeds
            mock = MagicMock()

            @task(retries=1)
            def flaky_function():
                mock()

                if mock.call_count == 2:
                    return 1

                raise ValueError("try again, but only once")

            # Create a task run to test
            task_run = await prefect_client.create_task_run(
                task=flaky_function,
                flow_run_id=flow_run.id,
                state=Pending(),
                dynamic_key="0",
            )

            # Actually run the task
            with mock_anyio_sleep.assert_sleeps_for(43):
                await orchestrate_task_run(
                    task=flaky_function,
                    task_run=task_run,
                    parameters={},
                    wait_for=None,
                    result_factory=result_factory,
                    interruptible=False,
                    client=prefect_client,
                    log_prints=False,
                )


class TestOrchestrateFlowRun:
    @pytest.fixture
    def partial_flow_run_context(self, result_factory, local_filesystem):
        return PartialModel(
            FlowRunContext,
            task_runner=SequentialTaskRunner(),
            sync_portal=None,
            result_factory=result_factory,
        )

    async def test_propose_state_does_not_recurse(
        self, monkeypatch, prefect_client, mock_anyio_sleep
    ):
        """
        Regression test for https://github.com/PrefectHQ/prefect/issues/8825.
        Previously propose_state would make a recursive call. In extreme cases
        the server would instruct propose_state to wait almost indefinitely
        leading to propose_state to hit max recursion depth
        """

        @flow
        def foo():
            return 1

        flow_run = await prefect_client.create_flow_run(
            flow=foo,
            state=State(
                type=StateType.PENDING,
            ),
        )

        delay_seconds = 30
        num_waits = sys.getrecursionlimit() + 50

        prefect_client.set_flow_run_state = AsyncMock(
            side_effect=[
                *[
                    OrchestrationResult(
                        status=SetStateStatus.WAIT,
                        details=StateWaitDetails(delay_seconds=delay_seconds),
                    )
                    for _ in range(num_waits)
                ],
                OrchestrationResult(
                    status=SetStateStatus.ACCEPT,
                    details=StateAcceptDetails(),
                    state=Running(),
                ),
            ]
        )

        with mock_anyio_sleep.assert_sleeps_for(delay_seconds * num_waits):
            await propose_state(
                prefect_client, State(type=StateType.RUNNING), flow_run_id=flow_run.id
            )

    async def test_waits_until_scheduled_start_time(
        self, prefect_client, mock_anyio_sleep, partial_flow_run_context
    ):
        @flow
        def foo():
            return 1

        partial_flow_run_context.background_tasks = anyio.create_task_group()

        flow_run = await prefect_client.create_flow_run(
            flow=foo,
            state=State(
                type=StateType.SCHEDULED,
                state_details=StateDetails(
                    scheduled_time=pendulum.now("utc").add(minutes=5)
                ),
            ),
        )
        with mock_anyio_sleep.assert_sleeps_for(5 * 60):
            state = await orchestrate_flow_run(
                flow=foo,
                flow_run=flow_run,
                parameters={},
                wait_for=None,
                client=prefect_client,
                interruptible=False,
                partial_flow_run_context=partial_flow_run_context,
                user_thread=threading.current_thread(),
            )

        assert await state.result() == 1

    async def test_does_not_wait_for_scheduled_time_in_past(
        self, prefect_client, mock_anyio_sleep, partial_flow_run_context
    ):
        @flow
        def foo():
            return 1

        partial_flow_run_context.background_tasks = anyio.create_task_group()

        flow_run = await prefect_client.create_flow_run(
            flow=foo,
            state=State(
                type=StateType.SCHEDULED,
                state_details=StateDetails(
                    scheduled_time=pendulum.now("utc").subtract(minutes=5)
                ),
            ),
        )

        with anyio.fail_after(5):
            state = await orchestrate_flow_run(
                flow=foo,
                flow_run=flow_run,
                parameters={},
                wait_for=None,
                client=prefect_client,
                interruptible=False,
                partial_flow_run_context=partial_flow_run_context,
                user_thread=threading.current_thread(),
            )

        mock_anyio_sleep.assert_not_called()
        assert await state.result() == 1

    async def test_waits_for_awaiting_retry_scheduled_time(
        self, prefect_client, mock_anyio_sleep, partial_flow_run_context
    ):
        flow_run_count = 0

        partial_flow_run_context.background_tasks = anyio.create_task_group()

        @flow(retries=1, retry_delay_seconds=43)
        def flaky_function():
            nonlocal flow_run_count
            flow_run_count += 1

            if flow_run_count == 1:
                raise ValueError("try again, but only once")

            return 1

        flow_run = await prefect_client.create_flow_run(
            flow=flaky_function, state=Pending()
        )

        with mock_anyio_sleep.assert_sleeps_for(43):
            state = await orchestrate_flow_run(
                flow=flaky_function,
                flow_run=flow_run,
                parameters={},
                wait_for=None,
                client=prefect_client,
                interruptible=False,
                partial_flow_run_context=partial_flow_run_context,
                user_thread=threading.current_thread(),
            )

        # Check for a proper final result
        assert await state.result() == 1

        # Check expected state transitions
        states = await prefect_client.read_flow_run_states(str(flow_run.id))
        state_names = [state.type for state in states]
        assert state_names == [
            StateType.PENDING,
            StateType.RUNNING,
            StateType.SCHEDULED,
            StateType.RUNNING,
            StateType.COMPLETED,
        ]

    async def test_global_flow_retry_delay_seconds(
        self, prefect_client, mock_anyio_sleep, partial_flow_run_context
    ):
        with temporary_settings(
            updates={PREFECT_FLOW_DEFAULT_RETRY_DELAY_SECONDS: "43"}
        ):
            flow_run_count = 0

            partial_flow_run_context.background_tasks = anyio.create_task_group()

            @flow(retries=1)
            def flaky_function():
                nonlocal flow_run_count
                flow_run_count += 1

                if flow_run_count == 1:
                    raise ValueError("try again, but only once")

                return 1

            flow_run = await prefect_client.create_flow_run(
                flow=flaky_function, state=Pending()
            )

            with mock_anyio_sleep.assert_sleeps_for(43):
                await orchestrate_flow_run(
                    flow=flaky_function,
                    flow_run=flow_run,
                    parameters={},
                    wait_for=None,
                    client=prefect_client,
                    interruptible=False,
                    partial_flow_run_context=partial_flow_run_context,
                    user_thread=threading.current_thread(),
                )


class TestFlowRunCrashes:
    @staticmethod
    @contextmanager
    def capture_cancellation():
        """Utility for capturing crash exceptions consistently in these tests"""
        try:
            yield
        except BaseException:
            # In python 3.8+ cancellation raises a `BaseException` that will not
            # be captured by `orchestrate_flow_run` and needs to be trapped here to
            # prevent the test from failing before we can assert things are 'Crashed'
            pass
        except anyio.get_cancelled_exc_class() as exc:
            raise RuntimeError("The cancellation error was not caught.") from exc

    async def test_flow_timeouts_are_not_crashes(self, flow_run, prefect_client):
        """
        Since timeouts use anyio cancellation scopes, we want to ensure that they are
        not marked as crashes
        """

        @flow(timeout_seconds=0.1)
        async def my_flow():
            await anyio.sleep_forever()

        await begin_flow_run(
            flow=my_flow,
            parameters={},
            flow_run=flow_run,
            client=prefect_client,
            user_thread=threading.current_thread(),
        )
        flow_run = await prefect_client.read_flow_run(flow_run.id)

        assert flow_run.state.is_failed()
        assert flow_run.state.type != StateType.CRASHED
        assert "exceeded timeout" in flow_run.state.message

    async def test_aborts_are_not_crashes(self, flow_run, prefect_client):
        """
        Since aborts are base exceptions, we want to ensure that they are not marked as
        crashes
        """

        @flow
        async def my_flow():
            raise Abort()

        with pytest.raises(Abort):
            # ^ the exception should be re-raised
            await begin_flow_run(
                flow=my_flow,
                parameters={},
                flow_run=flow_run,
                client=prefect_client,
                user_thread=threading.current_thread(),
            )

        flow_run = await prefect_client.read_flow_run(flow_run.id)

        assert flow_run.state.type != StateType.CRASHED


class TestTaskRunCrashes:
    @pytest.mark.filterwarnings(
        "ignore::pytest.PytestUnhandledThreadExceptionWarning"
    )  # Pytest complains about unhandled exception in runtime thread
    @pytest.mark.parametrize("interrupt_type", [KeyboardInterrupt, SystemExit])
    async def test_interrupt_in_task_function_crashes_task_and_flow(
        self, flow_run, prefect_client, interrupt_type
    ):
        @task
        async def my_task():
            raise interrupt_type()

        @flow
        async def my_flow():
            await my_task()

        with pytest.raises(interrupt_type):
            await begin_flow_run(
                flow=my_flow,
                flow_run=flow_run,
                parameters={},
                client=prefect_client,
                user_thread=threading.current_thread(),
            )

        flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert flow_run.state.is_crashed()
        assert flow_run.state.type == StateType.CRASHED
        assert "Execution was aborted" in flow_run.state.message
        with pytest.raises(CrashedRun, match="Execution was aborted"):
            await flow_run.state.result()

        task_runs = await prefect_client.read_task_runs()
        assert len(task_runs) == 1
        task_run = task_runs[0]
        assert task_run.state.is_crashed()
        assert task_run.state.type == StateType.CRASHED
        assert "Execution was aborted" in task_run.state.message
        with pytest.raises(CrashedRun, match="Execution was aborted"):
            await task_run.state.result()

    @pytest.mark.filterwarnings(
        "ignore::pytest.PytestUnhandledThreadExceptionWarning"
    )  # Pytest complains about unhandled exception in runtime thread
    @pytest.mark.parametrize("interrupt_type", [KeyboardInterrupt, SystemExit])
    async def test_interrupt_in_task_orchestration_crashes_task_and_flow(
        self, flow_run, prefect_client, interrupt_type, monkeypatch
    ):
        monkeypatch.setattr(
            "prefect.engine.orchestrate_task_run", AsyncMock(side_effect=interrupt_type)
        )

        @task
        async def my_task():
            pass

        @flow
        async def my_flow():
            await my_task()

        with pytest.raises(interrupt_type):
            await begin_flow_run(
                flow=my_flow,
                flow_run=flow_run,
                parameters={},
                client=prefect_client,
                user_thread=threading.current_thread(),
            )

        flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert flow_run.state.is_crashed()
        assert flow_run.state.type == StateType.CRASHED
        assert "Execution was aborted" in flow_run.state.message
        with pytest.raises(CrashedRun, match="Execution was aborted"):
            await flow_run.state.result()

        task_runs = await prefect_client.read_task_runs()
        assert len(task_runs) == 1
        task_run = task_runs[0]
        assert task_run.state.is_crashed()
        assert task_run.state.type == StateType.CRASHED
        assert "Execution was aborted" in task_run.state.message
        with pytest.raises(CrashedRun, match="Execution was aborted"):
            await task_run.state.result()

    async def test_error_in_task_orchestration_crashes_task_but_not_flow(
        self, flow_run, prefect_client, monkeypatch
    ):
        exception = ValueError("Boo!")

        monkeypatch.setattr(
            "prefect.engine.orchestrate_task_run", AsyncMock(side_effect=exception)
        )

        @task
        async def my_task():
            pass

        @flow
        async def my_flow():
            await my_task._run()

        # Note exception should not be re-raised
        state = await begin_flow_run(
            flow=my_flow,
            flow_run=flow_run,
            parameters={},
            client=prefect_client,
            user_thread=threading.current_thread(),
        )

        flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert flow_run.state.is_failed()
        assert flow_run.state.name == "Failed"
        assert "1/1 states failed" in flow_run.state.message

        task_run_states = await state.result(raise_on_failure=False)
        assert len(task_run_states) == 1
        task_run_state = task_run_states[0]
        assert task_run_state.is_crashed()

        assert task_run_state.type == StateType.CRASHED
        assert (
            "Execution was interrupted by an unexpected exception"
            in task_run_state.message
        )
        assert exceptions_equal(
            await task_run_state.result(raise_on_failure=False), exception
        )

        # Check that the state was reported to the server
        task_run = await prefect_client.read_task_run(
            task_run_state.state_details.task_run_id
        )
        compare_fields = {"name", "type", "message"}
        assert task_run_state.dict(include=compare_fields) == task_run.state.dict(
            include=compare_fields
        )


class TestDeploymentFlowRun:
    async def create_deployment(self, client, flow):
        flow_id = await client.create_flow(flow)
        return await client.create_deployment(
            flow_id,
            name="test",
            manifest_path="file.json",
        )

    async def test_completed_run(self, prefect_client, patch_manifest_load):
        @flow
        def my_flow(x: int):
            return x

        await patch_manifest_load(my_flow)
        deployment_id = await self.create_deployment(prefect_client, my_flow)

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id, parameters={"x": 1}
        )

        state = await retrieve_flow_then_begin_flow_run(
            flow_run.id, client=prefect_client, user_thread=threading.current_thread()
        )
        assert await state.result() == 1

    async def test_retries_loaded_from_flow_definition(
        self, prefect_client, patch_manifest_load, mock_anyio_sleep
    ):
        @flow(retries=2, retry_delay_seconds=3)
        def my_flow(x: int):
            raise ValueError()

        await patch_manifest_load(my_flow)
        deployment_id = await self.create_deployment(prefect_client, my_flow)

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id, parameters={"x": 1}
        )
        assert flow_run.empirical_policy.retries is None
        assert flow_run.empirical_policy.retry_delay is None

        with mock_anyio_sleep.assert_sleeps_for(
            my_flow.retries * my_flow.retry_delay_seconds,
            # Allow an extra second tolerance per retry to account for rounding
            extra_tolerance=my_flow.retries,
        ):
            state = await retrieve_flow_then_begin_flow_run(
                flow_run.id,
                client=prefect_client,
                user_thread=threading.current_thread(),
            )

        flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert flow_run.empirical_policy.retries == 2
        assert flow_run.empirical_policy.retry_delay == 3
        assert state.is_failed()
        assert flow_run.run_count == 3

    async def test_failed_run(self, prefect_client, patch_manifest_load):
        @flow
        def my_flow(x: int):
            raise ValueError("test!")

        await patch_manifest_load(my_flow)
        deployment_id = await self.create_deployment(prefect_client, my_flow)

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id, parameters={"x": 1}
        )

        state = await retrieve_flow_then_begin_flow_run(
            flow_run.id, client=prefect_client, user_thread=threading.current_thread()
        )
        assert state.is_failed()
        with pytest.raises(ValueError, match="test!"):
            await state.result()

    async def test_parameters_are_cast_to_correct_type(
        self, prefect_client, patch_manifest_load
    ):
        @flow
        def my_flow(x: int):
            return x

        await patch_manifest_load(my_flow)
        deployment_id = await self.create_deployment(prefect_client, my_flow)

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id, parameters={"x": "1"}
        )

        state = await retrieve_flow_then_begin_flow_run(
            flow_run.id, client=prefect_client, user_thread=threading.current_thread()
        )
        assert await state.result() == 1

    async def test_state_is_failed_when_parameters_fail_validation(
        self, prefect_client, patch_manifest_load
    ):
        @flow
        def my_flow(x: int):
            return x

        await patch_manifest_load(my_flow)
        deployment_id = await self.create_deployment(prefect_client, my_flow)

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id, parameters={"x": "not-an-int"}
        )

        state = await retrieve_flow_then_begin_flow_run(
            flow_run.id, client=prefect_client, user_thread=threading.current_thread()
        )
        assert state.is_failed()
        assert "Validation of flow parameters failed with error" in state.message
        assert (
            "ParameterTypeError: Flow run received invalid parameters" in state.message
        )
        assert "x: value is not a valid integer" in state.message

        with pytest.raises(ParameterTypeError, match="value is not a valid integer"):
            await state.result()


class TestDynamicKeyHandling:
    async def test_dynamic_key_increases_sequentially(self, prefect_client):
        @task
        def my_task():
            pass

        @flow
        def my_flow():
            my_task()
            my_task()
            my_task()

        my_flow()

        task_runs = await prefect_client.read_task_runs()

        assert sorted([int(run.dynamic_key) for run in task_runs]) == [0, 1, 2]

    async def test_subflow_resets_dynamic_key(self, prefect_client):
        @task
        def my_task():
            pass

        @flow
        def subflow():
            my_task()

        @flow
        def my_flow():
            my_task()
            my_task()
            subflow()
            my_task()

        state = my_flow._run()

        task_runs = await prefect_client.read_task_runs()
        parent_task_runs = [
            task_run
            for task_run in task_runs
            if task_run.flow_run_id == state.state_details.flow_run_id
        ]
        subflow_task_runs = [
            task_run
            for task_run in task_runs
            if task_run.flow_run_id != state.state_details.flow_run_id
        ]

        assert len(parent_task_runs) == 4  # 3 standard task runs and 1 subflow
        assert len(subflow_task_runs) == 1

        assert int(subflow_task_runs[0].dynamic_key) == 0

    async def test_dynamic_key_unique_per_task_key(self, prefect_client):
        @task
        def task_one():
            pass

        @task
        def task_two():
            pass

        @flow
        def my_flow():
            task_one()
            task_two()
            task_two()
            task_one()

        my_flow()

        task_runs = await prefect_client.read_task_runs()

        assert sorted([int(run.dynamic_key) for run in task_runs]) == [0, 0, 1, 1]


class TestCreateThenBeginFlowRun:
    async def test_handles_bad_parameter_types(
        self, prefect_client, parameterized_flow
    ):
        state = await create_then_begin_flow_run(
            flow=parameterized_flow,
            parameters={"dog": [1, 2], "cat": "not an int"},
            wait_for=None,
            return_type="state",
            client=prefect_client,
            user_thread=threading.current_thread(),
        )
        assert state.type == StateType.FAILED
        assert "Validation of flow parameters failed with error" in state.message
        assert (
            "ParameterTypeError: Flow run received invalid parameters" in state.message
        )
        assert "dog: str type expected" in state.message
        assert "cat: value is not a valid integer" in state.message
        with pytest.raises(ParameterTypeError):
            await state.result()

    async def test_handles_signature_mismatches(
        self, prefect_client, parameterized_flow
    ):
        state = await create_then_begin_flow_run(
            flow=parameterized_flow,
            parameters={"puppy": "a string", "kitty": 42},
            wait_for=None,
            return_type="state",
            client=prefect_client,
            user_thread=threading.current_thread(),
        )
        assert state.type == StateType.FAILED
        assert "Validation of flow parameters failed with error" in state.message
        assert (
            "SignatureMismatchError: Function expects parameters ['dog', 'cat'] but was"
            " provided with parameters ['puppy', 'kitty']"
            in state.message
        )
        with pytest.raises(SignatureMismatchError):
            await state.result()

    async def test_does_not_raise_signature_mismatch_on_missing_default_args(
        self, prefect_client
    ):
        @flow
        def flow_use_and_return_defaults(foo: str = "bar", bar: int = 1):
            """Flow for testing functions"""
            assert foo == "bar"
            assert bar == 1
            return foo, bar

        state = await create_then_begin_flow_run(
            flow=flow_use_and_return_defaults,
            parameters={},
            wait_for=None,
            return_type="state",
            client=prefect_client,
            user_thread=threading.current_thread(),
        )
        assert state.type == StateType.COMPLETED
        assert await state.result() == ("bar", 1)

    async def test_handles_other_errors(
        self, prefect_client, parameterized_flow, monkeypatch
    ):
        def raise_unspecified_exception(*args, **kwargs):
            raise Exception("I am another exception!")

        # Patch validate_parameters to check for other exception case handling
        monkeypatch.setattr(
            prefect.flows.Flow, "validate_parameters", raise_unspecified_exception
        )

        state = await create_then_begin_flow_run(
            flow=parameterized_flow,
            parameters={"puppy": "a string", "kitty": 42},
            wait_for=None,
            return_type="state",
            client=prefect_client,
            user_thread=threading.current_thread(),
        )
        assert state.type == StateType.FAILED
        assert "Validation of flow parameters failed with error" in state.message
        assert "Exception: I am another exception!" in state.message
        with pytest.raises(Exception):
            await state.result()


class TestRetrieveFlowThenBeginFlowRun:
    async def test_handles_bad_parameter_types(
        self, prefect_client, patch_manifest_load, parameterized_flow
    ):
        await patch_manifest_load(parameterized_flow)
        flow_id = await prefect_client.create_flow(parameterized_flow)
        dep_id = await prefect_client.create_deployment(
            flow_id,
            name="test",
            manifest_path="path/file.json",
        )
        new_flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=dep_id, parameters={"dog": [1], "cat": "not an int"}
        )
        state = await retrieve_flow_then_begin_flow_run(
            flow_run_id=new_flow_run.id, user_thread=threading.current_thread()
        )
        assert state.type == StateType.FAILED
        assert "Validation of flow parameters failed with error" in state.message
        assert (
            "ParameterTypeError: Flow run received invalid parameters" in state.message
        )
        assert "dog: str type expected" in state.message
        assert "cat: value is not a valid integer" in state.message
        with pytest.raises(ParameterTypeError):
            await state.result()

    async def test_handles_signature_mismatches(
        self, prefect_client, parameterized_flow
    ):
        state = await create_then_begin_flow_run(
            flow=parameterized_flow,
            parameters={"puppy": "a string", "kitty": 42},
            wait_for=None,
            return_type="state",
            client=prefect_client,
            user_thread=threading.current_thread(),
        )
        assert state.type == StateType.FAILED
        assert "Validation of flow parameters failed with error" in state.message
        assert (
            "SignatureMismatchError: Function expects parameters ['dog', 'cat'] but was"
            " provided with parameters ['puppy', 'kitty']"
            in state.message
        )
        with pytest.raises(SignatureMismatchError):
            await state.result()

    async def test_handles_other_errors(
        self, prefect_client, parameterized_flow, monkeypatch
    ):
        def raise_unspecified_exception(*args, **kwargs):
            raise Exception("I am another exception!")

        # Patch validate_parameters to check for other exception case handling
        monkeypatch.setattr(
            prefect.flows.Flow, "validate_parameters", raise_unspecified_exception
        )

        state = await create_then_begin_flow_run(
            flow=parameterized_flow,
            parameters={"puppy": "a string", "kitty": 42},
            wait_for=None,
            return_type="state",
            client=prefect_client,
            user_thread=threading.current_thread(),
        )
        assert state.type == StateType.FAILED
        assert "Validation of flow parameters failed with error" in state.message
        assert "Exception: I am another exception!" in state.message
        with pytest.raises(Exception):
            await state.result()


class TestCreateAndBeginSubflowRun:
    async def test_handles_bad_parameter_types(
        self,
        prefect_client,
        parameterized_flow,
        get_flow_run_context,
    ):
        with await get_flow_run_context():
            state = await create_and_begin_subflow_run(
                flow=parameterized_flow,
                parameters={"dog": [1, 2], "cat": "not an int"},
                wait_for=None,
                return_type="state",
                client=prefect_client,
                user_thread=threading.current_thread(),
            )

        assert state.type == StateType.FAILED
        assert "Validation of flow parameters failed with error" in state.message
        assert (
            "ParameterTypeError: Flow run received invalid parameters" in state.message
        )
        assert "dog: str type expected" in state.message
        assert "cat: value is not a valid integer" in state.message
        with pytest.raises(ParameterTypeError):
            await state.result()

    async def test_handles_signature_mismatches(
        self,
        prefect_client,
        parameterized_flow,
        get_flow_run_context,
    ):
        with await get_flow_run_context():
            state = await create_and_begin_subflow_run(
                flow=parameterized_flow,
                parameters={"puppy": "a string", "kitty": 42},
                wait_for=None,
                return_type="state",
                client=prefect_client,
                user_thread=threading.current_thread(),
            )

        assert state.type == StateType.FAILED
        assert "Validation of flow parameters failed with error" in state.message
        assert (
            "SignatureMismatchError: Function expects parameters ['dog', 'cat'] but was"
            " provided with parameters ['puppy', 'kitty']"
            in state.message
        )
        with pytest.raises(SignatureMismatchError):
            await state.result()

    async def test_handles_other_errors(
        self, prefect_client, parameterized_flow, monkeypatch
    ):
        def raise_unspecified_exception(*args, **kwargs):
            raise Exception("I am another exception!")

        # Patch validate_parameters to check for other exception case handling
        monkeypatch.setattr(
            prefect.flows.Flow, "validate_parameters", raise_unspecified_exception
        )

        state = await create_then_begin_flow_run(
            flow=parameterized_flow,
            parameters={"puppy": "a string", "kitty": 42},
            wait_for=None,
            return_type="state",
            client=prefect_client,
            user_thread=threading.current_thread(),
        )
        assert state.type == StateType.FAILED
        assert "Validation of flow parameters failed with error" in state.message
        assert "Exception: I am another exception!" in state.message
        with pytest.raises(Exception):
            await state.result()


class TestLinkStateToResult:
    @pytest.fixture
    def state(self):
        return State(id=uuid4(), type=StateType.COMPLETED)

    class RandomTestClass:
        pass

    class PydanticTestClass(BaseModel):
        num: int
        list_of_ints: List[int]

    @pytest.mark.parametrize(
        "test_input", [True, False, -5, 0, 1, 256, ..., None, NotImplemented]
    )
    async def test_link_state_to_result_with_untrackables(
        self, test_input, get_flow_run_context, state
    ):
        with await get_flow_run_context() as ctx:
            link_state_to_result(state=state, result=test_input)
            assert ctx.task_run_results == {}

    @pytest.mark.parametrize("test_input", [-6, 257, "Hello", RandomTestClass()])
    async def test_link_state_to_result_with_single_trackables(
        self, get_flow_run_context, test_input, state
    ):
        input_id = id(test_input)

        with await get_flow_run_context() as ctx:
            link_state_to_result(state=state, result=test_input)
            assert ctx.task_run_results == {input_id: state}

    @pytest.mark.parametrize(
        "test_inputs",
        [
            [-6, 257],
            [-42, RandomTestClass()],
            [4200, "Test", RandomTestClass()],
        ],
    )
    async def test_link_state_to_result_with_multiple_unnested_trackables(
        self, get_flow_run_context, test_inputs, state
    ):
        input_ids = []
        with await get_flow_run_context() as ctx:
            for test_input in test_inputs:
                input_ids.append(id(test_input))
                link_state_to_result(state=state, result=test_input)
            assert ctx.task_run_results == {id: state for id in input_ids}

    @pytest.mark.parametrize(
        "test_input",
        [
            [True],
            (False,),
            [1, 2, 3],
            (1, 2, 3),
        ],
    )
    async def test_link_state_to_result_with_list_or_tuple_of_untrackables(
        self, get_flow_run_context, test_input, state
    ):
        with await get_flow_run_context() as ctx:
            link_state_to_result(state=state, result=test_input)
            assert ctx.task_run_results == {id(test_input): state}

    @pytest.mark.parametrize(
        "test_input",
        [
            ["Test", 1, RandomTestClass()],
            ("Test", 1, RandomTestClass()),
        ],
    )
    async def test_link_state_to_result_with_list_or_tuple_of_mixed(
        self, get_flow_run_context, test_input, state
    ):
        with await get_flow_run_context() as ctx:
            link_state_to_result(state=state, result=test_input)
            assert ctx.task_run_results == {
                id(test_input[0]): state,
                id(test_input[2]): state,
                id(test_input): state,
            }

    async def test_link_state_to_result_with_nested_list(
        self, get_flow_run_context, state
    ):
        test_input = [1, [-6, [1, 2, 3]]]

        with await get_flow_run_context() as ctx:
            link_state_to_result(state=state, result=test_input)
            assert ctx.task_run_results == {
                id(test_input): state,
                id(test_input[1]): state,
            }

    async def test_link_state_to_result_with_nested_pydantic_class(
        self, get_flow_run_context, state
    ):
        pydantic_instance = self.PydanticTestClass(num=42, list_of_ints=[1, 257])

        test_input = [-7, pydantic_instance, 1]

        with await get_flow_run_context() as ctx:
            link_state_to_result(state=state, result=test_input)
            assert ctx.task_run_results == {
                id(test_input): state,
                id(test_input[0]): state,
                id(test_input[1]): state,
            }

    async def test_link_state_to_result_with_pydantic_class(
        self, get_flow_run_context, state
    ):
        pydantic_instance = self.PydanticTestClass(num=42, list_of_ints=[1, 257])

        with await get_flow_run_context() as ctx:
            link_state_to_result(state=state, result=pydantic_instance)
            assert ctx.task_run_results == {
                id(pydantic_instance): state,
                id(pydantic_instance.list_of_ints): state,
            }

    @pytest.mark.parametrize(
        "test_input,expected_status",
        [
            (True, True),
            (-5, True),
            (-6, False),
            ("Hello", False),
            (RandomTestClass(), False),
            ([0, 257], True),
            ([False, "Test", RandomTestClass()], True),
            ([-256, RandomTestClass()], False),
            ([-6, 257], False),
            ([-42, RandomTestClass()], False),
            ([4200, "Test", RandomTestClass()], False),
            (PydanticTestClass(num=42, list_of_ints=[1, 2, 3]), True),
            (PydanticTestClass(num=257, list_of_ints=[1, 2, 3]), False),
        ],
    )
    async def test_link_state_to_result_marks_trackability_in_state_details(
        self, get_flow_run_context, test_input, expected_status, state
    ):
        with await get_flow_run_context():
            link_state_to_result(state=state, result=test_input)
            assert state.state_details.untrackable_result == expected_status


class TestAPIHealthcheck:
    @pytest.fixture(autouse=True)
    def reset_cache(self):
        API_HEALTHCHECKS.clear()
        yield

    async def test_healthcheck_for_ephemeral_client(self):
        async with get_client() as client:
            await check_api_reachable(client, fail_message="test")

        # Check caching
        assert "http://ephemeral-prefect/api/" in API_HEALTHCHECKS
        assert isinstance(API_HEALTHCHECKS["http://ephemeral-prefect/api/"], float)

        assert API_HEALTHCHECKS["http://ephemeral-prefect/api/"] == pytest.approx(
            time.monotonic() + 60 * 10, abs=5
        )

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_healthcheck_for_remote_client(self, hosted_api_server):
        async with get_client() as client:
            await check_api_reachable(client, fail_message="test")

        expected_url = hosted_api_server + "/"  # httpx client appends trailing /

        assert expected_url in API_HEALTHCHECKS
        assert isinstance(API_HEALTHCHECKS[expected_url], float)

        assert API_HEALTHCHECKS[expected_url] == pytest.approx(
            time.monotonic() + 60 * 10, abs=10
        )

    async def test_healthcheck_not_reset_within_expiration(self):
        async with get_client() as client:
            await check_api_reachable(client, fail_message="test")
            value = API_HEALTHCHECKS["http://ephemeral-prefect/api/"]
            for _ in range(2):
                await check_api_reachable(client, fail_message="test")
                assert API_HEALTHCHECKS["http://ephemeral-prefect/api/"] == value

    async def test_healthcheck_reset_after_expiration(self):
        async with get_client() as client:
            await check_api_reachable(client, fail_message="test")
            value = API_HEALTHCHECKS[
                "http://ephemeral-prefect/api/"
            ] = time.monotonic()  # set it to expire now
            await check_api_reachable(client, fail_message="test")
            assert API_HEALTHCHECKS["http://ephemeral-prefect/api/"] != value
            assert API_HEALTHCHECKS["http://ephemeral-prefect/api/"] == pytest.approx(
                time.monotonic() + 60 * 10, abs=5
            )

    async def test_failed_healthcheck(self):
        async with get_client() as client:
            client.api_healthcheck = AsyncMock(return_value=ValueError("test"))
            with pytest.raises(
                RuntimeError,
                match="test. Failed to reach API at http://ephemeral-prefect/api/.",
            ):
                await check_api_reachable(client, fail_message="test")

            # Not cached
            assert "http://ephemeral-prefect/api/" not in API_HEALTHCHECKS
            assert len(API_HEALTHCHECKS.keys()) == 0


def test_flow_call_with_task_runner_duplicate_not_implemented(caplog):
    class MyTaskRunner(BaseTaskRunner):
        @property
        def concurrency_type(self):
            return TaskConcurrencyType.SEQUENTIAL

        def wait(self, *args, **kwargs):
            pass

        def submit(self, *args, **kwargs):
            pass

    @flow(task_runner=MyTaskRunner)
    def my_flow():
        return 1

    assert my_flow() == 1

    assert (
        "Task runner 'MyTaskRunner' does not implement the"
        " `duplicate` method and will fail if used for concurrent execution of"
        " the same flow."
        in caplog.text
    )


def test_subflow_call_with_task_runner_duplicate_not_implemented(caplog):
    class MyTaskRunner(BaseTaskRunner):
        @property
        def concurrency_type(self):
            return TaskConcurrencyType.SEQUENTIAL

        def wait(self, *args, **kwargs):
            pass

        def submit(self, *args, **kwargs):
            pass

    @flow(task_runner=MyTaskRunner)
    def child():
        return 1

    @flow
    def parent():
        return child()

    assert parent() == 1

    assert (
        "Task runner 'MyTaskRunner' does not implement the"
        " `duplicate` method and will fail if used for concurrent execution of"
        " the same flow."
        in caplog.text
    )

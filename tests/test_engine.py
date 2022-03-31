from contextlib import contextmanager
from functools import partial
from unittest.mock import MagicMock

import anyio
import pendulum
import pytest

from prefect import flow, task
from prefect.context import TaskRunContext
from prefect.engine import (
    begin_flow_run,
    orchestrate_flow_run,
    orchestrate_task_run,
    retrieve_flow_then_begin_flow_run,
)
from prefect.exceptions import ParameterTypeError
from prefect.futures import PrefectFuture
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.filters import FlowRunFilter
from prefect.orion.schemas.states import (
    Cancelled,
    Failed,
    Pending,
    Running,
    State,
    StateDetails,
    StateType,
)
from prefect.task_runners import SequentialTaskRunner
from prefect.utilities.testing import AsyncMock, exceptions_equal


class TestOrchestrateTaskRun:
    async def test_waits_until_scheduled_start_time(
        self, orion_client, flow_run, monkeypatch, local_storage_block
    ):
        @task
        def foo():
            return 1

        task_run = await orion_client.create_task_run(
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

        # Mock sleep for a fast test; force transition into a new scheduled state so we
        # don't repeatedly propose the state
        async def reset_scheduled_time(*_):
            await orion_client.set_task_run_state(
                task_run_id=task_run.id,
                state=State(
                    type=StateType.SCHEDULED,
                    state_details=StateDetails(scheduled_time=pendulum.now("utc")),
                ),
                force=True,
            )

        sleep = AsyncMock(side_effect=reset_scheduled_time)
        monkeypatch.setattr("anyio.sleep", sleep)
        state = await orchestrate_task_run(
            task=foo,
            task_run=task_run,
            parameters={},
            wait_for=None,
            result_storage=local_storage_block,
            client=orion_client,
        )

        sleep.assert_awaited_once()
        assert state.is_completed()
        assert state.result() == 1

    async def test_does_not_wait_for_scheduled_time_in_past(
        self, orion_client, flow_run, monkeypatch, local_storage_block
    ):
        @task
        def foo():
            return 1

        task_run = await orion_client.create_task_run(
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

        sleep = AsyncMock()
        monkeypatch.setattr("anyio.sleep", sleep)
        state = await orchestrate_task_run(
            task=foo,
            task_run=task_run,
            parameters={},
            wait_for=None,
            result_storage=local_storage_block,
            client=orion_client,
        )

        sleep.assert_not_called()
        assert state.is_completed()
        assert state.result() == 1

    async def test_waits_for_awaiting_retry_scheduled_time(
        self, monkeypatch, orion_client, flow_run, local_storage_block
    ):
        # Define a task that fails once and then succeeds
        mock = MagicMock()

        @task(retries=1, retry_delay_seconds=43)
        def flaky_function():
            mock()

            if mock.call_count == 2:
                return 1

            raise ValueError("try again, but only once")

        # Create a task run to test
        task_run = await orion_client.create_task_run(
            task=flaky_function,
            flow_run_id=flow_run.id,
            state=Pending(),
            dynamic_key="0",
        )

        # Mock sleep for a fast test; force transition into a new scheduled state so we
        # don't repeatedly propose the state
        async def reset_scheduled_time(*_):
            await orion_client.set_task_run_state(
                task_run_id=task_run.id,
                state=State(
                    type=StateType.SCHEDULED,
                    state_details=StateDetails(scheduled_time=pendulum.now("utc")),
                ),
                force=True,
            )

        sleep = AsyncMock(side_effect=reset_scheduled_time)
        monkeypatch.setattr("anyio.sleep", sleep)

        # Actually run the task
        state = await orchestrate_task_run(
            task=flaky_function,
            task_run=task_run,
            parameters={},
            wait_for=None,
            result_storage=local_storage_block,
            client=orion_client,
        )

        # Check for a proper final result
        assert state.result() == 1

        # Assert that the sleep was called
        # due to network time and rounding, the expected sleep time will be less than
        # 43 seconds so we test a window
        sleep.assert_awaited_once()
        assert 40 < sleep.call_args[0][0] < 43

        # Check expected state transitions
        states = await orion_client.read_task_run_states(task_run.id)
        state_names = [state.type for state in states]
        assert state_names == [
            StateType.PENDING,
            StateType.RUNNING,
            StateType.SCHEDULED,
            StateType.SCHEDULED,  # This is a forced state change to speedup the test
            StateType.RUNNING,
            StateType.COMPLETED,
        ]

    @pytest.mark.parametrize(
        "upstream_task_state", [Pending(), Running(), Cancelled(), Failed()]
    )
    async def test_returns_not_ready_when_any_upstream_futures_resolve_to_incomplete(
        self, orion_client, flow_run, upstream_task_state, local_storage_block
    ):
        # Define a mock to ensure the task was not run
        mock = MagicMock()

        @task
        def my_task(x):
            mock()

        # Create an upstream task run
        upstream_task_run = await orion_client.create_task_run(
            task=my_task,
            flow_run_id=flow_run.id,
            state=upstream_task_state,
            dynamic_key="upstream",
        )
        upstream_task_state.state_details.task_run_id = upstream_task_run.id

        # Create a future to wrap the upstream task, have it resolve to the given
        # incomplete state
        future = PrefectFuture(
            task_run=upstream_task_run,
            task_runner=None,
            _final_state=upstream_task_state,
        )

        # Create a task run to test
        task_run = await orion_client.create_task_run(
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
            result_storage=local_storage_block,
            client=orion_client,
        )

        # The task did not run
        mock.assert_not_called()

        # Check that the state is 'NotReady'
        assert state.is_pending()
        assert state.name == "NotReady"
        assert (
            state.message
            == f"Upstream task run '{upstream_task_run.id}' did not reach a 'COMPLETED' state."
        )

    @pytest.mark.parametrize(
        "upstream_task_state", [Pending(), Running(), Cancelled(), Failed()]
    )
    async def test_states_in_parameters_can_be_incomplete(
        self, orion_client, flow_run, upstream_task_state, local_storage_block
    ):
        # Define a mock to ensure the task was not run
        mock = MagicMock()

        @task
        def my_task(x):
            mock(x)

        # Create a task run to test
        task_run = await orion_client.create_task_run(
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
            parameters={"x": upstream_task_state},
            wait_for=None,
            result_storage=local_storage_block,
            client=orion_client,
        )

        # The task ran with the state as its input
        mock.assert_called_once_with(upstream_task_state)

        # Check that the state completed happily
        assert state.is_completed()


class TestOrchestrateFlowRun:
    async def test_waits_until_scheduled_start_time(
        self, orion_client, monkeypatch, local_storage_block
    ):
        @flow
        def foo():
            return 1

        flow_run = await orion_client.create_flow_run(
            flow=foo,
            state=State(
                type=StateType.SCHEDULED,
                state_details=StateDetails(
                    scheduled_time=pendulum.now("utc").add(minutes=5)
                ),
            ),
        )

        # Mock sleep for a fast test; force transition into a new scheduled state so we
        # don't repeatedly propose the state
        async def reset_scheduled_time(*_):
            await orion_client.set_flow_run_state(
                flow_run_id=flow_run.id,
                state=State(
                    type=StateType.SCHEDULED,
                    state_details=StateDetails(scheduled_time=pendulum.now("utc")),
                ),
                force=True,
            )

        sleep = AsyncMock(side_effect=reset_scheduled_time)
        monkeypatch.setattr("anyio.sleep", sleep)

        state = await orchestrate_flow_run(
            flow=foo,
            flow_run=flow_run,
            parameters={},
            task_runner=SequentialTaskRunner(),
            sync_portal=None,
            result_storage=local_storage_block,
            client=orion_client,
        )

        sleep.assert_awaited_once()
        assert state.result() == 1

    async def test_does_not_wait_for_scheduled_time_in_past(
        self, orion_client, monkeypatch, local_storage_block
    ):
        @flow
        def foo():
            return 1

        flow_run = await orion_client.create_flow_run(
            flow=foo,
            state=State(
                type=StateType.SCHEDULED,
                state_details=StateDetails(
                    scheduled_time=pendulum.now("utc").subtract(minutes=5)
                ),
            ),
        )

        sleep = AsyncMock()
        monkeypatch.setattr("anyio.sleep", sleep)

        with anyio.fail_after(5):
            state = await orchestrate_flow_run(
                flow=foo,
                flow_run=flow_run,
                parameters={},
                task_runner=SequentialTaskRunner(),
                sync_portal=None,
                result_storage=local_storage_block,
                client=orion_client,
            )

        sleep.assert_not_called()
        assert state.result() == 1


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

    async def test_anyio_cancellation_crashes_flow(self, flow_run, orion_client):
        started = anyio.Event()

        @flow
        async def my_flow():
            started.set()
            await anyio.sleep_forever()

        with self.capture_cancellation():
            async with anyio.create_task_group() as tg:
                tg.start_soon(
                    partial(
                        begin_flow_run,
                        flow=my_flow,
                        flow_run=flow_run,
                        parameters={},
                        client=orion_client,
                    )
                )
                await started.wait()
                tg.cancel_scope.cancel()

        flow_run = await orion_client.read_flow_run(flow_run.id)

        assert flow_run.state.is_failed()
        assert flow_run.state.name == "Crashed"
        assert (
            "Execution was cancelled by the runtime environment"
            in flow_run.state.message
        )
        assert exceptions_equal(
            flow_run.state.result(raise_on_failure=False),
            anyio.get_cancelled_exc_class()(),
        )

    async def test_anyio_cancellation_crashes_subflow(self, flow_run, orion_client):
        started = anyio.Event()

        @flow
        async def child_flow():
            started.set()
            await anyio.sleep_forever()

        @flow
        async def parent_flow():
            await child_flow()

        with self.capture_cancellation():
            async with anyio.create_task_group() as tg:
                tg.start_soon(
                    partial(
                        begin_flow_run,
                        flow=parent_flow,
                        parameters={},
                        flow_run=flow_run,
                        client=orion_client,
                    )
                )
                await started.wait()
                tg.cancel_scope.cancel()

        parent_flow_run = await orion_client.read_flow_run(flow_run.id)
        assert parent_flow_run.state.is_failed()
        assert parent_flow_run.state.name == "Crashed"
        assert exceptions_equal(
            parent_flow_run.state.result(raise_on_failure=False),
            anyio.get_cancelled_exc_class()(),
        )

        child_runs = await orion_client.read_flow_runs(
            flow_run_filter=FlowRunFilter(parent_task_run_id=dict(is_null_=False))
        )
        assert len(child_runs) == 1
        child_run = child_runs[0]
        assert child_run.state.is_failed()
        assert child_run.state.name == "Crashed"
        assert (
            "Execution was cancelled by the runtime environment"
            in child_run.state.message
        )

    @pytest.mark.parametrize("interrupt_type", [KeyboardInterrupt, SystemExit])
    async def test_interrupt_in_flow_function_crashes_flow(
        self, flow_run, orion_client, interrupt_type
    ):
        @flow
        async def my_flow():
            raise interrupt_type()

        with pytest.raises(interrupt_type):
            await begin_flow_run(
                flow=my_flow, flow_run=flow_run, parameters={}, client=orion_client
            )

        flow_run = await orion_client.read_flow_run(flow_run.id)
        assert flow_run.state.is_failed()
        assert flow_run.state.name == "Crashed"
        assert "Execution was aborted" in flow_run.state.message
        assert exceptions_equal(
            flow_run.state.result(raise_on_failure=False), interrupt_type()
        )

    @pytest.mark.parametrize("interrupt_type", [KeyboardInterrupt, SystemExit])
    async def test_interrupt_during_orchestration_crashes_flow(
        self, flow_run, orion_client, monkeypatch, interrupt_type
    ):
        monkeypatch.setattr(
            "prefect.client.OrionClient.propose_state",
            MagicMock(side_effect=interrupt_type()),
        )

        @flow
        async def my_flow():
            pass

        with pytest.raises(interrupt_type):
            await begin_flow_run(
                flow=my_flow, flow_run=flow_run, parameters={}, client=orion_client
            )

        flow_run = await orion_client.read_flow_run(flow_run.id)
        assert flow_run.state.is_failed()
        assert flow_run.state.name == "Crashed"
        assert "Execution was aborted" in flow_run.state.message
        with pytest.warns(UserWarning, match="not safe to re-raise"):
            assert exceptions_equal(flow_run.state.result(), interrupt_type())

    @pytest.mark.parametrize("interrupt_type", [KeyboardInterrupt, SystemExit])
    async def test_interrupt_in_flow_function_crashes_subflow(
        self, flow_run, orion_client, interrupt_type
    ):
        @flow
        async def child_flow():
            raise interrupt_type()

        @flow
        async def parent_flow():
            await child_flow()

        with pytest.raises(interrupt_type):
            await begin_flow_run(
                flow=parent_flow, flow_run=flow_run, parameters={}, client=orion_client
            )

        flow_run = await orion_client.read_flow_run(flow_run.id)
        assert flow_run.state.is_failed()
        assert flow_run.state.name == "Crashed"
        assert "Execution was aborted" in flow_run.state.message
        assert exceptions_equal(
            flow_run.state.result(raise_on_failure=False), interrupt_type()
        )

        child_runs = await orion_client.read_flow_runs(
            flow_run_filter=FlowRunFilter(parent_task_run_id=dict(is_null_=False))
        )
        assert len(child_runs) == 1
        child_run = child_runs[0]
        assert child_run.id != flow_run.id
        assert child_run.state.is_failed()
        assert child_run.state.name == "Crashed"
        assert "Execution was aborted" in child_run.state.message

    async def test_flow_timeouts_are_not_crashes(self, flow_run, orion_client):
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
            client=orion_client,
        )
        flow_run = await orion_client.read_flow_run(flow_run.id)

        assert flow_run.state.is_failed()
        assert flow_run.state.name != "Crashed"
        assert "exceeded timeout" in flow_run.state.message

    async def test_timeouts_do_not_hide_crashes(self, flow_run, orion_client):
        """
        Since timeouts capture anyio cancellations, we want to ensure that something
        still ends up in a 'Crashed' state if it is cancelled independently from our
        timeout cancellation.
        """
        started = anyio.Event()

        @flow(timeout_seconds=100)
        async def my_flow():
            started.set()
            await anyio.sleep_forever()

        with self.capture_cancellation():
            async with anyio.create_task_group() as tg:
                tg.start_soon(
                    partial(
                        begin_flow_run,
                        parameters={},
                        flow=my_flow,
                        flow_run=flow_run,
                        client=orion_client,
                    )
                )
                await started.wait()
                tg.cancel_scope.cancel()

        flow_run = await orion_client.read_flow_run(flow_run.id)

        assert flow_run.state.is_failed()
        assert flow_run.state.name == "Crashed"
        assert (
            "Execution was cancelled by the runtime environment"
            in flow_run.state.message
        )


class TestTaskRunCrashes:
    @pytest.mark.parametrize("interrupt_type", [KeyboardInterrupt, SystemExit])
    async def test_interrupt_in_task_function_crashes_task_and_flow(
        self, flow_run, orion_client, interrupt_type
    ):
        @task
        async def my_task():
            raise interrupt_type()

        @flow
        async def my_flow():
            await my_task()

        with pytest.raises(interrupt_type):
            await begin_flow_run(
                flow=my_flow, flow_run=flow_run, parameters={}, client=orion_client
            )

        flow_run = await orion_client.read_flow_run(flow_run.id)
        assert flow_run.state.is_failed()
        assert flow_run.state.name == "Crashed"
        assert "Execution was aborted" in flow_run.state.message
        with pytest.warns(UserWarning, match="not safe to re-raise"):
            assert exceptions_equal(flow_run.state.result(), interrupt_type())

        task_runs = await orion_client.read_task_runs()
        assert len(task_runs) == 1
        task_run = task_runs[0]
        assert task_run.state.is_failed()
        assert task_run.state.name == "Crashed"
        assert "Execution was aborted" in task_run.state.message
        with pytest.warns(UserWarning, match="not safe to re-raise"):
            assert exceptions_equal(task_run.state.result(), interrupt_type())

    @pytest.mark.parametrize("interrupt_type", [KeyboardInterrupt, SystemExit])
    async def test_interrupt_in_task_orchestration_crashes_task_and_flow(
        self, flow_run, orion_client, interrupt_type, monkeypatch
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
                flow=my_flow, flow_run=flow_run, parameters={}, client=orion_client
            )

        flow_run = await orion_client.read_flow_run(flow_run.id)
        assert flow_run.state.is_failed()
        assert flow_run.state.name == "Crashed"
        assert "Execution was aborted" in flow_run.state.message
        with pytest.warns(UserWarning, match="not safe to re-raise"):
            assert exceptions_equal(flow_run.state.result(), interrupt_type())

        task_runs = await orion_client.read_task_runs()
        assert len(task_runs) == 1
        task_run = task_runs[0]
        assert task_run.state.is_failed()
        assert task_run.state.name == "Crashed"
        assert "Execution was aborted" in task_run.state.message
        with pytest.warns(UserWarning, match="not safe to re-raise"):
            assert exceptions_equal(task_run.state.result(), interrupt_type())

    async def test_error_in_task_orchestration_crashes_task_but_not_flow(
        self, flow_run, orion_client, monkeypatch
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
            await my_task()

        # Note exception should not be re-raised
        state = await begin_flow_run(
            flow=my_flow, flow_run=flow_run, parameters={}, client=orion_client
        )

        flow_run = await orion_client.read_flow_run(flow_run.id)
        assert flow_run.state.is_failed()
        assert flow_run.state.name == "Failed"
        assert "1/1 states failed" in flow_run.state.message

        task_run_states = state.result(raise_on_failure=False)
        assert len(task_run_states) == 1
        task_run_state = task_run_states[0]
        assert task_run_state.is_failed()
        assert task_run_state.name == "Crashed"
        assert (
            "Execution was interrupted by an unexpected exception"
            in task_run_state.message
        )
        assert exceptions_equal(
            task_run_state.result(raise_on_failure=False), exception
        )

        # Check that the state was reported to the server
        task_run = await orion_client.read_task_run(
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
            flow_data=DataDocument.encode("cloudpickle", flow),
        )

    async def test_completed_run(self, orion_client):
        @flow
        def my_flow(x: int):
            return x

        deployment_id = await self.create_deployment(orion_client, my_flow)

        flow_run = await orion_client.create_flow_run_from_deployment(
            deployment_id, parameters={"x": 1}
        )

        state = await retrieve_flow_then_begin_flow_run(
            flow_run.id, client=orion_client
        )
        assert state.result() == 1

    async def test_failed_run(self, orion_client):
        @flow
        def my_flow(x: int):
            raise ValueError("test!")

        deployment_id = await self.create_deployment(orion_client, my_flow)

        flow_run = await orion_client.create_flow_run_from_deployment(
            deployment_id, parameters={"x": 1}
        )

        state = await retrieve_flow_then_begin_flow_run(
            flow_run.id, client=orion_client
        )
        assert state.is_failed()
        with pytest.raises(ValueError, match="test!"):
            state.result()

    async def test_parameters_are_cast_to_correct_type(self, orion_client):
        @flow
        def my_flow(x: int):
            return x

        deployment_id = await self.create_deployment(orion_client, my_flow)

        flow_run = await orion_client.create_flow_run_from_deployment(
            deployment_id, parameters={"x": "1"}
        )

        state = await retrieve_flow_then_begin_flow_run(
            flow_run.id, client=orion_client
        )
        assert state.result() == 1

    async def test_state_is_failed_when_parameters_fail_validation(self, orion_client):
        @flow
        def my_flow(x: int):
            return x

        deployment_id = await self.create_deployment(orion_client, my_flow)

        flow_run = await orion_client.create_flow_run_from_deployment(
            deployment_id, parameters={"x": "not-an-int"}
        )

        state = await retrieve_flow_then_begin_flow_run(
            flow_run.id, client=orion_client
        )
        assert state.is_failed()
        assert state.message == "Flow run received invalid parameters."
        with pytest.raises(ParameterTypeError, match="value is not a valid integer"):
            state.result()

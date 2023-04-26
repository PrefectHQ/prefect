import prefect
import pytest

from prefect.utilities.annotations import quote
import prefect.states
import prefect.context
import prefect.runtime
from prefect.exceptions import FailedRun, CancelledRun
from prefect.states import StateType


def test_check_if_running_does_not_raise_in_normal_operation_sync():
    @prefect.task
    def check_task():
        prefect.check_if_running()

    @prefect.flow
    def check_flow():
        check_task()
        return quote(prefect.check_if_running())

    result = check_flow().unwrap()

    # A RUNNING state should be returned by `check_if_running`
    assert isinstance(result, prefect.State)
    assert result.is_running()


async def test_check_if_running_does_not_raise_in_normal_operation_async():
    @prefect.task
    async def acheck_task():
        await prefect.check_if_running()

    @prefect.flow
    async def acheck_flow():
        await acheck_task()
        return quote(await prefect.check_if_running())

    result = (await acheck_flow()).unwrap()

    # A RUNNING state should be returned by `check_if_running`
    assert isinstance(result, prefect.State)
    assert result.is_running()


@pytest.mark.parametrize("state_type", [StateType.CANCELLED, StateType.CANCELLING])
async def test_check_if_running_raises_on_cancelled_flow_state_from_task(state_type):
    @prefect.task
    async def acheck_task():
        async with prefect.get_client() as client:
            await client.set_flow_run_state(
                prefect.runtime.flow_run.id, prefect.states.State(type=state_type)
            )

        with pytest.raises(FailedRun):
            await prefect.check_if_running()

    @prefect.flow
    async def acheck_flow():
        await acheck_task()

    await acheck_flow(return_state=True)


@pytest.mark.parametrize("state_type", [StateType.CANCELLED, StateType.CANCELLING])
async def test_check_if_running_raises_on_cancelled_task_state_from_task(state_type):
    @prefect.task
    async def acheck_task():
        async with prefect.get_client() as client:
            await client.set_task_run_state(
                prefect.runtime.task_run.id, prefect.states.State(type=state_type)
            )
        with pytest.raises(CancelledRun):
            await prefect.check_if_running()

    @prefect.flow
    async def acheck_flow():
        await acheck_task()

    await acheck_flow(return_state=True)


@pytest.mark.parametrize("state_type", [StateType.CANCELLED, StateType.CANCELLING])
async def test_check_if_running_raises_on_cancelled_flow_state_from_flow(state_type):
    @prefect.flow
    async def acheck_flow():
        async with prefect.get_client() as client:
            await client.set_flow_run_state(
                prefect.runtime.flow_run.id, prefect.states.State(type=state_type)
            )

        with pytest.raises(CancelledRun):
            await prefect.check_if_running()

    await acheck_flow(return_state=True)


async def test_check_if_running_raises_on_failed_flow_state_from_task():
    @prefect.task
    async def acheck_task():
        async with prefect.get_client() as client:
            await client.set_flow_run_state(
                prefect.runtime.flow_run.id, prefect.states.Failed()
            )

        with pytest.raises(FailedRun):
            await prefect.check_if_running()

    @prefect.flow
    async def acheck_flow():
        await acheck_task()

    await acheck_flow(return_state=True)


async def test_check_if_running_raises_on_failed_task_state_from_task():
    @prefect.task
    async def acheck_task():
        async with prefect.get_client() as client:
            await client.set_task_run_state(
                prefect.runtime.task_run.id, prefect.states.Failed()
            )
        with pytest.raises(FailedRun):
            await prefect.check_if_running()

    @prefect.flow
    async def acheck_flow():
        await acheck_task()

    await acheck_flow(return_state=True)


async def test_check_if_running_raises_on_failed_flow_state_from_flow():
    @prefect.flow
    async def acheck_flow():
        async with prefect.get_client() as client:
            await client.set_flow_run_state(
                prefect.runtime.flow_run.id, prefect.states.Failed()
            )

        with pytest.raises(FailedRun):
            await prefect.check_if_running()

    await acheck_flow(return_state=True)


async def test_check_if_running_raises_on_pending_flow_state_from_task():
    @prefect.task
    async def acheck_task():
        async with prefect.get_client() as client:
            await client.set_flow_run_state(
                prefect.runtime.flow_run.id, prefect.states.Pending(), force=True
            )

        with pytest.raises(RuntimeError, match="foo"):
            await prefect.check_if_running()

    @prefect.flow
    async def acheck_flow():
        await acheck_task()

    await acheck_flow(return_state=True)


async def test_check_if_running_raises_on_pending_task_state_from_task():
    @prefect.task
    async def acheck_task():
        async with prefect.get_client() as client:
            await client.set_task_run_state(
                prefect.runtime.task_run.id, prefect.states.Pending(), force=True
            )
        with pytest.raises(RuntimeError, match="foo"):
            await prefect.check_if_running()

    @prefect.flow
    async def acheck_flow():
        await acheck_task()

    await acheck_flow(return_state=True)


async def test_check_if_running_raises_on_pending_flow_state_from_flow():
    @prefect.flow
    async def acheck_flow():
        async with prefect.get_client() as client:
            await client.set_flow_run_state(
                prefect.runtime.flow_run.id, prefect.states.Pending(), force=True
            )

        with pytest.raises(RuntimeError, match="foo"):
            await prefect.check_if_running()

    await acheck_flow(return_state=True)

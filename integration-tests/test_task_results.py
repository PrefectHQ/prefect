import time
from uuid import UUID

import anyio

from prefect import flow, task
from prefect.client.orchestration import get_client
from prefect.states import State


@task(persist_result=True)
def hello() -> str:
    return "Hello!"


@flow
def wrapper_flow() -> State[str]:
    return hello(return_state=True)


async def get_state_from_api(task_run_id: UUID) -> State[str]:
    async with get_client() as client:
        task_run = await client.read_task_run(task_run_id)
        assert task_run.state is not None
        return task_run.state


def test_task_results():
    task_state = wrapper_flow()
    assert task_state.result() == "Hello!"
    assert task_state.state_details.task_run_id is not None

    time.sleep(3)  # wait for task run state to propagate

    api_state = anyio.run(get_state_from_api, task_state.state_details.task_run_id)

    result = api_state.result()
    assert result == "Hello!", f"Got {result!r}"

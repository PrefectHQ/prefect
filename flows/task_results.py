import anyio

from prefect import flow, task
from prefect.client.orchestration import get_client


@task(persist_result=True)
def hello():
    return "Hello!"


@flow
def wrapper_flow():
    return hello(return_state=True)


async def get_state_from_api(task_run_id):
    async with get_client() as client:
        task_run = await client.read_task_run(task_run_id)
        return task_run.state


if __name__ == "__main__":
    task_state = wrapper_flow()
    assert task_state.result() == "Hello!"

    api_state = anyio.run(get_state_from_api, task_state.state_details.task_run_id)

    result = api_state.result()
    assert result == "Hello!", f"Got {result!r}"

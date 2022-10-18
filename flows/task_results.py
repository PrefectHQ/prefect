import anyio
from packaging.version import Version

import prefect
from prefect import flow, get_client, task

# The version results were added in
RESULTS_VERSION = "2.6.0"


@task
def hello():
    return "Hello!"


@flow
def wrapper_flow():
    return hello(return_state=True)


if Version(prefect.__version__) >= Version(RESULTS_VERSION):
    hello = hello.with_options(persist_result=True)


async def get_state_from_api(task_run_id):
    async with get_client() as client:
        task_run = await client.read_task_run(task_run_id)
        return task_run.state


if __name__ == "__main__":
    task_state = wrapper_flow()
    assert task_state.result() == "Hello!"

    api_state = anyio.run(get_state_from_api, task_state.state_details.task_run_id)

    if Version(prefect.__version__) >= Version(RESULTS_VERSION):
        result = api_state.result()
        assert result == "Hello!", f"Got {result!r}"
    else:
        from prefect.results import _Result

        result = api_state.result()
        assert isinstance(result, _Result), f"Got {result!r}"

import anyio

from prefect import flow
from prefect.client.orchestration import get_client


@flow(persist_result=True)
def hello():
    return "Hello!"


async def get_state_from_api(flow_run_id):
    async with get_client() as client:
        flow_run = await client.read_flow_run(flow_run_id)
        return flow_run.state


def test_flow_results():
    state = hello(return_state=True)
    assert state.result() == "Hello!", f"Got state {state}"

    api_state = anyio.run(get_state_from_api, state.state_details.flow_run_id)

    result = api_state.result()
    assert result == "Hello!", f"Got {result!r}"

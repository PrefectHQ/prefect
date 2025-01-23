from prefect.client.orchestration import PrefectClient
from prefect.flows import flow
from prefect.runner import Runner
from prefect.states import StateType


class TestRunFlowWithRunner:
    async def test_run_flow_with_runner(self, prefect_client: PrefectClient):
        @flow
        def local_dummy_flow():
            pass

        flow_run = await prefect_client.create_flow_run(flow=local_dummy_flow)
        runner = Runner()
        await runner.run_flow(local_dummy_flow, flow_run)

        flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert flow_run.state.type == StateType.COMPLETED

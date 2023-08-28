import anyio

from prefect import flow, serve
from prefect.client.orchestration import PrefectClient


@flow
def dummy_flow_1():
    pass


@flow
def dummy_flow_2():
    pass


class TestServe:
    async def test_serve_can_create_multiple_deployments(
        self, prefect_client: PrefectClient
    ):
        async with anyio.create_task_group() as tg:
            deployment_1 = dummy_flow_1.to_deployment(__file__)
            deployment_2 = dummy_flow_2.to_deployment(__file__)

            tg.start_soon(serve, deployment_1, deployment_2)

            await anyio.sleep(1)

            tg.cancel_scope.cancel()

            deployment = await prefect_client.read_deployment_by_name(
                name="dummy_flow_1/test_runner"
            )

            assert deployment is not None

            deployment = await prefect_client.read_deployment_by_name(
                name="dummy_flow_2/test_runner"
            )

            assert deployment is not None

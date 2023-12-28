from prefect import flow, get_client
from prefect.runner import Runner


@flow
def dummy_flow_1():
    pass


async def test_runner():
    runner = Runner()

    deployment = await dummy_flow_1.to_deployment(__file__)

    await runner.add_deployment(deployment)

    await runner.start(run_once=True)

    async with get_client() as prefect_client:
        deployment = await prefect_client.read_deployment_by_name(
            name="dummy-flow-1/test_runner"
        )

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment.id
        )

        await runner.start(run_once=True)
        flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)

        assert flow_run.state.is_completed()


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_runner())

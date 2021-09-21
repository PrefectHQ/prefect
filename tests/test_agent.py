from prefect.flows import flow
from prefect.orion.schemas.states import Pending, Scheduled, Running, Completed
import pendulum
from prefect.agent import query_for_ready_flow_runs


async def test_query_for_ready_flow_runs(orion_client, deployment):
    @flow
    def foo():
        pass

    create_run_with_deployment = (
        lambda state: orion_client.create_flow_run_from_deployment(
            deployment, state=state
        )
    )
    fr_id_1 = await create_run_with_deployment(Pending())
    fr_id_2 = await create_run_with_deployment(
        Scheduled(scheduled_time=pendulum.now("utc").subtract(days=1))
    )
    fr_id_3 = await create_run_with_deployment(
        Scheduled(scheduled_time=pendulum.now("utc").add(seconds=5))
    )
    fr_id_4 = await create_run_with_deployment(
        Scheduled(scheduled_time=pendulum.now("utc").add(seconds=5))
    )
    fr_id_5 = await create_run_with_deployment(
        Scheduled(scheduled_time=pendulum.now("utc").add(seconds=20))
    )
    fr_id_6 = await create_run_with_deployment(Running())
    fr_id_7 = await create_run_with_deployment(Completed())
    fr_id_8 = await orion_client.create_flow_run(foo, Scheduled())

    flow_runs = await query_for_ready_flow_runs(
        client=orion_client, prefetch_seconds=10, submitted_ids=[fr_id_4]
    )
    ready_flow_run_ids = {flow_run.id for flow_run in flow_runs}
    # Only include scheduled runs in the past or next prefetch seconds
    # Does not include runs without deployments
    assert ready_flow_run_ids == {fr_id_2, fr_id_3}

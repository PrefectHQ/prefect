from datetime import datetime, timedelta, timezone

import pytest

from prefect.server import models, schemas
from prefect.server.api.ui.flows import SimpleNextFlowRun
from prefect.server.database import orm_models
from prefect.types._datetime import now


@pytest.fixture
async def flow_1(session):
    flow = await models.flows.create_flow(
        session=session,
        flow=schemas.core.Flow(name="my-flow"),
    )
    await session.commit()
    return flow


@pytest.fixture
async def flow_2(session):
    flow = await models.flows.create_flow(
        session=session,
        flow=schemas.core.Flow(name="my-flow-2"),
    )
    await session.commit()
    return flow


@pytest.fixture
async def flow_3(session):
    flow = await models.flows.create_flow(
        session=session,
        flow=schemas.core.Flow(name="my-flow-3"),
    )
    await session.commit()
    return flow


class TestCountDeployments:
    async def test_count_deployments(
        self,
        flow_1: orm_models.Flow,
        flow_2: orm_models.Flow,
        flow_3: orm_models.Flow,
        client,
        session,
    ):
        flow_1_count = 3
        flow_2_count = 2

        for i in range(flow_1_count):
            await models.deployments.create_deployment(
                session=session,
                deployment=schemas.core.Deployment(
                    name=f"My Deployment {i}",
                    flow_id=flow_1.id,
                ),
            )
        for i in range(flow_2_count):
            await models.deployments.create_deployment(
                session=session,
                deployment=schemas.core.Deployment(
                    name=f"My Deployment {i}",
                    flow_id=flow_2.id,
                ),
            )
        await session.commit()

        response = await client.post(
            "/ui/flows/count-deployments",
            json={
                "flow_ids": [
                    str(flow_1.id),
                    str(flow_2.id),
                    str(flow_3.id),
                ]
            },
        )
        assert response.status_code == 200
        assert response.json() == {
            str(flow_1.id): flow_1_count,
            str(flow_2.id): flow_2_count,
            str(flow_3.id): 0,
        }


class TestNextRunsByFlow:
    async def test_next_runs_by_flow_no_runs(
        self,
        flow_1: orm_models.Flow,
        flow_2: orm_models.Flow,
        flow_3: orm_models.Flow,
        client,
    ):
        response = await client.post(
            "/ui/flows/next-runs",
            json={
                "flow_ids": [
                    str(flow_1.id),
                    str(flow_2.id),
                    str(flow_3.id),
                ]
            },
        )
        assert response.status_code == 200
        assert response.json() == {
            str(flow_1.id): None,
            str(flow_2.id): None,
            str(flow_3.id): None,
        }

    async def test_next_runs_by_flow(
        self,
        flow_1: orm_models.Flow,
        flow_2: orm_models.Flow,
        flow_3: orm_models.Flow,
        client,
        session,
    ):
        next_run_flow1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow_1.id,
                flow_version="0.1",
                state=schemas.states.State(
                    type=schemas.states.StateType.SCHEDULED,
                    timestamp=now("UTC"),
                    state_details={"scheduled_time": now("UTC")},
                ),
            ),
        )

        # Not the next run
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow_1.id,
                flow_version="0.1",
                state=schemas.states.State(
                    type=schemas.states.StateType.SCHEDULED,
                    timestamp=datetime.now(timezone.utc) + timedelta(hours=1),
                    state_details={
                        "scheduled_time": datetime.now(timezone.utc)
                        + timedelta(hours=1)
                    },
                ),
            ),
        )

        next_run_flow2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow_2.id,
                flow_version="0.1",
                state=schemas.states.State(
                    type=schemas.states.StateType.SCHEDULED,
                    timestamp=datetime.now(timezone.utc) + timedelta(hours=1),
                    state_details={
                        "scheduled_time": datetime.now(timezone.utc)
                        + timedelta(hours=1)
                    },
                ),
            ),
        )

        # Run sooner than the next but not scheduled
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow_2.id,
                flow_version="0.1",
                state=schemas.states.Completed(),
            ),
        )

        await session.commit()

        response = await client.post(
            "/ui/flows/next-runs",
            json={
                "flow_ids": [
                    str(flow_1.id),
                    str(flow_2.id),
                    str(flow_3.id),
                ]
            },
        )

        expected_next_run_workspace1_flow1 = SimpleNextFlowRun(
            id=next_run_flow1.id,
            flow_id=next_run_flow1.flow_id,
            name=next_run_flow1.name,
            state_type=next_run_flow1.state_type,
            state_name=next_run_flow1.state_name,
            next_scheduled_start_time=next_run_flow1.next_scheduled_start_time,
        ).model_dump(mode="json")
        expected_next_run_workspace1_flow2 = SimpleNextFlowRun(
            id=next_run_flow2.id,
            flow_id=next_run_flow2.flow_id,
            name=next_run_flow2.name,
            state_type=next_run_flow2.state_type,
            state_name=next_run_flow2.state_name,
            next_scheduled_start_time=next_run_flow2.next_scheduled_start_time,
        ).model_dump(mode="json")

        assert response.status_code == 200
        assert response.json() == {
            str(flow_1.id): expected_next_run_workspace1_flow1,
            str(flow_2.id): expected_next_run_workspace1_flow2,
            str(flow_3.id): None,
        }

from typing import List

import pytest
from starlette import status

from prefect.server import models, schemas
from prefect.server.api.ui.flow_runs import SimpleFlowRun
from prefect.server.database import orm_models
from prefect.server.schemas import actions, states
from prefect.utilities.pydantic import parse_obj_as


@pytest.fixture
async def flow_runs(flow, session):
    flow_2 = await models.flows.create_flow(
        session=session,
        flow=actions.FlowCreate(name="another-test"),
    )

    # flow run 1 -----------------------------

    flow_run_1 = await models.flow_runs.create_flow_run(
        session=session, flow_run=actions.FlowRunCreate(flow_id=flow.id)
    )
    await models.flow_runs.set_flow_run_state(
        session=session, flow_run_id=flow_run_1.id, state=states.Running()
    )
    await models.flow_runs.set_flow_run_state(
        session=session, flow_run_id=flow_run_1.id, state=states.Completed()
    )

    # flow run 2 -----------------------------

    flow_run_2 = await models.flow_runs.create_flow_run(
        session=session,
        flow_run=actions.FlowRunCreate(flow_id=flow.id),
    )
    await models.flow_runs.set_flow_run_state(
        session=session, flow_run_id=flow_run_2.id, state=states.Running()
    )
    await models.flow_runs.set_flow_run_state(
        session=session, flow_run_id=flow_run_2.id, state=states.Failed()
    )

    # flow run 3 -----------------------------

    flow_run_3 = await models.flow_runs.create_flow_run(
        session=session,
        flow_run=actions.FlowRunCreate(flow_id=flow_2.id),
    )
    await models.flow_runs.set_flow_run_state(
        session=session, flow_run_id=flow_run_3.id, state=states.Running()
    )

    await session.commit()
    return [flow_run_1, flow_run_2, flow_run_3]


class TestReadFlowRunHistory:
    async def test_read_flow_runs_200(self, flow_runs, client):
        response = await client.post("/ui/flow_runs/history")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 3

    async def test_read_flow_runs(self, flow_runs, client):
        response = await client.post("/ui/flow_runs/history", json=dict(sort="ID_DESC"))
        flow_runs = sorted(flow_runs, key=lambda x: x.id, reverse=True)
        data = parse_obj_as(List[SimpleFlowRun], response.json())
        for i in range(3):
            assert data[i].id == flow_runs[i].id
            assert data[i].state_type == flow_runs[i].state_type
            assert data[i].timestamp == flow_runs[i].expected_start_time
            # less than or equal because this is dynamically computed for running states
            assert data[i].duration <= flow_runs[i].estimated_run_time


class TestFlowRunsCountTaskRuns:
    async def test_count_task_runs(
        self,
        flow_run: orm_models.FlowRun,
        client,
        session,
    ):
        task_runs_count = 3

        for i in range(task_runs_count):
            await models.task_runs.create_task_run(
                session=session,
                task_run=schemas.core.TaskRun(
                    flow_run_id=flow_run.id,
                    name=f"dummy-{i}",
                    task_key=f"dummy-{i}",
                    dynamic_key=f"dummy-{i}",
                ),
            )

        await session.commit()

        response = await client.post(
            "ui/flow_runs/count-task-runs",
            json={
                "flow_run_ids": [
                    str(flow_run.id),
                ]
            },
        )

        assert response.status_code == 200

        assert response.json() == {
            str(flow_run.id): task_runs_count,
        }

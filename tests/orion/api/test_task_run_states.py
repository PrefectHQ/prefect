from uuid import uuid4

import pendulum
import pytest

from prefect.orion import models, schemas


class TestReadTaskRunStateById:
    async def test_read_task_run_state(self, task_run, client, session):
        # create a flow run state to read
        result = await models.task_run_states.set_task_run_state(
            session=session,
            task_run_id=task_run.id,
            state=schemas.states.Running(),
        )
        await session.commit()

        # make sure we can read the state
        task_run_state_id = result.state.id
        response = await client.get(f"/task_run_states/{task_run_state_id}")
        assert response.status_code == 200
        assert response.json()["id"] == str(task_run_state_id)

    async def test_read_task_run_state_returns_404_if_does_not_exist(self, client):
        response = await client.get(f"/task_run_states/{uuid4()}")
        assert response.status_code == 404


class TestReadTaskRunStateByTaskRunId:
    async def test_read_task_run_state(self, task_run, task_run_states, client):
        response = await client.get(
            "/task_run_states/", params=dict(task_run_id=task_run.id)
        )
        assert response.status_code == 200
        response_state_ids = {state["id"] for state in response.json()}
        assert response_state_ids == set([str(state.id) for state in task_run_states])

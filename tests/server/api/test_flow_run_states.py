from uuid import uuid4

from starlette import status

from prefect.server import models, schemas


class TestReadFlowRunStateById:
    async def test_read_flow_run_state(self, flow_run, client, session):
        # create a flow run state to read
        result = await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=flow_run.id,
            state=schemas.states.Running(),
        )
        await session.commit()

        # make sure we can read the state
        flow_run_state_id = result.state.id
        response = await client.get(f"/flow_run_states/{flow_run_state_id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == str(flow_run_state_id)

    async def test_read_flow_run_state_returns_404_if_does_not_exist(self, client):
        response = await client.get(f"/flow_run_states/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReadFlowRunStateByFlowRunId:
    async def test_read_flow_run_state(
        self,
        flow_run,
        flow_run_states,
        client,
        session,
    ):
        response = await client.get(
            "/flow_run_states/", params=dict(flow_run_id=str(flow_run.id))
        )
        assert response.status_code == status.HTTP_200_OK
        response_state_ids = {state["id"] for state in response.json()}
        assert response_state_ids == set([str(state.id) for state in flow_run_states])

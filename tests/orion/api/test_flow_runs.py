from uuid import uuid4

import pendulum
import pydantic
import pytest
import sqlalchemy as sa

from prefect.orion import models, schemas
from prefect.orion.orchestration.rules import OrchestrationResult
from prefect.orion.schemas import actions, core, responses, states, data


class TestCreateFlowRun:
    async def test_create_flow_run(self, flow, client, session):
        response = await client.post(
            "/flow_runs/",
            json=actions.FlowRunCreate(
                flow_id=flow.id,
                name="orange you glad i didnt say yellow salamander",
                state=states.Pending(),
            ).dict(json_compatible=True),
        )
        assert response.status_code == 201
        assert response.json()["flow_id"] == str(flow.id)
        assert response.json()["id"]
        assert response.json()["state"]["type"] == "PENDING"
        assert (
            response.json()["name"] == "orange you glad i didnt say yellow salamander"
        )

        flow_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=response.json()["id"]
        )
        assert flow_run.flow_id == flow.id

    async def test_create_flow_run_with_state_sets_timestamp_on_server(
        self, flow, client, session
    ):
        response = await client.post(
            "/flow_runs/",
            json=actions.FlowRunCreate(
                flow_id=flow.id,
                state=states.Completed(timestamp=pendulum.now().add(months=1)),
            ).dict(json_compatible=True),
        )
        assert response.status_code == 201

        flow_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=response.json()["id"]
        )
        # the timestamp was overwritten
        assert flow_run.state.timestamp < pendulum.now()

    async def test_create_flow_run_without_state_yields_default_pending(
        self, flow, client, session
    ):
        response = await client.post("/flow_runs/", json={"flow_id": str(flow.id)})
        assert response.json()["state"]["type"] == "PENDING"

    async def test_create_multiple_flow_runs(self, flow, client, session):

        response1 = await client.post(
            "/flow_runs/",
            json=actions.FlowRunCreate(flow_id=flow.id, state=states.Pending()).dict(
                json_compatible=True
            ),
        )
        response2 = await client.post(
            "/flow_runs/",
            json=actions.FlowRunCreate(flow_id=flow.id, state=states.Pending()).dict(
                json_compatible=True
            ),
        )
        assert response1.status_code == 201
        assert response2.status_code == 201
        assert response1.json()["flow_id"] == str(flow.id)
        assert response2.json()["flow_id"] == str(flow.id)
        assert response1.json()["id"] != response2.json()["id"]

        result = await session.execute(
            sa.select(models.orm.FlowRun.id).filter_by(flow_id=flow.id)
        )
        ids = result.scalars().all()
        assert {response1.json()["id"], response2.json()["id"]} == {str(i) for i in ids}

    async def test_create_flow_run_with_idempotency_key_recovers_original_flow_run(
        self, flow, client, session
    ):
        data = actions.FlowRunCreate(
            flow_id=flow.id, state=states.Pending(), idempotency_key="test-key"
        ).dict(json_compatible=True)
        response1 = await client.post("/flow_runs/", json=data)
        assert response1.status_code == 201

        response2 = await client.post("/flow_runs/", json=data)
        assert response2.status_code == 200
        assert response1.json()["id"] == response2.json()["id"]

    async def test_create_flow_run_with_idempotency_key_across_multiple_flows(
        self, flow, client, session
    ):
        flow2 = models.orm.Flow(name="another flow")
        session.add(flow2)
        await session.commit()

        data = actions.FlowRunCreate(
            flow_id=flow.id, state=states.Pending(), idempotency_key="test-key"
        )
        data2 = actions.FlowRunCreate(
            flow_id=flow2.id, state=states.Pending(), idempotency_key="test-key"
        )
        response1 = await client.post(
            "/flow_runs/", json=data.dict(json_compatible=True)
        )
        assert response1.status_code == 201

        response2 = await client.post(
            "/flow_runs/",
            json=data2.dict(json_compatible=True),
        )
        assert response2.status_code == 201
        assert response1.json()["id"] != response2.json()["id"]

    async def test_create_flow_run_with_subflow_information(
        self, flow, task_run, client, session
    ):
        flow_run_data = actions.FlowRunCreate(
            flow_id=flow.id, parent_task_run_id=task_run.id, state=states.Pending()
        )
        response = await client.post(
            "/flow_runs/", json=flow_run_data.dict(json_compatible=True)
        )

        flow_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=response.json()["id"]
        )
        assert flow_run.parent_task_run_id == task_run.id

    async def test_create_flow_run_with_running_state(self, flow, client, session):
        flow_run_data = actions.FlowRunCreate(
            flow_id=str(flow.id),
            state=states.Running(),
        )
        response = await client.post(
            "/flow_runs/", json=flow_run_data.dict(json_compatible=True)
        )
        flow_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=response.json()["id"]
        )
        assert str(flow_run.id) == response.json()["id"]
        assert flow_run.state.type == flow_run_data.state.type

    async def test_create_flow_run_with_deployment_id(
        self, flow, client, session, flow_function
    ):

        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=core.Deployment(
                name="",
                flow_id=flow.id,
                flow_data=data.DataDocument.encode("cloudpickle", flow_function),
            ),
        )
        await session.commit()

        response = await client.post(
            "/flow_runs/",
            json=actions.FlowRunCreate(
                flow_id=flow.id, deployment_id=deployment.id
            ).dict(json_compatible=True),
        )

        assert response.json()["deployment_id"] == str(deployment.id)


class TestUpdateFlowRun:
    async def test_update_flow_run_succeeds(self, flow, session, client):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, flow_version="1.0"),
        )
        await session.commit()
        now = pendulum.now("UTC")

        response = await client.patch(
            f"flow_runs/{flow_run.id}",
            json=actions.FlowRunUpdate(
                flow_version="The next one", name="not yellow salamander"
            ).dict(json_compatible=True),
        )
        assert response.status_code == 204

        response = await client.get(f"flow_runs/{flow_run.id}")
        updated_flow_run = pydantic.parse_obj_as(schemas.core.FlowRun, response.json())
        assert updated_flow_run.flow_version == "The next one"
        assert updated_flow_run.name == "not yellow salamander"
        assert updated_flow_run.updated > now

    async def test_update_flow_run_does_not_update_if_fields_not_set(
        self, flow, session, client
    ):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, flow_version="1.0"),
        )
        await session.commit()

        response = await client.patch(
            f"flow_runs/{flow_run.id}",
            json={},
        )
        assert response.status_code == 204

        response = await client.get(f"flow_runs/{flow_run.id}")
        updated_flow_run = pydantic.parse_obj_as(schemas.core.FlowRun, response.json())
        assert updated_flow_run.flow_version == "1.0"

    async def test_update_flow_run_raises_error_if_flow_run_not_found(self, client):
        response = await client.patch(
            f"flow_runs/{str(uuid4())}",
            json={},
        )
        assert response.status_code == 404


class TestReadFlowRun:
    async def test_read_flow_run(self, flow, flow_run, client):
        # make sure we we can read the flow run correctly
        response = await client.get(f"/flow_runs/{flow_run.id}")
        assert response.status_code == 200
        assert response.json()["id"] == str(flow_run.id)
        assert response.json()["flow_id"] == str(flow.id)

    async def test_read_flow_run_with_state(self, flow_run, client, session):
        state_id = uuid4()
        (
            await models.flow_runs.set_flow_run_state(
                session=session,
                flow_run_id=flow_run.id,
                state=states.State(id=state_id, type="RUNNING"),
            )
        ).state
        response = await client.get(f"/flow_runs/{flow_run.id}")
        assert flow_run.state.type.value == "RUNNING"
        assert flow_run.state.id == state_id

    async def test_read_flow_run_returns_404_if_does_not_exist(self, client):
        response = await client.get(f"/flow_runs/{uuid4()}")
        assert response.status_code == 404


class TestReadFlowRuns:
    @pytest.fixture
    async def flow_runs(self, flow, session):
        flow_2 = await models.flows.create_flow(
            session=session,
            flow=actions.FlowCreate(name="another-test"),
        )

        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=actions.FlowRunCreate(flow_id=flow.id),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=actions.FlowRunCreate(flow_id=flow.id),
        )
        flow_run_3 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=actions.FlowRunCreate(flow_id=flow_2.id),
        )
        await session.commit()
        return [flow_run_1, flow_run_2, flow_run_3]

    async def test_read_flow_runs(self, flow_runs, client):
        response = await client.post("/flow_runs/filter")
        assert response.status_code == 200
        assert len(response.json()) == 3

    async def test_read_flow_runs_applies_flow_filter(self, flow, flow_runs, client):
        flow_run_filter = dict(
            flows=schemas.filters.FlowFilter(
                id=schemas.filters.FlowFilterId(any_=[flow.id])
            ).dict(json_compatible=True)
        )
        response = await client.post("/flow_runs/filter/", json=flow_run_filter)
        assert response.status_code == 200
        assert len(response.json()) == 2

    async def test_read_flow_runs_applies_flow_run_filter(
        self, flow, flow_runs, client
    ):
        flow_run_filter = dict(
            flow_runs=schemas.filters.FlowRunFilter(
                id=schemas.filters.FlowRunFilterId(any_=[flow_runs[0].id])
            ).dict(json_compatible=True)
        )
        response = await client.post("/flow_runs/filter/", json=flow_run_filter)
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == str(flow_runs[0].id)

    async def test_read_flow_runs_applies_task_run_filter(
        self, flow, flow_runs, client, session
    ):
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.actions.TaskRunCreate(
                flow_run_id=flow_runs[1].id, task_key="my-key", dynamic_key="0"
            ),
        )
        await session.commit()

        flow_run_filter = dict(
            task_runs=schemas.filters.TaskRunFilter(
                id=schemas.filters.TaskRunFilterId(any_=[task_run_1.id])
            ).dict(json_compatible=True)
        )
        response = await client.post("/flow_runs/filter/", json=flow_run_filter)
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == str(flow_runs[1].id)

    async def test_read_flow_runs_applies_limit(self, flow_runs, client):
        response = await client.post("/flow_runs/filter", json=dict(limit=1))
        assert response.status_code == 200
        assert len(response.json()) == 1

    async def test_read_flow_runs_returns_empty_list(self, client):
        response = await client.post("/flow_runs/filter")
        assert response.status_code == 200
        assert response.json() == []

    async def test_read_flow_runs_applies_sort(self, session, flow, client):
        now = pendulum.now()
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.State(
                    type="SCHEDULED",
                    timestamp=now.subtract(minutes=1),
                ),
            ),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.State(
                    type="SCHEDULED",
                    timestamp=now.add(minutes=1),
                ),
            ),
        )
        await session.commit()

        response = await client.post(
            "/flow_runs/filter/",
            json=dict(
                limit=1, sort=schemas.sorting.FlowRunSort.EXPECTED_START_TIME_ASC.value
            ),
        )
        assert response.status_code == 200
        assert response.json()[0]["id"] == str(flow_run_1.id)

        response = await client.post(
            "/flow_runs/filter/",
            json=dict(
                limit=1,
                offset=1,
                sort=schemas.sorting.FlowRunSort.EXPECTED_START_TIME_ASC.value,
            ),
        )
        assert response.status_code == 200
        assert response.json()[0]["id"] == str(flow_run_2.id)

        response = await client.post(
            "/flow_runs/filter/",
            json=dict(
                limit=1, sort=schemas.sorting.FlowRunSort.EXPECTED_START_TIME_DESC.value
            ),
        )
        assert response.status_code == 200
        assert response.json()[0]["id"] == str(flow_run_2.id)

        response = await client.post(
            "/flow_runs/filter/",
            json=dict(
                limit=1,
                offset=1,
                sort=schemas.sorting.FlowRunSort.EXPECTED_START_TIME_DESC.value,
            ),
        )
        assert response.status_code == 200
        assert response.json()[0]["id"] == str(flow_run_1.id)

    @pytest.mark.parametrize(
        "sort", [sort_option.value for sort_option in schemas.sorting.FlowRunSort]
    )
    async def test_read_flow_runs_sort_succeeds_for_all_sort_values(
        self, sort, flow_run, client
    ):
        response = await client.post("/flow_runs/filter", json=dict(sort=sort))
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == str(flow_run.id)


class TestDeleteFlowRuns:
    async def test_delete_flow_runs(self, flow_run, client, session):
        # delete the flow run
        response = await client.delete(f"/flow_runs/{flow_run.id}")
        assert response.status_code == 204

        # make sure it's deleted (first grab its ID)
        flow_run_id = flow_run.id
        session.expire_all()

        run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run_id
        )
        assert run is None
        response = await client.get(f"/flow_runs/{flow_run_id}")
        assert response.status_code == 404

    async def test_delete_flow_run_returns_404_if_does_not_exist(self, client):
        response = await client.delete(f"/flow_runs/{uuid4()}")
        assert response.status_code == 404


class TestSetFlowRunState:
    async def test_set_flow_run_state(self, flow_run, client, session):
        response = await client.post(
            f"/flow_runs/{flow_run.id}/set_state",
            json=dict(state=dict(type="RUNNING", name="Test State")),
        )
        assert response.status_code == 201

        api_response = OrchestrationResult.parse_obj(response.json())
        assert api_response.status == responses.SetStateStatus.ACCEPT

        flow_run_id = flow_run.id
        session.expire(flow_run)

        run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run_id
        )
        assert run.state.type == states.StateType.RUNNING
        assert run.state.name == "Test State"

    async def test_set_flow_run_errors_if_client_provides_timestamp(
        self, flow_run, client
    ):
        response = await client.post(
            f"/flow_runs/{flow_run.id}/set_state",
            json=dict(
                state=dict(
                    type="RUNNING",
                    name="Test State",
                    timestamp=str(pendulum.now().add(months=1)),
                )
            ),
        )
        assert response.status_code == 422

    async def test_set_flow_run_state_force_skips_orchestration(
        self, flow_run, client, session
    ):
        response1 = await client.post(
            f"/flow_runs/{flow_run.id}/set_state",
            json=dict(
                state=dict(
                    type="SCHEDULED",
                    name="Scheduled",
                    state_details=dict(
                        scheduled_time=str(pendulum.now().add(months=1))
                    ),
                )
            ),
        )
        assert response1.status_code == 201

        # trying to enter a running state fails
        response2 = await client.post(
            f"/flow_runs/{flow_run.id}/set_state",
            json=dict(state=dict(type="RUNNING", name="Running")),
        )
        assert response2.status_code == 200
        assert response2.json()["status"] == "WAIT"

        # trying to enter a running state succeeds with force=True
        response2 = await client.post(
            f"/flow_runs/{flow_run.id}/set_state",
            json=dict(state=dict(type="RUNNING", name="Running"), force=True),
        )
        assert response2.status_code == 201
        assert response2.json()["status"] == "ACCEPT"


class TestFlowRunHistory:
    async def test_history_interval_must_be_one_second_or_larger(self, client):
        response = await client.post(
            "/flow_runs/history",
            json=dict(
                history_start=str(pendulum.now()),
                history_end=str(pendulum.now().add(days=1)),
                history_interval_seconds=0.9,
            ),
        )
        assert response.status_code == 422
        assert b"History interval must not be less than 1 second" in response.content

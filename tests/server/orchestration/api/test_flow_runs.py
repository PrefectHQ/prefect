from typing import List, Optional
from unittest import mock
from uuid import UUID, uuid4

import orjson
import pendulum
import pytest
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from prefect import states as client_states
from prefect.client.schemas import actions as client_actions
from prefect.input import RunInput, keyset_from_paused_state
from prefect.server import models, schemas
from prefect.server.schemas import core, responses
from prefect.server.schemas.actions import LogCreate
from prefect.server.schemas.core import TaskRunResult
from prefect.server.schemas.responses import FlowRunResponse, OrchestrationResult
from prefect.server.schemas.states import StateType
from prefect.utilities.pydantic import parse_obj_as


class TestCreateFlowRun:
    async def test_create_flow_run(self, flow, client, session):
        response = await client.post(
            "/flow_runs/",
            json=client_actions.FlowRunCreate(
                flow_id=flow.id,
                name="orange you glad i didn't say yellow salamander",
                state=client_states.Pending().to_state_create(),
            ).model_dump(mode="json"),
        )
        assert response.status_code == status.HTTP_201_CREATED, response.text
        assert response.json()["flow_id"] == str(flow.id)
        assert response.json()["id"]
        assert response.json()["state"]["type"] == "PENDING"
        assert (
            response.json()["name"] == "orange you glad i didn't say yellow salamander"
        )

        flow_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=response.json()["id"]
        )
        assert flow_run.flow_id == flow.id

    async def test_create_flow_run_witout_job_vars_defaults_to_empty(
        self, flow, client, session
    ):
        response = await client.post(
            "/flow_runs/",
            json=client_actions.FlowRunCreate(
                flow_id=flow.id,
                name="",
            ).model_dump(mode="json"),
        )
        assert response.status_code == status.HTTP_201_CREATED, response.text
        assert response.json()["job_variables"] == {}

        flow_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=response.json()["id"]
        )
        assert flow_run.job_variables == {}

    async def test_create_flow_run_with_state_sets_timestamp_on_server(
        self, flow, client, session
    ):
        response = await client.post(
            "/flow_runs/",
            json=client_actions.FlowRunCreate(
                flow_id=flow.id,
                state=client_states.Completed(
                    timestamp=pendulum.now("UTC").add(months=1)
                ).to_state_create(),
            ).model_dump(mode="json"),
        )
        assert response.status_code == status.HTTP_201_CREATED, response.text

        flow_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=response.json()["id"]
        )
        # the timestamp was overwritten
        assert flow_run.state.timestamp < pendulum.now("UTC")

    async def test_create_flow_run_without_state_yields_default_pending(
        self, flow, client, session
    ):
        response = await client.post("/flow_runs/", json={"flow_id": str(flow.id)})
        assert response.json()["state"]["type"] == "PENDING"

    async def test_create_multiple_flow_runs(self, flow, client, session, db):
        response1 = await client.post(
            "/flow_runs/",
            json=client_actions.FlowRunCreate(
                flow_id=flow.id, state=client_states.Pending().to_state_create()
            ).model_dump(mode="json"),
        )
        response2 = await client.post(
            "/flow_runs/",
            json=client_actions.FlowRunCreate(
                flow_id=flow.id, state=client_states.Pending().to_state_create()
            ).model_dump(mode="json"),
        )
        assert response1.status_code == status.HTTP_201_CREATED
        assert response2.status_code == status.HTTP_201_CREATED
        assert response1.json()["flow_id"] == str(flow.id)
        assert response2.json()["flow_id"] == str(flow.id)
        assert response1.json()["id"] != response2.json()["id"]

        result = await session.execute(
            sa.select(db.FlowRun.id).filter_by(flow_id=flow.id)
        )
        ids = result.scalars().all()
        assert {response1.json()["id"], response2.json()["id"]} == {str(i) for i in ids}

    async def test_create_flow_run_with_idempotency_key_recovers_original_flow_run(
        self, flow, client, session
    ):
        data = client_actions.FlowRunCreate(
            flow_id=flow.id,
            state=client_states.Pending().to_state_create(),
            idempotency_key="test-key",
        ).model_dump(mode="json")
        response1 = await client.post("/flow_runs/", json=data)
        assert response1.status_code == 201

        response2 = await client.post("/flow_runs/", json=data)
        assert response2.status_code == status.HTTP_200_OK
        assert response1.json()["id"] == response2.json()["id"]

    async def test_create_flow_run_with_idempotency_key_across_multiple_flows(
        self,
        flow,
        client,
        session,
        db,
    ):
        flow2 = db.Flow(name="another flow")
        session.add(flow2)
        await session.commit()

        data = client_actions.FlowRunCreate(
            flow_id=flow.id,
            state=client_states.Pending().to_state_create(),
            idempotency_key="test-key",
        )
        data2 = client_actions.FlowRunCreate(
            flow_id=flow2.id,
            state=client_states.Pending().to_state_create(),
            idempotency_key="test-key",
        )
        response1 = await client.post("/flow_runs/", json=data.model_dump(mode="json"))
        assert response1.status_code == status.HTTP_201_CREATED

        response2 = await client.post(
            "/flow_runs/",
            json=data2.model_dump(mode="json"),
        )
        assert response2.status_code == status.HTTP_201_CREATED
        assert response1.json()["id"] != response2.json()["id"]

    async def test_create_flow_run_with_subflow_information(
        self, flow, task_run, client, session
    ):
        flow_run_data = client_actions.FlowRunCreate(
            flow_id=flow.id,
            parent_task_run_id=task_run.id,
            state=client_states.Pending().to_state_create(),
        )
        response = await client.post(
            "/flow_runs/", json=flow_run_data.model_dump(mode="json")
        )

        flow_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=response.json()["id"]
        )
        assert flow_run.parent_task_run_id == task_run.id

    async def test_create_flow_run_with_running_state(self, flow, client, session):
        flow_run_data = client_actions.FlowRunCreate(
            flow_id=str(flow.id),
            state=client_states.Running().to_state_create(),
        )
        response = await client.post(
            "/flow_runs/", json=flow_run_data.model_dump(mode="json")
        )
        flow_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=response.json()["id"]
        )
        assert str(flow_run.id) == response.json()["id"]
        assert flow_run.state.type == flow_run_data.state.type

    async def test_create_flow_run_with_deployment_id(
        self,
        flow,
        client,
        session,
    ):
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=core.Deployment(
                name="",
                flow_id=flow.id,
            ),
        )
        await session.commit()

        response = await client.post(
            "/flow_runs/",
            json=client_actions.FlowRunCreate(
                flow_id=flow.id, deployment_id=deployment.id
            ).model_dump(mode="json"),
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
            json=client_actions.FlowRunUpdate(
                flow_version="The next one",
                name="not yellow salamander",
            ).model_dump(mode="json"),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT, response.text

        response = await client.get(f"flow_runs/{flow_run.id}")
        updated_flow_run = parse_obj_as(
            schemas.responses.FlowRunResponse, response.json()
        )
        assert updated_flow_run.flow_version == "The next one"
        assert updated_flow_run.name == "not yellow salamander"
        assert updated_flow_run.updated > now

    async def test_update_flow_run_with_job_vars_but_no_state(
        self, flow, session, client
    ):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, flow_version="1.0"),
        )
        await session.commit()

        job_vars = {"key": "value"}
        response = await client.patch(
            f"flow_runs/{flow_run.id}",
            json=client_actions.FlowRunUpdate(
                name="", job_variables=job_vars
            ).model_dump(mode="json"),
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
        assert (
            "Flow run state is required to update job variables but none exists"
            in response.json()["detail"]
        )

    @pytest.mark.parametrize(
        "state",
        [
            schemas.states.Pending(),
            schemas.states.Running(),
            schemas.states.Failed(),
            schemas.states.Cancelled(),
        ],
    )
    async def test_update_flow_run_with_job_vars_wrong_state(
        self, flow, session, client, state
    ):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                flow_version="1.0",
                state=state,
            ),
        )
        await session.commit()

        job_vars = {"key": "value"}
        response = await client.patch(
            f"flow_runs/{flow_run.id}",
            json=client_actions.FlowRunUpdate(
                name="", job_variables=job_vars
            ).model_dump(mode="json"),
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
        assert (
            f"Job variables for a flow run in state {state.type.name} cannot be updated"
            in response.json()["detail"]
        )

    async def test_update_flow_run_with_job_vars_no_deployment(
        self, flow, session, client
    ):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                flow_version="1.0",
                state=schemas.states.Scheduled(
                    scheduled_time=pendulum.now("UTC").add(days=1)
                ),
            ),
        )
        await session.commit()

        job_vars = {"key": "value"}
        response = await client.patch(
            f"flow_runs/{flow_run.id}",
            json=client_actions.FlowRunUpdate(
                name="", job_variables=job_vars
            ).model_dump(mode="json"),
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
        assert (
            "A deployment for the flow run could not be found"
            in response.json()["detail"]
        )

    async def test_update_flow_run_with_job_vars_deployment_and_scheduled_state(
        self, flow, session, client
    ):
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                flow_id=flow.id,
                parameters={"foo": "bar"},
                tags=["foo", "bar"],
            ),
        )
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                flow_version="1.0",
                state=schemas.states.Scheduled(
                    scheduled_time=pendulum.now("UTC").add(days=1)
                ),
                deployment_id=deployment.id,
            ),
        )
        await session.commit()

        job_vars = {"key": "value"}
        response = await client.patch(
            f"flow_runs/{flow_run.id}",
            json=client_actions.FlowRunUpdate(
                name="", job_variables=job_vars
            ).model_dump(mode="json"),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT, response.text

        response = await client.get(f"flow_runs/{flow_run.id}")
        updated_flow_run = parse_obj_as(
            schemas.responses.FlowRunResponse, response.json()
        )
        assert updated_flow_run.job_variables == job_vars

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
        assert response.status_code == status.HTTP_204_NO_CONTENT, response.text

        response = await client.get(f"flow_runs/{flow_run.id}")
        updated_flow_run = parse_obj_as(
            schemas.responses.FlowRunResponse, response.json()
        )
        assert updated_flow_run.flow_version == "1.0"

    async def test_update_flow_run_raises_error_if_flow_run_not_found(self, client):
        response = await client.patch(
            f"flow_runs/{str(uuid4())}",
            json={},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text


class TestReadFlowRun:
    async def test_read_flow_run(self, flow, flow_run, client):
        # make sure we we can read the flow run correctly
        response = await client.get(f"/flow_runs/{flow_run.id}")
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["id"] == str(flow_run.id)
        assert response.json()["flow_id"] == str(flow.id)
        assert response.json()["deployment_version"] is None

    @pytest.fixture
    async def flow_run_with_deployment_version(self, flow, session):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                flow_version="1.0",
                deployment_version="Deployment Version 1.0",
                state=schemas.states.Pending(),
            ),
        )
        await session.commit()
        return flow_run

    async def test_read_flow_run_with_deployment_version(
        self, flow, flow_run_with_deployment_version, client
    ):
        # make sure we we can read the flow run correctly
        response = await client.get(f"/flow_runs/{flow_run_with_deployment_version.id}")
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["id"] == str(flow_run_with_deployment_version.id)
        assert response.json()["flow_id"] == str(flow.id)
        assert response.json()["deployment_version"] == "Deployment Version 1.0"

    async def test_read_flow_run_like_the_engine_does(self, flow, flow_run, client):
        """Regression test for the hex format of UUIDs in `PREFECT__FLOW_RUN_ID`

        The only route that is requested in this way is `GET /flow_runs/{id}`; other
        methods aren't affected because they are based on prior requests for flow runs
        and will use a fully-formatted UUID with dashes.
        """

        flow_run_id = flow_run.id.hex
        assert "-" not in flow_run_id
        assert len(flow_run_id) == 32

        response = await client.get(f"/flow_runs/{flow_run.id}")
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["id"] == str(flow_run.id)
        assert response.json()["flow_id"] == str(flow.id)

    async def test_read_flow_run_with_invalid_id_is_rejected(self, client):
        """Additional safety check with for the above regression test to confirm that
        we're not attempting query with any old string as a flow run ID."""
        with mock.patch("prefect.server.models.flow_runs.read_flow_run") as mock_read:
            response = await client.get("/flow_runs/THISAINTIT")
            # Ideally this would be a 404, but we're letting FastAPI take care of this
            # at the parameter parsing level, so it's a 422
            assert response.status_code == 422, response.text

        mock_read.assert_not_called()

    async def test_read_flow_run_with_state(self, flow_run, client, session):
        state_id = uuid4()
        (
            await models.flow_runs.set_flow_run_state(
                session=session,
                flow_run_id=flow_run.id,
                state=schemas.states.State(id=state_id, type="RUNNING"),
            )
        ).state
        await client.get(f"/flow_runs/{flow_run.id}")
        assert flow_run.state.type.value == "RUNNING"
        assert flow_run.state.id == state_id

    async def test_read_flow_run_returns_404_if_does_not_exist(self, client):
        response = await client.get(f"/flow_runs/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text


class TestReadFlowRuns:
    @pytest.fixture
    async def flow_runs(self, flow, work_queue_1, session):
        flow_2 = await models.flows.create_flow(
            session=session,
            flow=schemas.actions.FlowCreate(name="another-test"),
        )

        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.actions.FlowRunCreate(
                flow_id=flow.id, name="fr1", tags=["red"]
            ),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.actions.FlowRunCreate(
                flow_id=flow.id, name="fr2", tags=["blue"]
            ),
        )
        flow_run_3 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow_2.id,
                name="fr3",
                tags=["blue", "red"],
                work_queue_id=work_queue_1.id,
            ),
        )
        await session.commit()
        return [flow_run_1, flow_run_2, flow_run_3]

    @pytest.fixture
    async def flow_runs_with_idempotency_key(
        self, flow, work_queue_1, session
    ) -> List[core.FlowRun]:
        """
        Return a list of two `core.FlowRun`'s with different idempotency keys.
        """
        flow_run_1_with_idempotency_key = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.actions.FlowRunCreate(
                flow_id=flow.id,
                name="fr1",
                tags=["red"],
                idempotency_key="my-idempotency-key",
            ),
        )
        flow_run_2_with_a_different_idempotency_key = (
            await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.actions.FlowRunCreate(
                    flow_id=flow.id,
                    name="fr2",
                    tags=["blue"],
                    idempotency_key="a-different-idempotency-key",
                ),
            )
        )
        await session.commit()
        return [
            flow_run_1_with_idempotency_key,
            flow_run_2_with_a_different_idempotency_key,
        ]

    async def test_read_flow_runs(self, flow_runs, client):
        response = await client.post("/flow_runs/filter")
        assert response.status_code == status.HTTP_200_OK, response.text
        assert len(response.json()) == 3
        # return type should be correct
        assert parse_obj_as(List[schemas.responses.FlowRunResponse], response.json())

    async def test_read_flow_runs_work_pool_fields(
        self,
        flow_runs,
        client,
        work_pool,
        work_queue_1,
    ):
        response = await client.post("/flow_runs/filter")
        assert response.status_code == status.HTTP_200_OK, response.text
        assert len(response.json()) == 3
        response = sorted(
            parse_obj_as(List[schemas.responses.FlowRunResponse], response.json()),
            key=lambda fr: fr.name,
        )
        assert response[2].work_pool_name == work_pool.name
        assert response[2].work_queue_name == work_queue_1.name

    async def test_read_flow_runs_applies_flow_filter(self, flow, flow_runs, client):
        flow_run_filter = dict(
            flows=schemas.filters.FlowFilter(
                id=schemas.filters.FlowFilterId(any_=[flow.id])
            ).model_dump(mode="json")
        )
        response = await client.post("/flow_runs/filter", json=flow_run_filter)
        assert response.status_code == status.HTTP_200_OK, response.text
        assert len(response.json()) == 2

    async def test_read_flow_runs_applies_flow_run_filter(
        self, flow, flow_runs, client
    ):
        flow_run_filter = dict(
            flow_runs=schemas.filters.FlowRunFilter(
                id=schemas.filters.FlowRunFilterId(any_=[flow_runs[0].id])
            ).model_dump(mode="json")
        )
        response = await client.post("/flow_runs/filter", json=flow_run_filter)
        assert response.status_code == status.HTTP_200_OK, response.text
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == str(flow_runs[0].id)

    async def test_read_flow_runs_applies_flow_run_idempotency_key_filter(
        self, flow_runs_with_idempotency_key, client
    ):
        """
        This test tests that when we pass a value for idempotency key to the flow run
        filter, we get back the flow run with the matching idempotency key.
        """
        idempotency_key_of_flow_run_we_want_to_retrieve = (
            flow_runs_with_idempotency_key[0].idempotency_key
        )
        flow_run_idempotency_key_filter = dict(
            flow_runs=schemas.filters.FlowRunFilter(
                idempotency_key=schemas.filters.FlowRunFilterIdempotencyKey(
                    any_=[idempotency_key_of_flow_run_we_want_to_retrieve]
                )
            ).model_dump(mode="json")
        )
        response = await client.post(
            "/flow_runs/filter", json=flow_run_idempotency_key_filter
        )
        flow_run_filter_results = response.json()
        assert response.status_code == status.HTTP_200_OK, response.text
        assert (
            len(flow_run_filter_results) == 1
            and len(flow_runs_with_idempotency_key) == 2
        )
        assert flow_run_filter_results[0]["idempotency_key"] == str(
            idempotency_key_of_flow_run_we_want_to_retrieve
        )

    async def test_read_flow_runs_idempotency_key_filter_excludes_idempotency_key(
        self, flow_runs_with_idempotency_key, client
    ):
        """
        This test tests to make sure that when you pass idempotency keys to the not_any_ argument
        of the filter, the filter excludes flow runs having that value for idempotency key
        """
        idempotency_key_of_flow_run_to_exclude: str = flow_runs_with_idempotency_key[
            0
        ].idempotency_key
        idempotency_key_of_flow_run_that_should_be_included: str = (
            flow_runs_with_idempotency_key[1].idempotency_key
        )
        flow_run_idempotency_key_exclude_filter = dict(
            flow_runs=schemas.filters.FlowRunFilter(
                idempotency_key=schemas.filters.FlowRunFilterIdempotencyKey(
                    not_any_=[idempotency_key_of_flow_run_to_exclude]
                )
            ).model_dump(mode="json")
        )
        response = await client.post(
            "/flow_runs/filter", json=flow_run_idempotency_key_exclude_filter
        )
        flow_run_filter_results = response.json()
        assert response.status_code == status.HTTP_200_OK, response.text

        # assert we started with two flow runs from fixture
        assert len(flow_runs_with_idempotency_key) == 2

        # filtering the fixture should result in a single element
        assert len(flow_run_filter_results) == 1

        # make sure the idempotency key we're excluding is not included in the results
        for result in flow_run_filter_results:
            assert result["idempotency_key"] != idempotency_key_of_flow_run_to_exclude

        # make sure the idempotency key we did not exclude is still in the results
        assert flow_run_filter_results[0]["idempotency_key"] == str(
            idempotency_key_of_flow_run_that_should_be_included
        )

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
            ).model_dump(mode="json")
        )
        response = await client.post("/flow_runs/filter", json=flow_run_filter)
        assert response.status_code == status.HTTP_200_OK, response.text
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == str(flow_runs[1].id)

    async def test_read_flow_runs_applies_work_pool_name_filter(
        self, flow_runs, client, work_pool
    ):
        work_pool_filter = dict(
            work_pools=schemas.filters.WorkPoolFilter(
                name=schemas.filters.WorkPoolFilterName(any_=[work_pool.name])
            ).model_dump(mode="json")
        )
        response = await client.post("/flow_runs/filter", json=work_pool_filter)
        assert response.status_code == status.HTTP_200_OK, response.text
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == str(flow_runs[2].id)

    async def test_read_flow_runs_applies_work_queue_id_filter(
        self,
        flow_runs,
        work_queue_1,
        client,
    ):
        work_pool_filter = dict(
            work_pool_queues=schemas.filters.WorkQueueFilter(
                id=schemas.filters.WorkQueueFilterId(any_=[work_queue_1.id])
            ).model_dump(mode="json")
        )
        response = await client.post("/flow_runs/filter", json=work_pool_filter)
        assert response.status_code == status.HTTP_200_OK, response.text
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == str(flow_runs[2].id)

    async def test_read_flow_runs_multi_filter(self, flow, flow_runs, client):
        flow_run_filter = dict(
            flow_runs=dict(tags=dict(all_=["blue"])),
            flows=dict(name=dict(any_=["another-test"])),
            limit=1,
            offset=0,
        )
        response = await client.post("/flow_runs/filter", json=flow_run_filter)
        assert response.status_code == status.HTTP_200_OK, response.text
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == str(flow_runs[2].id)

    async def test_read_flow_runs_applies_limit(self, flow_runs, client):
        response = await client.post("/flow_runs/filter", json=dict(limit=1))
        assert response.status_code == status.HTTP_200_OK, response.text
        assert len(response.json()) == 1

    async def test_read_flow_runs_returns_empty_list(self, client):
        response = await client.post("/flow_runs/filter")
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json() == []

    async def test_read_flow_runs_applies_sort(self, session, flow, client):
        now = pendulum.now("UTC")
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                name="Flow Run 1",
                state=schemas.states.State(
                    type=StateType.SCHEDULED,
                    timestamp=now.subtract(minutes=1),
                ),
            ),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                name="Flow Run 2",
                state=schemas.states.State(
                    type=StateType.SCHEDULED,
                    timestamp=now.add(minutes=1),
                ),
                start_time=now.subtract(minutes=2),
            ),
        )
        await session.commit()

        response = await client.post(
            "/flow_runs/filter",
            json=dict(limit=1, sort=schemas.sorting.FlowRunSort.START_TIME_ASC.value),
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()[0]["id"] == str(flow_run_2.id)

        response = await client.post(
            "/flow_runs/filter",
            json=dict(limit=1, sort=schemas.sorting.FlowRunSort.START_TIME_DESC.value),
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()[0]["id"] == str(flow_run_1.id)

        response = await client.post(
            "/flow_runs/filter",
            json=dict(
                limit=1, sort=schemas.sorting.FlowRunSort.EXPECTED_START_TIME_ASC.value
            ),
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()[0]["id"] == str(flow_run_1.id)

        response = await client.post(
            "/flow_runs/filter",
            json=dict(
                limit=1,
                offset=1,
                sort=schemas.sorting.FlowRunSort.EXPECTED_START_TIME_ASC.value,
            ),
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()[0]["id"] == str(flow_run_2.id)

        response = await client.post(
            "/flow_runs/filter",
            json=dict(
                limit=1, sort=schemas.sorting.FlowRunSort.EXPECTED_START_TIME_DESC.value
            ),
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()[0]["id"] == str(flow_run_2.id)

        response = await client.post(
            "/flow_runs/filter",
            json=dict(
                limit=1,
                offset=1,
                sort=schemas.sorting.FlowRunSort.EXPECTED_START_TIME_DESC.value,
            ),
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()[0]["id"] == str(flow_run_1.id)

        response = await client.post(
            "/flow_runs/filter",
            json=dict(
                limit=1,
                sort=schemas.sorting.FlowRunSort.NAME_ASC.value,
            ),
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()[0]["id"] == str(flow_run_1.id)

        response = await client.post(
            "/flow_runs/filter",
            json=dict(
                limit=1,
                sort=schemas.sorting.FlowRunSort.NAME_DESC.value,
            ),
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()[0]["id"] == str(flow_run_2.id)

    @pytest.mark.parametrize(
        "sort", [sort_option.value for sort_option in schemas.sorting.FlowRunSort]
    )
    async def test_read_flow_runs_sort_succeeds_for_all_sort_values(
        self, sort, flow_run, client
    ):
        response = await client.post("/flow_runs/filter", json=dict(sort=sort))
        assert response.status_code == status.HTTP_200_OK, response.text
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == str(flow_run.id)

    @pytest.fixture
    async def parent_flow_run(self, flow, session):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                flow_version="1.0",
                state=schemas.states.Pending(),
            ),
        )
        await session.commit()
        return flow_run

    @pytest.fixture
    async def child_runs(
        self,
        flow,
        parent_flow_run,
        session,
    ):
        children = []
        for i in range(5):
            dummy_task = await models.task_runs.create_task_run(
                session=session,
                task_run=schemas.core.TaskRun(
                    flow_run_id=parent_flow_run.id,
                    name=f"dummy-{i}",
                    task_key=f"dummy-{i}",
                    dynamic_key=f"dummy-{i}",
                ),
            )
            children.append(
                await models.flow_runs.create_flow_run(
                    session=session,
                    flow_run=schemas.core.FlowRun(
                        flow_id=flow.id,
                        flow_version="1.0",
                        state=schemas.states.Pending(),
                        parent_task_run_id=dummy_task.id,
                    ),
                )
            )
        return children

    @pytest.fixture
    async def grandchild_runs(self, flow, child_runs, session):
        grandchildren = []
        for child in child_runs:
            for i in range(3):
                dummy_task = await models.task_runs.create_task_run(
                    session=session,
                    task_run=schemas.core.TaskRun(
                        flow_run_id=child.id,
                        name=f"dummy-{i}",
                        task_key=f"dummy-{i}",
                        dynamic_key=f"dummy-{i}",
                    ),
                )
                grandchildren.append(
                    await models.flow_runs.create_flow_run(
                        session=session,
                        flow_run=schemas.core.FlowRun(
                            flow_id=flow.id,
                            flow_version="1.0",
                            state=schemas.states.Pending(),
                            parent_task_run_id=dummy_task.id,
                        ),
                    )
                )
        return grandchildren

    async def test_read_subflow_runs(
        self,
        client,
        parent_flow_run,
        child_runs,
        # included to make sure we're only going 1 level deep
        grandchild_runs,
        # included to make sure we're not bringing in extra flow runs
        flow_runs,
    ):
        """We should be able to find all subflow runs of a given flow run."""
        subflow_filter = {
            "flow_runs": schemas.filters.FlowRunFilter(
                parent_flow_run_id=schemas.filters.FlowRunFilterParentFlowRunId(
                    any_=[parent_flow_run.id]
                )
            ).model_dump(mode="json")
        }

        response = await client.post(
            "/flow_runs/filter",
            json=subflow_filter,
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        assert len(response.json()) == len(child_runs)

        returned = {UUID(run["id"]) for run in response.json()}
        expected = {run.id for run in child_runs}
        assert returned == expected

    async def test_read_subflow_runs_non_existant(
        self,
        client,
        # including these to make sure we aren't bringing in extra flow runs
        parent_flow_run,
        child_runs,
        grandchild_runs,
        flow_runs,
    ):
        subflow_filter = {
            "flow_runs": schemas.filters.FlowRunFilter(
                parent_flow_run_id=schemas.filters.FlowRunFilterParentFlowRunId(
                    any_=[uuid4()]
                )
            ).model_dump(mode="json")
        }

        response = await client.post(
            "/flow_runs/filter",
            json=subflow_filter,
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        assert len(response.json()) == 0

    @pytest.fixture
    async def pending_run(self, flow, session):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                flow_version="1.0",
                state=schemas.states.Pending(),
            ),
        )
        await session.commit()
        return flow_run

    @pytest.fixture
    async def scheduled_run(self, flow, session):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                flow_version="1.0",
                state=schemas.states.Scheduled(),
            ),
        )
        await session.commit()
        return flow_run

    async def test_read_flow_runs_filter_include_state_type(
        self,
        pending_run,
        scheduled_run,
        client,
    ):
        # filter for pending runs
        response = await client.post(
            "/flow_runs/filter",
            json={"flow_runs": {"state": {"type": {"any_": ["PENDING"]}}}},
        )
        assert response.status_code == 200

        flow_runs = parse_obj_as(list[FlowRunResponse], response.json())
        assert len(flow_runs) == 1
        assert flow_runs[0].id == pending_run.id

        # filter for scheduled runs
        response = await client.post(
            "/flow_runs/filter",
            json={"flow_runs": {"state": {"type": {"any_": ["SCHEDULED"]}}}},
        )
        assert response.status_code == 200
        flow_runs = parse_obj_as(list[FlowRunResponse], response.json())
        assert len(flow_runs) == 1
        assert flow_runs[0].id == scheduled_run.id

    async def test_read_flow_runs_filter_exclude_state_type(
        self,
        pending_run,
        scheduled_run,
        client,
    ):
        # exclude pending runs
        response = await client.post(
            "/flow_runs/filter",
            json={"flow_runs": {"state": {"type": {"not_any_": ["PENDING"]}}}},
        )
        assert response.status_code == 200
        flow_runs = parse_obj_as(list[FlowRunResponse], response.json())
        assert len(flow_runs) == 1
        assert flow_runs[0].id == scheduled_run.id

        # exclude scheduled runs
        response = await client.post(
            "/flow_runs/filter",
            json={"flow_runs": {"state": {"type": {"not_any_": ["SCHEDULED"]}}}},
        )
        assert response.status_code == 200
        flow_runs = parse_obj_as(list[FlowRunResponse], response.json())
        assert len(flow_runs) == 1
        assert flow_runs[0].id == pending_run.id

    async def test_read_flow_runs_filter_include_state_name(
        self,
        pending_run,
        scheduled_run,
        client,
    ):
        # filter for pending runs
        response = await client.post(
            "/flow_runs/filter",
            json={"flow_runs": {"state": {"name": {"any_": ["Pending"]}}}},
        )
        assert response.status_code == 200
        flow_runs = parse_obj_as(list[FlowRunResponse], response.json())
        assert len(flow_runs) == 1
        assert flow_runs[0].id == pending_run.id

        # filter for scheduled runs
        response = await client.post(
            "/flow_runs/filter",
            json={"flow_runs": {"state": {"name": {"any_": ["Scheduled"]}}}},
        )
        assert response.status_code == 200
        flow_runs = parse_obj_as(list[FlowRunResponse], response.json())
        assert len(flow_runs) == 1
        assert flow_runs[0].id == scheduled_run.id

    async def test_read_flow_runs_filter_exclude_state_name(
        self,
        pending_run,
        scheduled_run,
        client,
    ):
        # exclude pending runs
        response = await client.post(
            "/flow_runs/filter",
            json={"flow_runs": {"state": {"name": {"not_any_": ["Pending"]}}}},
        )
        assert response.status_code == 200
        flow_runs = parse_obj_as(list[FlowRunResponse], response.json())
        assert len(flow_runs) == 1
        assert flow_runs[0].id == scheduled_run.id

        # exclude scheduled runs
        response = await client.post(
            "/flow_runs/filter",
            json={"flow_runs": {"state": {"name": {"not_any_": ["Scheduled"]}}}},
        )
        assert response.status_code == 200
        flow_runs = parse_obj_as(list[FlowRunResponse], response.json())
        assert len(flow_runs) == 1
        assert flow_runs[0].id == pending_run.id


class TestReadFlowRunGraph:
    @pytest.fixture
    async def graph_data(self, session):
        def create_flow(flow):
            return models.flows.create_flow(session=session, flow=flow)

        def create_flow_run(flow_run):
            return models.flow_runs.create_flow_run(session=session, flow_run=flow_run)

        def create_task_run(task_run):
            return models.task_runs.create_task_run(session=session, task_run=task_run)

        flow = await create_flow(flow=core.Flow(name="f-1", tags=["db", "blue"]))

        fr = await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=flow.id,
                tags=["running"],
                state=schemas.states.Completed(),
            )
        )

        prev_tr = None
        for r in range(10):
            tr = await create_task_run(
                core.TaskRun(
                    flow_run_id=fr.id,
                    task_key=str(r),
                    dynamic_key=str(r * 3),
                    state=schemas.states.Completed(),
                    task_inputs=(
                        dict(x=[TaskRunResult(id=prev_tr.id)]) if prev_tr else dict()
                    ),
                )
            )

            prev_tr = tr

        await session.commit()

        return fr

    async def test_read_flow_run_graph(self, flow_run, client):
        response = await client.get(f"/flow_runs/{flow_run.id}/graph")
        assert response.status_code == status.HTTP_200_OK, response.text

    async def test_read_flow_run_graph_returns_dependencies(self, graph_data, client):
        response = await client.get(f"/flow_runs/{graph_data.id}/graph")
        assert len(response.json()) == 10

    async def test_read_flow_run_graph_returns_upstream_dependencies(
        self, graph_data, client
    ):
        def filter_graph(task_run):
            return len(task_run["upstream_dependencies"]) > 0

        response = await client.get(f"/flow_runs/{graph_data.id}/graph")

        # Remove task runs that don't have upstream dependencies, since we know the first created task run doesn't have any
        # but we have no guarantee of ordering
        task_runs = list(filter(filter_graph, response.json()))

        # Make sure we've only removed the root task run
        assert len(task_runs) == 9

        # Test that all task runs in the list have exactly one upstream dependency
        assert all(
            len(
                task_run["upstream_dependencies"]
                if task_run["upstream_dependencies"]
                else []
            )
            == 1
            for task_run in task_runs
        )


class TestDeleteFlowRuns:
    async def test_delete_flow_runs(self, flow_run, client, session):
        # delete the flow run
        response = await client.delete(f"/flow_runs/{flow_run.id}")
        assert response.status_code == 204, response.text

        # make sure it's deleted (first grab its ID)
        flow_run_id = flow_run.id
        session.expire_all()

        run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run_id
        )
        assert run is None
        response = await client.get(f"/flow_runs/{flow_run_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text

    async def test_delete_flow_run_returns_404_if_does_not_exist(self, client):
        response = await client.delete(f"/flow_runs/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text

    @pytest.mark.parametrize(
        "state_type,expected_slots",
        [
            ("PENDING", 0),
            ("RUNNING", 0),
            ("CANCELLING", 0),
            *[
                (type, 1)
                for type in schemas.states.StateType
                if type not in ("PENDING", "RUNNING", "CANCELLING")
            ],
        ],
    )
    async def test_delete_flow_run_releases_concurrency_slots(
        self,
        client,
        session,
        flow,
        deployment_with_concurrency_limit,
        state_type,
        expected_slots,
    ):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                deployment_id=deployment_with_concurrency_limit.id,
                state=schemas.states.State(
                    type=state_type,
                ),
            ),
        )

        # Take one active slot
        await models.concurrency_limits_v2.bulk_increment_active_slots(
            session=session,
            concurrency_limit_ids=[
                deployment_with_concurrency_limit.concurrency_limit_id
            ],
            slots=1,
        )

        await session.commit()

        concurrency_limit = await models.concurrency_limits_v2.read_concurrency_limit(
            session=session,
            concurrency_limit_id=deployment_with_concurrency_limit.concurrency_limit_id,
        )
        await session.refresh(concurrency_limit)
        assert concurrency_limit.active_slots == 1

        # delete the flow run
        response = await client.delete(f"/flow_runs/{flow_run.id}")
        assert response.status_code == 204, response.text

        await session.refresh(concurrency_limit)
        assert concurrency_limit.active_slots == expected_slots


class TestResumeFlowrun:
    @pytest.fixture
    async def paused_flow_run_waiting_for_input(
        self,
        session,
        flow,
    ):
        class SimpleInput(RunInput):
            approved: bool

        client_state = client_states.Paused(pause_key="1")
        server_state = schemas.states.Paused(pause_key="1")
        keyset = keyset_from_paused_state(client_state)
        server_state.state_details.run_input_keyset = keyset

        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id, flow_version="1.0", state=server_state
            ),
        )

        assert flow_run

        await models.flow_run_input.create_flow_run_input(
            session=session,
            flow_run_input=schemas.core.FlowRunInput(
                flow_run_id=flow_run.id,
                key="paused-1-schema",
                value=orjson.dumps(SimpleInput.model_json_schema()).decode(),
            ),
        )

        await session.commit()

        return flow_run

    @pytest.fixture
    async def paused_flow_run_waiting_for_input_with_default(
        self,
        session,
        flow,
    ):
        class SimpleInput(RunInput):
            how_many: Optional[str] = "5"
            approved: Optional[bool] = True

        client_state = client_states.Paused(pause_key="1")
        server_state = schemas.states.Paused(pause_key="1")
        keyset = keyset_from_paused_state(client_state)
        server_state.state_details.run_input_keyset = keyset

        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id, flow_version="1.0", state=server_state
            ),
        )

        assert flow_run

        await models.flow_run_input.create_flow_run_input(
            session=session,
            flow_run_input=schemas.core.FlowRunInput(
                flow_run_id=flow_run.id,
                key="paused-1-schema",
                value=orjson.dumps(SimpleInput.model_json_schema()).decode(),
            ),
        )

        await session.commit()

        return flow_run

    async def test_resuming_blocking_pauses(
        self, blocking_paused_flow_run, client, session
    ):
        flow_run_id = blocking_paused_flow_run.id
        await client.post(
            f"/flow_runs/{flow_run_id}/resume",
        )

        session.expire_all()
        resumed_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run_id
        )
        assert resumed_run.state.type == "RUNNING"

    async def test_resuming_nonblocking_pauses(
        self, nonblocking_paused_flow_run, client, session
    ):
        flow_run_id = nonblocking_paused_flow_run.id
        await client.post(
            f"/flow_runs/{flow_run_id}/resume",
        )

        session.expire_all()
        resumed_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run_id
        )
        assert resumed_run.state.type == StateType.SCHEDULED

    async def test_cannot_resume_nonblocking_pauses_without_deployment(
        self, nonblockingpaused_flow_run_without_deployment, client, session
    ):
        flow_run_id = nonblockingpaused_flow_run_without_deployment.id
        await client.post(
            f"/flow_runs/{flow_run_id}/resume",
        )

        session.expire_all()
        resumed_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run_id
        )
        assert resumed_run.state.type == "PAUSED"

    async def test_cannot_resume_flow_runs_without_a_state(self, flow_run, client):
        flow_run_id = flow_run.id
        response = await client.post(
            f"/flow_runs/{flow_run_id}/resume",
        )
        assert response.json()["status"] == "ABORT"

    async def test_cannot_resume_flow_runs_not_in_paused_state(
        self, failed_flow_run_with_deployment, client, session
    ):
        flow_run_id = failed_flow_run_with_deployment.id
        response = await client.post(
            f"/flow_runs/{flow_run_id}/resume",
        )
        assert response.json()["status"] == "ABORT"

        session.expire_all()
        resumed_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run_id
        )
        assert resumed_run.state.type == "FAILED"

    async def test_resume_flow_run_waiting_for_input_without_input_succeeds_with_defaults(
        self, client, paused_flow_run_waiting_for_input_with_default
    ):
        response = await client.post(
            f"/flow_runs/{paused_flow_run_waiting_for_input_with_default.id}/resume",
        )
        assert response.status_code == 201, response.text
        assert response.json()["status"] == "ACCEPT"

    async def test_resume_flow_run_waiting_for_input_without_input_fails_if_required(
        self,
        client,
        paused_flow_run_waiting_for_input,
    ):
        response = await client.post(
            f"/flow_runs/{paused_flow_run_waiting_for_input.id}/resume",
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "REJECT"
        assert (
            "'approved' is a required property" in response.json()["details"]["reason"]
        )
        assert response.json()["state"]["id"] == str(
            paused_flow_run_waiting_for_input.state_id
        )

    async def test_cannot_resume_flow_run_waiting_for_input_missing_schema(
        self,
        client,
        paused_flow_run_waiting_for_input,
    ):
        response = await client.delete(
            f"/flow_runs/{paused_flow_run_waiting_for_input.id}/input/paused-1-schema",
        )
        assert response.status_code == 204, response.text

        response = await client.post(
            f"/flow_runs/{paused_flow_run_waiting_for_input.id}/resume",
            json={"run_input": {"approved": True}},
        )

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "REJECT"
        assert response.json()["details"]["reason"] == "Run input schema not found."
        assert response.json()["state"]["id"] == str(
            paused_flow_run_waiting_for_input.state_id
        )

    async def test_cannot_resume_flow_run_waiting_for_input_schema_not_json(
        self,
        client,
        paused_flow_run_waiting_for_input,
    ):
        response = await client.delete(
            f"/flow_runs/{paused_flow_run_waiting_for_input.id}/input/paused-1-schema",
        )
        assert response.status_code == 204, response.text

        response = await client.post(
            f"/flow_runs/{paused_flow_run_waiting_for_input.id}/input",
            json=dict(
                key="paused-1-schema",
                value="not json",
            ),
        )
        assert response.status_code == 201, response.text

        response = await client.post(
            f"/flow_runs/{paused_flow_run_waiting_for_input.id}/resume",
            json={"run_input": {"approved": True}},
        )

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "REJECT"
        assert (
            response.json()["details"]["reason"]
            == "Run input schema is not valid JSON."
        )
        assert response.json()["state"]["id"] == str(
            paused_flow_run_waiting_for_input.state_id
        )

    async def test_cannot_resume_flow_run_waiting_for_input_schema_fails_validation(
        self,
        client,
        paused_flow_run_waiting_for_input,
    ):
        response = await client.post(
            f"/flow_runs/{paused_flow_run_waiting_for_input.id}/resume",
            json={"run_input": {"approved": "not a bool!"}},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "REJECT"
        assert (
            "'not a bool!' is not of type 'boolean'"
            in response.json()["details"]["reason"]
        )
        assert response.json()["state"]["id"] == str(
            paused_flow_run_waiting_for_input.state_id
        )

    async def test_resume_flow_run_waiting_for_input_valid_data(
        self,
        client,
        session,
        paused_flow_run_waiting_for_input,
    ):
        response = await client.post(
            f"/flow_runs/{paused_flow_run_waiting_for_input.id}/resume",
            json={"run_input": {"approved": True}},
        )

        assert response.status_code == 201, response.text
        assert response.json()["status"] == "ACCEPT"

        flow_run_input = await models.flow_run_input.read_flow_run_input(
            session=session,
            flow_run_id=paused_flow_run_waiting_for_input.id,
            key="paused-1-response",
        )

        assert flow_run_input
        assert orjson.loads(flow_run_input.value) == {"approved": True}

    async def test_resume_flow_run_waiting_for_input_with_json_hydrated_input(
        self,
        session,
        client,
        paused_flow_run_waiting_for_input_with_default,
    ):
        response = await client.post(
            f"/flow_runs/{paused_flow_run_waiting_for_input_with_default.id}/resume",
            json={
                "run_input": {"how_many": {"__prefect_kind": "json", "value": '"3"'}}
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["status"] == "ACCEPT"

        flow_run_input = await models.flow_run_input.read_flow_run_input(
            session=session,
            flow_run_id=paused_flow_run_waiting_for_input_with_default.id,
            key="paused-1-response",
        )

        assert flow_run_input
        assert orjson.loads(flow_run_input.value) == {"how_many": "3"}
        assert response.json()["state"]["id"] != str(
            paused_flow_run_waiting_for_input_with_default.state_id
        )

    async def test_resume_flow_run_waiting_for_input_with_jinja_hydrated_input(
        self,
        session,
        client,
        paused_flow_run_waiting_for_input_with_default,
    ):
        response = await client.post(
            f"/flow_runs/{paused_flow_run_waiting_for_input_with_default.id}/resume",
            json={
                "run_input": {
                    "how_many": {"__prefect_kind": "jinja", "template": "{{ 2 + 2 }}"}
                }
            },
        )
        assert response.status_code == 201
        assert response.json()["status"] == "ACCEPT"

        flow_run_input = await models.flow_run_input.read_flow_run_input(
            session=session,
            flow_run_id=paused_flow_run_waiting_for_input_with_default.id,
            key="paused-1-response",
        )

        assert flow_run_input
        assert orjson.loads(flow_run_input.value) == {"how_many": "4"}
        assert response.json()["state"]["id"] != str(
            paused_flow_run_waiting_for_input_with_default.state_id
        )

    async def test_resume_flow_run_waiting_for_input_with_workspace_variable_hydrated_input(
        self,
        session,
        client,
        paused_flow_run_waiting_for_input_with_default,
    ):
        await models.variables.create_variable(
            session,
            schemas.actions.VariableCreate(name="my_variable", value="my_value"),
        )
        await session.commit()

        response = await client.post(
            f"/flow_runs/{paused_flow_run_waiting_for_input_with_default.id}/resume",
            json={
                "run_input": {
                    "how_many": {
                        "__prefect_kind": "workspace_variable",
                        "variable_name": "my_variable",
                    }
                }
            },
        )
        assert response.status_code == 201, str(response.content)
        assert response.json()["status"] == "ACCEPT"

        flow_run_input = await models.flow_run_input.read_flow_run_input(
            session=session,
            flow_run_id=paused_flow_run_waiting_for_input_with_default.id,
            key="paused-1-response",
        )

        assert flow_run_input
        assert orjson.loads(flow_run_input.value) == {"how_many": "my_value"}
        assert response.json()["state"]["id"] != str(
            paused_flow_run_waiting_for_input_with_default.state_id
        )

    async def test_resume_flow_run_waiting_for_input_with_malformed_dehydrated_input(
        self,
        client,
        paused_flow_run_waiting_for_input_with_default,
    ):
        response = await client.post(
            f"/flow_runs/{paused_flow_run_waiting_for_input_with_default.id}/resume",
            json={
                "run_input": {
                    "how_many": {
                        "__prefect_kind": "json",
                        "value": '{"invalid": json}',
                    },
                }
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "REJECT"
        assert response.json()["details"]["reason"].startswith(
            "Error hydrating run input: Invalid JSON"
        )


class TestSetFlowRunState:
    async def test_set_flow_run_state(self, flow_run, client, session):
        response = await client.post(
            f"/flow_runs/{flow_run.id}/set_state",
            json=dict(state=dict(type="RUNNING", name="Test State")),
        )
        assert response.status_code == 201, response.text

        api_response = OrchestrationResult.model_validate(response.json())

        assert api_response.status == responses.SetStateStatus.ACCEPT

        flow_run_id = flow_run.id
        session.expire(flow_run)

        run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run_id
        )
        assert run.state.type == client_states.StateType.RUNNING
        assert run.state.name == "Test State"

    @pytest.mark.parametrize("proposed_state", ["PENDING", "RUNNING"])
    async def test_setting_flow_run_state_twice_aborts(
        self, flow_run, client, session, proposed_state
    ):
        # A multi-agent environment may attempt to orchestrate a run more than once,
        # this test ensures that a 2nd agent cannot re-propose a state that's already
        # been set

        response = await client.post(
            f"/flow_runs/{flow_run.id}/set_state",
            json=dict(state=dict(type=proposed_state, name="Test State")),
        )
        assert response.status_code == 201, response.text

        api_response = OrchestrationResult.model_validate(response.json())
        assert api_response.status == responses.SetStateStatus.ACCEPT

        response = await client.post(
            f"/flow_runs/{flow_run.id}/set_state",
            json=dict(state=dict(type="PENDING", name="Test State")),
        )
        assert response.status_code == 200, response.text

        api_response = OrchestrationResult.model_validate(response.json())
        assert api_response.status == responses.SetStateStatus.ABORT

    async def test_set_flow_run_state_force_skips_orchestration(
        self, flow_run, client, session
    ):
        response1 = await client.post(
            f"/flow_runs/{flow_run.id}/set_state",
            json=dict(
                state=dict(
                    type=StateType.SCHEDULED,
                    name="Scheduled",
                    state_details=dict(
                        scheduled_time=str(pendulum.now("UTC").add(months=1))
                    ),
                )
            ),
        )
        assert response1.status_code == status.HTTP_201_CREATED

        # trying to enter a running state fails
        response2 = await client.post(
            f"/flow_runs/{flow_run.id}/set_state",
            json=dict(state=dict(type="RUNNING", name="Running")),
        )
        assert response2.status_code == status.HTTP_200_OK
        assert response2.json()["status"] == "WAIT"

        # trying to enter a running state succeeds with force=True
        response2 = await client.post(
            f"/flow_runs/{flow_run.id}/set_state",
            json=dict(state=dict(type="RUNNING", name="Running"), force=True),
        )
        assert response2.status_code == status.HTTP_201_CREATED
        assert response2.json()["status"] == "ACCEPT"

    @pytest.mark.parametrize("data", [1, "test", {"foo": "bar"}])
    async def test_set_flow_run_state_accepts_any_jsonable_data(
        self, flow_run, client, session, data
    ):
        response = await client.post(
            f"/flow_runs/{flow_run.id}/set_state",
            json=dict(state=dict(type="COMPLETED", data=data)),
        )
        assert response.status_code == 201, response.text

        api_response = OrchestrationResult.model_validate(response.json())
        assert api_response.status == responses.SetStateStatus.ACCEPT

        flow_run_id = flow_run.id
        session.expire(flow_run)

        run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run_id
        )
        assert run.state.data == data

    async def test_flow_run_receives_wait_until_scheduled_start_time(
        self, flow_run, client, session
    ):
        response = await client.post(
            f"/flow_runs/{flow_run.id}/set_state",
            json=dict(
                state=client_states.Scheduled(
                    scheduled_time=pendulum.now("UTC").add(days=1)
                )
                .to_state_create()
                .model_dump(mode="json")
            ),
        )
        assert response.status_code == 201, response.text
        api_response = OrchestrationResult.model_validate(response.json())
        assert api_response.status == responses.SetStateStatus.ACCEPT

        response = await client.post(
            f"/flow_runs/{flow_run.id}/set_state",
            json=dict(
                state=client_states.Pending().to_state_create().model_dump(mode="json")
            ),
        )
        assert response.status_code == 201, response.text
        api_response = OrchestrationResult.model_validate(response.json())
        assert api_response.status == responses.SetStateStatus.ACCEPT

        response = await client.post(
            f"/flow_runs/{flow_run.id}/set_state",
            json=dict(
                state=client_states.Running().to_state_create().model_dump(mode="json")
            ),
        )
        assert response.status_code == 200, response.text
        api_response = OrchestrationResult.model_validate(response.json())
        assert api_response.status == responses.SetStateStatus.WAIT
        assert (
            0
            <= (
                # Fuzzy comparison
                pendulum.duration(days=1).total_seconds()
                - api_response.details.delay_seconds
            )
            <= 10
        )

    @pytest.fixture
    async def pending_flow_run(self, session, flow):
        model = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                flow_version="0.1",
                state=schemas.states.Pending(),
            ),
        )
        await session.commit()
        return model

    async def test_pending_to_pending(self, pending_flow_run, client):
        response = await client.post(
            f"flow_runs/{pending_flow_run.id}/set_state",
            json=dict(state=dict(type="PENDING", name="Test State")),
        )
        assert response.status_code == 200, response.text

        api_response = OrchestrationResult.model_validate(response.json())
        assert api_response.status == responses.SetStateStatus.ABORT
        assert (
            api_response.details.reason
            == "This run is in a PENDING state and cannot transition to a PENDING"
            " state."
        )

    @pytest.fixture
    async def transition_id(self) -> UUID:
        return uuid4()

    @pytest.fixture
    async def pending_flow_run_with_transition_id(self, session, flow, transition_id):
        model = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                flow_version="0.1",
                state=schemas.states.Pending(
                    state_details={"transition_id": str(transition_id)}
                ),
            ),
        )
        await session.commit()
        return model

    async def test_pending_to_pending_same_transition_id(
        self,
        pending_flow_run_with_transition_id,
        client,
        transition_id,
    ):
        response = await client.post(
            f"flow_runs/{pending_flow_run_with_transition_id.id}/set_state",
            json=dict(
                state=dict(
                    type="PENDING",
                    name="Test State",
                    state_details={"transition_id": str(transition_id)},
                )
            ),
        )
        assert response.status_code == 200, response.text

        api_response = OrchestrationResult.model_validate(response.json())
        assert api_response.status == responses.SetStateStatus.REJECT
        assert (
            api_response.details.reason
            == "This run has already made this state transition."
        )
        # the transition is rejected and the returned state should be the existing state in the db
        assert api_response.state.id == pending_flow_run_with_transition_id.state_id

    @pytest.mark.parametrize(
        "client_version,should_use_orchestration",
        [
            (None, True),
            ("2.19.3", True),
            ("3.0.0rc20", False),
            ("3.0.0", False),
            ("3.0.1", False),
            ("3.0.2", False),
            ("3.0.3", False),
            ("3.0.4", True),
        ],
    )
    async def test_set_flow_run_state_uses_deployment_concurrency_orchestration_for_certain_client_versions(
        self,
        client_version,
        should_use_orchestration,
        client,
        flow_run_with_concurrency_limit,
    ):
        # Ensure that setting the flow run state uses new concurrency rules
        # for older (2.x) clients and 3.x clients other than the ones with
        # worker handling for deployment concurrency.
        with mock.patch(
            "prefect.server.orchestration.core_policy.SecureFlowConcurrencySlots.before_transition"
        ) as mock_before_transition:
            post_kwargs = {
                "json": dict(state=dict(type="PENDING", name="Pending")),
                "headers": {},
            }
            if client_version:
                post_kwargs["headers"][
                    "User-Agent"
                ] = f"prefect/{client_version} (API 2.19.3)"
            response = await client.post(
                f"/flow_runs/{flow_run_with_concurrency_limit.id}/set_state",
                **post_kwargs,
            )
            assert response.status_code == 201

            if should_use_orchestration:
                mock_before_transition.assert_awaited_once()
            else:
                mock_before_transition.assert_not_awaited()


class TestManuallyRetryingFlowRuns:
    async def test_manual_flow_run_retries(
        self, failed_flow_run_with_deployment, client, session
    ):
        assert failed_flow_run_with_deployment.run_count == 1
        assert failed_flow_run_with_deployment.deployment_id
        flow_run_id = failed_flow_run_with_deployment.id

        await client.post(
            f"/flow_runs/{flow_run_id}/set_state",
            json=dict(state=dict(type=StateType.SCHEDULED, name="AwaitingRetry")),
        )

        session.expire_all()
        restarted_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run_id
        )
        assert restarted_run.run_count == 1, "manual retries preserve the run count"
        assert restarted_run.state.type == StateType.SCHEDULED

    async def test_manual_flow_run_retries_succeed_even_if_exceeding_retries_setting(
        self, failed_flow_run_with_deployment_with_no_more_retries, client, session
    ):
        assert failed_flow_run_with_deployment_with_no_more_retries.run_count == 3
        assert (
            failed_flow_run_with_deployment_with_no_more_retries.empirical_policy.retries
            == 2
        )
        assert failed_flow_run_with_deployment_with_no_more_retries.deployment_id
        flow_run_id = failed_flow_run_with_deployment_with_no_more_retries.id

        await client.post(
            f"/flow_runs/{flow_run_id}/set_state",
            json=dict(state=dict(type=StateType.SCHEDULED, name="AwaitingRetry")),
        )

        session.expire_all()
        restarted_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run_id
        )
        assert restarted_run.run_count == 3, "manual retries preserve the run count"
        assert restarted_run.state.type == StateType.SCHEDULED

    async def test_manual_flow_run_retries_allow_arbitrary_state_name(
        self, failed_flow_run_with_deployment, client, session
    ):
        assert failed_flow_run_with_deployment.run_count == 1
        assert failed_flow_run_with_deployment.deployment_id
        flow_run_id = failed_flow_run_with_deployment.id

        await client.post(
            f"/flow_runs/{flow_run_id}/set_state",
            json=dict(state=dict(type=StateType.SCHEDULED, name="FooBar")),
        )

        session.expire_all()
        restarted_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run_id
        )
        assert restarted_run.state.type == StateType.SCHEDULED

    async def test_cannot_restart_flow_run_without_deployment(
        self, failed_flow_run_without_deployment, client, session
    ):
        assert failed_flow_run_without_deployment.run_count == 1
        assert not failed_flow_run_without_deployment.deployment_id
        flow_run_id = failed_flow_run_without_deployment.id

        await client.post(
            f"/flow_runs/{flow_run_id}/set_state",
            json=dict(state=dict(type=StateType.SCHEDULED, name="AwaitingRetry")),
        )

        session.expire_all()
        restarted_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run_id
        )
        assert restarted_run.run_count == 1, "the run count should not change"
        assert restarted_run.state.type == "FAILED"


class TestFlowRunHistory:
    async def test_history_interval_must_be_one_second_or_larger(self, client):
        response = await client.post(
            "/flow_runs/history",
            json=dict(
                history_start=str(pendulum.now("UTC")),
                history_end=str(pendulum.now("UTC").add(days=1)),
                history_interval_seconds=0.9,
            ),
        )
        assert (
            response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        ), response.text
        assert b"History interval must not be less than 1 second" in response.content


class TestFlowRunLateness:
    @pytest.fixture
    def url(self) -> str:
        return "/flow_runs/lateness"

    @pytest.fixture()
    async def late_flow_runs(self, session, flow):
        flow_runs = []
        for i in range(5):
            one_minute_ago = pendulum.now("UTC").subtract(minutes=1)
            flow_run = await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id,
                    state=schemas.states.Scheduled(scheduled_time=one_minute_ago),
                ),
            )
            await models.flow_runs.set_flow_run_state(
                session=session,
                flow_run_id=flow_run.id,
                state=schemas.states.Running(timestamp=one_minute_ago.add(seconds=i)),
            )
            flow_runs.append(flow_run)

            await session.commit()

        return flow_runs

    async def test_average_lateness_no_flow_runs(self, url: str, client):
        response = await client.post(url)
        assert response.status_code == 200, response.text

        # If no flow runs match the filter, the average lateness is null.
        assert response.content == b"null"

    async def test_average_lateness(
        self,
        url: str,
        client,
        late_flow_runs,
    ):
        response = await client.post(url)
        assert response.status_code == 200, response.text

        # The flow runs in `late_flow_runs` are created in a loop and the
        # lateness is the iteration count of the loop. There are 5 flow runs,
        # so avg(0 + 1 + 2 + 3 + 4) == 2.0
        assert response.content == b"2.0"

    async def test_supports_filters(
        self,
        url: str,
        client,
        late_flow_runs,
    ):
        flow_run_ids = [flow_run.id for flow_run in late_flow_runs[-2:]]
        flow_run_filter = schemas.filters.FlowRunFilter(
            id=schemas.filters.FlowRunFilterId(any_=flow_run_ids)
        )
        response = await client.post(
            url, json={"flow_runs": flow_run_filter.model_dump(mode="json")}
        )
        assert response.status_code == 200, response.text

        # The flow runs in `late_flow_runs` are created in a loop and the
        # lateness is the iteration count of the loop. We're only looking at
        # the last two flow runs in that list so avg(3 + 4) == 3.5
        assert response.content == b"3.5"


class TestFlowRunInput:
    @pytest.fixture
    async def flow_run_input(self, session: AsyncSession, flow_run):
        flow_run_input = await models.flow_run_input.create_flow_run_input(
            session=session,
            flow_run_input=schemas.core.FlowRunInput(
                flow_run_id=flow_run.id,
                key="structured-key-1",
                value="really important stuff",
            ),
        )

        await session.commit()

        return flow_run_input

    async def test_create_flow_run_input(
        self, flow_run, client: AsyncClient, session: AsyncSession
    ):
        response = await client.post(
            f"/flow_runs/{flow_run.id}/input",
            json=dict(
                key="structured-key-1",
                value="really important stuff",
            ),
        )

        assert response.status_code == 201, response.text

        flow_run_input = await models.flow_run_input.read_flow_run_input(
            session=session, flow_run_id=flow_run.id, key="structured-key-1"
        )
        assert flow_run_input.flow_run_id == flow_run.id
        assert flow_run_input.key == "structured-key-1"
        assert flow_run_input.value == "really important stuff"

    async def test_404_non_existent_flow_run(
        self, client: AsyncClient, session: AsyncSession
    ):
        not_a_flow_run_id = str(uuid4())
        response = await client.post(
            f"/flow_runs/{not_a_flow_run_id}/input",
            json=dict(
                key="structured-key-1",
                value="really important stuff",
            ),
        )

        assert response.status_code == 404, response.text

        flow_run_input = await models.flow_run_input.read_flow_run_input(
            session=session, flow_run_id=not_a_flow_run_id, key="structured-key-1"
        )
        assert flow_run_input is None

    async def test_409_key_conflict(
        self, flow_run, client: AsyncClient, session: AsyncSession
    ):
        response = await client.post(
            f"/flow_runs/{flow_run.id}/input",
            json=dict(
                key="structured-key-1",
                value="really important stuff",
            ),
        )

        assert response.status_code == 201, response.text

        # Now try to create the same key again, which should result in a 409
        response = await client.post(
            f"/flow_runs/{flow_run.id}/input",
            json=dict(
                key="structured-key-1",
                value="really important stuff",
            ),
        )

        assert response.status_code == 409, response.text

    async def test_filter_flow_run_input(self, client: AsyncClient, flow_run_input):
        response = await client.post(
            f"/flow_runs/{flow_run_input.flow_run_id}/input/filter",
            json={"prefix": "structured"},
        )
        assert response.status_code == 200, response.text
        assert len(response.json()) == 1
        assert (
            schemas.core.FlowRunInput.model_validate(response.json()[0])
            == flow_run_input
        )

    async def test_filter_flow_run_input_limits_response(
        self, client: AsyncClient, session: AsyncSession, flow_run
    ):
        for i in range(100):
            await models.flow_run_input.create_flow_run_input(
                session=session,
                flow_run_input=schemas.core.FlowRunInput(
                    flow_run_id=flow_run.id,
                    key=f"structured-key-{i}",
                    value="really important stuff",
                ),
            )
        await session.commit()

        response = await client.post(
            f"/flow_runs/{flow_run.id}/input/filter",
            json={"prefix": "structured", "limit": 10},
        )
        assert response.status_code == 200, response.text
        assert len(response.json()) == 10
        assert response.json()[0]["key"] == "structured-key-0"

        response = await client.post(
            f"/flow_runs/{flow_run.id}/input/filter",
            json={"prefix": "structured", "limit": 20},
        )

        assert response.status_code == 200, response.text
        assert len(response.json()) == 20
        assert response.json()[-1]["key"] == "structured-key-19"

    async def test_filter_flow_run_input_excludes_keys(
        self,
        client: AsyncClient,
        flow_run_input,
    ):
        response = await client.post(
            f"/flow_runs/{flow_run_input.flow_run_id}/input/filter",
            json={"prefix": "structured", "exclude_keys": [flow_run_input.key]},
        )
        assert response.status_code == 200, response.text
        assert len(response.json()) == 0

    async def test_filter_flow_run_input_no_matches(
        self,
        client: AsyncClient,
        flow_run_input,
    ):
        response = await client.post(
            f"/flow_runs/{flow_run_input.flow_run_id}/input/filter",
            json={"prefix": "big-dawg"},
        )
        assert response.status_code == 200, response.text
        assert len(response.json()) == 0

    async def test_read_flow_run_input(self, client: AsyncClient, flow_run_input):
        response = await client.get(
            f"/flow_runs/{flow_run_input.flow_run_id}/input/{flow_run_input.key}",
        )
        assert response.status_code == 200, response.text
        assert response.content.decode() == flow_run_input.value

    async def test_404_read_flow_run_input_no_matching_input(
        self, client: AsyncClient, flow_run
    ):
        response = await client.get(
            f"/flow_runs/{flow_run.id}/input/missing-key",
        )
        assert response.status_code == 404, response.text

    async def test_delete_flow_run_input(
        self, client: AsyncClient, session: AsyncSession, flow_run_input
    ):
        response = await client.delete(
            f"/flow_runs/{flow_run_input.flow_run_id}/input/{flow_run_input.key}",
        )
        assert response.status_code == 204, response.text

        flow_run_input = await models.flow_run_input.read_flow_run_input(
            session=session,
            flow_run_id=flow_run_input.flow_run_id,
            key=flow_run_input.key,
        )
        assert flow_run_input is None

    async def test_404_delete_flow_run_input_no_matching_input(
        self, client: AsyncClient, flow_run_input
    ):
        response = await client.delete(
            f"/flow_runs/{flow_run_input.flow_run_id}/input/missing-key",
        )
        assert response.status_code == 404, response.text


class TestPaginateFlowRuns:
    @pytest.fixture
    async def flow_runs(self, flow, work_queue_1, session):
        flow_2 = await models.flows.create_flow(
            session=session,
            flow=schemas.actions.FlowCreate(name="another-test"),
        )

        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.actions.FlowRunCreate(
                flow_id=flow.id, name="fr1", tags=["red"]
            ),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.actions.FlowRunCreate(
                flow_id=flow.id, name="fr2", tags=["blue"]
            ),
        )
        flow_run_3 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow_2.id,
                name="fr3",
                tags=["blue", "red"],
                work_queue_id=work_queue_1.id,
            ),
        )
        await session.commit()
        return [flow_run_1, flow_run_2, flow_run_3]

    @pytest.fixture
    async def flow_runs_with_idempotency_key(
        self, flow, work_queue_1, session
    ) -> List[core.FlowRun]:
        """
        Return a list of two `core.FlowRun`'s with different idempotency keys.
        """
        flow_run_1_with_idempotency_key = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.actions.FlowRunCreate(
                flow_id=flow.id,
                name="fr1",
                tags=["red"],
                idempotency_key="my-idempotency-key",
            ),
        )
        flow_run_2_with_a_different_idempotency_key = (
            await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.actions.FlowRunCreate(
                    flow_id=flow.id,
                    name="fr2",
                    tags=["blue"],
                    idempotency_key="a-different-idempotency-key",
                ),
            )
        )
        await session.commit()
        return [
            flow_run_1_with_idempotency_key,
            flow_run_2_with_a_different_idempotency_key,
        ]

    async def test_read_flow_runs(self, flow_runs, client):
        response = await client.post("/flow_runs/paginate")

        assert response.status_code == status.HTTP_200_OK, response.text

        json = response.json()

        assert len(json["results"]) == 3
        assert json["count"] == 3
        assert json["page"] == 1
        assert json["pages"] == 1

        # return type should be correct
        assert parse_obj_as(List[schemas.responses.FlowRunResponse], json["results"])

    async def test_read_flow_runs_work_pool_fields(
        self,
        flow_runs,
        client,
        work_pool,
        work_queue_1,
    ):
        response = await client.post("/flow_runs/paginate")
        results = response.json()["results"]

        assert response.status_code == status.HTTP_200_OK, response.text
        assert len(results) == 3

        results_sorted = sorted(
            parse_obj_as(List[schemas.responses.FlowRunResponse], results),
            key=lambda fr: fr.name,
        )

        assert results_sorted[2].work_pool_name == work_pool.name
        assert results_sorted[2].work_queue_name == work_queue_1.name

    async def test_read_flow_runs_applies_flow_filter(self, flow, flow_runs, client):
        flow_run_filter = dict(
            flows=schemas.filters.FlowFilter(
                id=schemas.filters.FlowFilterId(any_=[flow.id])
            ).model_dump(mode="json")
        )
        response = await client.post("/flow_runs/paginate", json=flow_run_filter)

        assert response.status_code == status.HTTP_200_OK, response.text
        assert len(response.json()["results"]) == 2

    async def test_read_flow_runs_applies_flow_run_filter(
        self, flow, flow_runs, client
    ):
        flow_run_filter = dict(
            flow_runs=schemas.filters.FlowRunFilter(
                id=schemas.filters.FlowRunFilterId(any_=[flow_runs[0].id])
            ).model_dump(mode="json")
        )
        response = await client.post("/flow_runs/paginate", json=flow_run_filter)

        assert response.status_code == status.HTTP_200_OK, response.text

        results = response.json()["results"]

        assert len(results) == 1
        assert results[0]["id"] == str(flow_runs[0].id)

    async def test_read_flow_runs_applies_flow_run_idempotency_key_filter(
        self, flow_runs_with_idempotency_key, client
    ):
        """
        This test tests that when we pass a value for idempotency key to the flow run
        filter, we get back the flow run with the matching idempotency key.
        """
        idempotency_key_of_flow_run_we_want_to_retrieve = (
            flow_runs_with_idempotency_key[0].idempotency_key
        )
        flow_run_idempotency_key_filter = dict(
            flow_runs=schemas.filters.FlowRunFilter(
                idempotency_key=schemas.filters.FlowRunFilterIdempotencyKey(
                    any_=[idempotency_key_of_flow_run_we_want_to_retrieve]
                )
            ).model_dump(mode="json")
        )
        response = await client.post(
            "/flow_runs/paginate", json=flow_run_idempotency_key_filter
        )
        results = response.json()["results"]

        assert response.status_code == status.HTTP_200_OK, response.text

        assert len(results) == 1 and len(flow_runs_with_idempotency_key) == 2

        assert results[0]["idempotency_key"] == str(
            idempotency_key_of_flow_run_we_want_to_retrieve
        )

    async def test_read_flow_runs_idempotency_key_filter_excludes_idempotency_key(
        self, flow_runs_with_idempotency_key, client
    ):
        """
        This test tests to make sure that when you pass idempotency keys to the not_any_ argument
        of the filter, the filter excludes flow runs having that value for idempotency key
        """
        idempotency_key_of_flow_run_to_exclude: str = flow_runs_with_idempotency_key[
            0
        ].idempotency_key
        idempotency_key_of_flow_run_that_should_be_included: str = (
            flow_runs_with_idempotency_key[1].idempotency_key
        )
        flow_run_idempotency_key_exclude_filter = dict(
            flow_runs=schemas.filters.FlowRunFilter(
                idempotency_key=schemas.filters.FlowRunFilterIdempotencyKey(
                    not_any_=[idempotency_key_of_flow_run_to_exclude]
                )
            ).model_dump(mode="json")
        )
        response = await client.post(
            "/flow_runs/paginate", json=flow_run_idempotency_key_exclude_filter
        )

        results = response.json()["results"]

        assert response.status_code == status.HTTP_200_OK, response.text

        # assert we started with two flow runs from fixture
        assert len(flow_runs_with_idempotency_key) == 2

        # filtering the fixture should result in a single element
        assert len(results) == 1

        # make sure the idempotency key we're excluding is not included in the results
        for result in results:
            assert result["idempotency_key"] != idempotency_key_of_flow_run_to_exclude

        # make sure the idempotency key we did not exclude is still in the results
        assert results[0]["idempotency_key"] == str(
            idempotency_key_of_flow_run_that_should_be_included
        )

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
            ).model_dump(mode="json")
        )
        response = await client.post("/flow_runs/paginate", json=flow_run_filter)

        assert response.status_code == status.HTTP_200_OK, response.text

        results = response.json()["results"]

        assert len(results) == 1
        assert results[0]["id"] == str(flow_runs[1].id)

    async def test_read_flow_runs_applies_work_pool_name_filter(
        self, flow_runs, client, work_pool
    ):
        work_pool_filter = dict(
            work_pools=schemas.filters.WorkPoolFilter(
                name=schemas.filters.WorkPoolFilterName(any_=[work_pool.name])
            ).model_dump(mode="json")
        )
        response = await client.post("/flow_runs/paginate", json=work_pool_filter)

        assert response.status_code == status.HTTP_200_OK, response.text

        results = response.json()["results"]

        assert len(results) == 1
        assert results[0]["id"] == str(flow_runs[2].id)

    async def test_read_flow_runs_applies_work_queue_id_filter(
        self,
        flow_runs,
        work_queue_1,
        client,
    ):
        work_pool_filter = dict(
            work_pool_queues=schemas.filters.WorkQueueFilter(
                id=schemas.filters.WorkQueueFilterId(any_=[work_queue_1.id])
            ).model_dump(mode="json")
        )
        response = await client.post("/flow_runs/paginate", json=work_pool_filter)

        assert response.status_code == status.HTTP_200_OK, response.text

        results = response.json()["results"]

        assert len(results) == 1
        assert results[0]["id"] == str(flow_runs[2].id)

    async def test_read_flow_runs_multi_filter(self, flow, flow_runs, client):
        flow_run_filter = dict(
            flow_runs=dict(tags=dict(all_=["blue"])),
            flows=dict(name=dict(any_=["another-test"])),
            limit=1,
            offset=0,
        )
        response = await client.post("/flow_runs/paginate", json=flow_run_filter)

        assert response.status_code == status.HTTP_200_OK, response.text

        results = response.json()["results"]

        assert len(results) == 1
        assert results[0]["id"] == str(flow_runs[2].id)

    async def test_read_flow_runs_applies_limit(self, flow_runs, client):
        response = await client.post("/flow_runs/paginate", json=dict(limit=1))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert len(response.json()["results"]) == 1

    async def test_read_flow_runs_returns_empty_list(self, client):
        response = await client.post("/flow_runs/paginate")

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["results"] == []

    async def test_read_flow_runs_applies_sort(self, session, flow, client):
        now = pendulum.now("UTC")
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                name="Flow Run 1",
                state=schemas.states.State(
                    type=StateType.SCHEDULED,
                    timestamp=now.subtract(minutes=1),
                ),
            ),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                name="Flow Run 2",
                state=schemas.states.State(
                    type=StateType.SCHEDULED,
                    timestamp=now.add(minutes=1),
                ),
                start_time=now.subtract(minutes=2),
            ),
        )
        await session.commit()

        response = await client.post(
            "/flow_runs/paginate",
            json=dict(limit=1, sort=schemas.sorting.FlowRunSort.START_TIME_ASC.value),
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["results"][0]["id"] == str(flow_run_2.id)

        response = await client.post(
            "/flow_runs/paginate",
            json=dict(limit=1, sort=schemas.sorting.FlowRunSort.START_TIME_DESC.value),
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["results"][0]["id"] == str(flow_run_1.id)

        response = await client.post(
            "/flow_runs/paginate",
            json=dict(
                limit=1, sort=schemas.sorting.FlowRunSort.EXPECTED_START_TIME_ASC.value
            ),
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["results"][0]["id"] == str(flow_run_1.id)

        response = await client.post(
            "/flow_runs/paginate",
            json=dict(
                limit=1,
                page=2,
                sort=schemas.sorting.FlowRunSort.EXPECTED_START_TIME_ASC.value,
            ),
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["results"][0]["id"] == str(flow_run_2.id)

        response = await client.post(
            "/flow_runs/paginate",
            json=dict(
                limit=1, sort=schemas.sorting.FlowRunSort.EXPECTED_START_TIME_DESC.value
            ),
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["results"][0]["id"] == str(flow_run_2.id)

        response = await client.post(
            "/flow_runs/paginate",
            json=dict(
                limit=1,
                page=2,
                sort=schemas.sorting.FlowRunSort.EXPECTED_START_TIME_DESC.value,
            ),
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["results"][0]["id"] == str(flow_run_1.id)

        response = await client.post(
            "/flow_runs/paginate",
            json=dict(
                limit=1,
                sort=schemas.sorting.FlowRunSort.NAME_ASC.value,
            ),
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["results"][0]["id"] == str(flow_run_1.id)

        response = await client.post(
            "/flow_runs/paginate",
            json=dict(
                limit=1,
                sort=schemas.sorting.FlowRunSort.NAME_DESC.value,
            ),
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["results"][0]["id"] == str(flow_run_2.id)

    @pytest.mark.parametrize(
        "sort", [sort_option.value for sort_option in schemas.sorting.FlowRunSort]
    )
    async def test_read_flow_runs_sort_succeeds_for_all_sort_values(
        self, sort, flow_run, client
    ):
        response = await client.post("/flow_runs/paginate", json=dict(sort=sort))

        assert response.status_code == status.HTTP_200_OK, response.text

        results = response.json()["results"]

        assert len(results) == 1
        assert results[0]["id"] == str(flow_run.id)

    @pytest.fixture
    async def parent_flow_run(self, flow, session):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                flow_version="1.0",
                state=schemas.states.Pending(),
            ),
        )
        await session.commit()
        return flow_run

    @pytest.fixture
    async def child_runs(
        self,
        flow,
        parent_flow_run,
        session,
    ):
        children = []
        for i in range(5):
            dummy_task = await models.task_runs.create_task_run(
                session=session,
                task_run=schemas.core.TaskRun(
                    flow_run_id=parent_flow_run.id,
                    name=f"dummy-{i}",
                    task_key=f"dummy-{i}",
                    dynamic_key=f"dummy-{i}",
                ),
            )
            children.append(
                await models.flow_runs.create_flow_run(
                    session=session,
                    flow_run=schemas.core.FlowRun(
                        flow_id=flow.id,
                        flow_version="1.0",
                        state=schemas.states.Pending(),
                        parent_task_run_id=dummy_task.id,
                    ),
                )
            )
        return children

    @pytest.fixture
    async def grandchild_runs(self, flow, child_runs, session):
        grandchildren = []
        for child in child_runs:
            for i in range(3):
                dummy_task = await models.task_runs.create_task_run(
                    session=session,
                    task_run=schemas.core.TaskRun(
                        flow_run_id=child.id,
                        name=f"dummy-{i}",
                        task_key=f"dummy-{i}",
                        dynamic_key=f"dummy-{i}",
                    ),
                )
                grandchildren.append(
                    await models.flow_runs.create_flow_run(
                        session=session,
                        flow_run=schemas.core.FlowRun(
                            flow_id=flow.id,
                            flow_version="1.0",
                            state=schemas.states.Pending(),
                            parent_task_run_id=dummy_task.id,
                        ),
                    )
                )
        return grandchildren

    async def test_read_subflow_runs(
        self,
        client,
        parent_flow_run,
        child_runs,
        # included to make sure we're only going 1 level deep
        grandchild_runs,
        # included to make sure we're not bringing in extra flow runs
        flow_runs,
    ):
        """We should be able to find all subflow runs of a given flow run."""
        subflow_filter = {
            "flow_runs": schemas.filters.FlowRunFilter(
                parent_flow_run_id=schemas.filters.FlowRunFilterParentFlowRunId(
                    any_=[parent_flow_run.id]
                )
            ).model_dump(mode="json")
        }

        response = await client.post(
            "/flow_runs/paginate",
            json=subflow_filter,
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert len(response.json()["results"]) == len(child_runs)

        returned = {UUID(run["id"]) for run in response.json()["results"]}
        expected = {run.id for run in child_runs}

        assert returned == expected

    async def test_read_subflow_runs_non_existant(
        self,
        client,
        # including these to make sure we aren't bringing in extra flow runs
        parent_flow_run,
        child_runs,
        grandchild_runs,
        flow_runs,
    ):
        subflow_filter = {
            "flow_runs": schemas.filters.FlowRunFilter(
                parent_flow_run_id=schemas.filters.FlowRunFilterParentFlowRunId(
                    any_=[uuid4()]
                )
            ).model_dump(mode="json")
        }

        response = await client.post(
            "/flow_runs/paginate",
            json=subflow_filter,
        )

        assert response.status_code == status.HTTP_200_OK, response.text
        assert len(response.json()["results"]) == 0


class TestDownloadFlowRunLogs:
    @pytest.fixture
    async def flow_run_1(self, session, flow):
        model = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.actions.FlowRunCreate(flow_id=flow.id, flow_version="0.1"),
        )

        await session.commit()

        return model

    @pytest.fixture
    async def flow_run_2(self, session, flow):
        model = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.actions.FlowRunCreate(flow_id=flow.id, flow_version="0.1"),
        )

        await session.commit()

        return model

    @pytest.fixture
    async def flow_run_1_logs(self, flow_run_1, session):
        NOW = pendulum.now("UTC")

        logs = [
            LogCreate(
                name="prefect.flow_run",
                level=10,
                message=f"Log message {i}",
                timestamp=NOW,
                flow_run_id=flow_run_1.id,
            )
            for i in range(10)
        ]

        await models.logs.create_logs(session=session, logs=logs)

        await session.commit()

        return logs

    @pytest.fixture
    async def flow_run_2_logs(self, flow_run_2, session):
        NOW = pendulum.now("UTC")

        logs = [
            LogCreate(
                name="prefect.flow_run",
                level=10,
                message=f"Log message {i}",
                timestamp=NOW,
                flow_run_id=flow_run_2.id,
            )
            for i in range(10)
        ]

        await models.logs.create_logs(session=session, logs=logs)

        await session.commit()

        return logs

    async def test_download_flow_run_logs(
        self,
        client,
        flow_run_1,
        flow_run_2,
        flow_run_1_logs,
        flow_run_2_logs,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr(
            "prefect.server.api.flow_runs.FLOW_RUN_LOGS_DOWNLOAD_PAGE_LIMIT", 3
        )

        async with client.stream(
            "GET", f"/flow_runs/{flow_run_1.id}/logs/download"
        ) as response:
            response_body = [
                str(chunk, "UTF-8") async for chunk in response.aiter_bytes()
            ]

            lines = "".join(response_body).splitlines()
            line_count = len(lines)

            # number of logs generated plus 1 for the header row
            expected_line_count = len(flow_run_1_logs) + 1

            assert (
                line_count == expected_line_count
            ), f"Expected {expected_line_count} lines, got {line_count}"

import uuid
from uuid import uuid4

import pendulum
import pytest
from starlette import status

from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import State
from prefect.server import models, schemas
from prefect.server.database.orm_models import TaskRun
from prefect.server.schemas import responses, states
from prefect.server.schemas.responses import OrchestrationResult
from prefect.states import Pending


class TestCreateTaskRun:
    async def test_create_task_run(self, flow_run, client, session):
        task_run_data = {
            "flow_run_id": str(flow_run.id),
            "task_key": "my-task-key",
            "name": "my-cool-task-run-name",
            "dynamic_key": "0",
        }
        response = await client.post("/task_runs/", json=task_run_data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["flow_run_id"] == str(flow_run.id)
        assert response.json()["id"]
        assert response.json()["name"] == "my-cool-task-run-name"

        task_run = await models.task_runs.read_task_run(
            session=session, task_run_id=response.json()["id"]
        )
        assert task_run.flow_run_id == flow_run.id

    async def test_create_task_run_gracefully_upserts(self, flow_run, client):
        # create a task run
        task_run_data = {
            "flow_run_id": str(flow_run.id),
            "task_key": "my-task-key",
            "dynamic_key": "my-dynamic-key",
        }
        task_run_response = await client.post("/task_runs/", json=task_run_data)

        # recreate the same task run, ensure graceful upsert
        response = await client.post("/task_runs/", json=task_run_data)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == task_run_response.json()["id"]

    async def test_create_task_run_without_flow_run_id(self, flow_run, client, session):
        task_run_data = {
            "flow_run_id": None,
            "task_key": "my-task-key",
            "name": "my-cool-task-run-name",
            "dynamic_key": "0",
        }
        response = await client.post("/task_runs/", json=task_run_data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["flow_run_id"] is None
        assert response.json()["id"]
        assert response.json()["name"] == "my-cool-task-run-name"

        task_run = await models.task_runs.read_task_run(
            session=session, task_run_id=response.json()["id"]
        )
        assert task_run.flow_run_id is None

        # Posting the same data twice should result in an upsert
        response_2 = await client.post("/task_runs/", json=task_run_data)
        assert response_2.status_code == status.HTTP_200_OK
        assert response.json()["id"] == response_2.json()["id"]

    async def test_create_task_run_without_state(self, flow_run, client, session):
        task_run_data = dict(
            flow_run_id=str(flow_run.id), task_key="task-key", dynamic_key="0"
        )
        response = await client.post("/task_runs/", json=task_run_data)
        task_run = await models.task_runs.read_task_run(
            session=session, task_run_id=response.json()["id"]
        )
        assert str(task_run.id) == response.json()["id"]
        assert task_run.state.type == states.StateType.PENDING

    async def test_create_task_run_with_state(self, flow_run, client, session):
        task_run_data = schemas.actions.TaskRunCreate(
            flow_run_id=flow_run.id,
            task_key="task-key",
            state=schemas.actions.StateCreate(type=schemas.states.StateType.RUNNING),
            dynamic_key="0",
        )
        response = await client.post(
            "/task_runs/", json=task_run_data.model_dump(mode="json")
        )
        task_run = await models.task_runs.read_task_run(
            session=session, task_run_id=response.json()["id"]
        )
        assert str(task_run.id) == response.json()["id"]
        assert task_run.state.type == task_run_data.state.type

    async def test_raises_on_retry_delay_validation(self, flow_run, client, session):
        task_run_data = {
            "flow_run_id": str(flow_run.id),
            "task_key": "my-task-key",
            "name": "my-cool-task-run-name",
            "dynamic_key": "0",
            "empirical_policy": {"retries": 3, "retry_delay": list(range(100))},
        }
        response = await client.post("/task_runs/", json=task_run_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert (
            "Can not configure more than 50 retry delays per task."
            in response.json()["exception_detail"][0]["msg"]
        )

    async def test_raises_on_jitter_factor_validation(self, flow_run, client, session):
        task_run_data = {
            "flow_run_id": str(flow_run.id),
            "task_key": "my-task-key",
            "name": "my-cool-task-run-name",
            "dynamic_key": "0",
            "empirical_policy": {"retries": 3, "retry_jitter_factor": -100},
        }
        response = await client.post("/task_runs/", json=task_run_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert (
            "`retry_jitter_factor` must be >= 0."
            in response.json()["exception_detail"][0]["msg"]
        )

    async def test_create_task_run_with_client_provided_id(self, flow_run, client):
        client_provided_id = uuid.uuid4()
        task_run_data = {
            "flow_run_id": str(flow_run.id),
            "task_key": "my-task-key",
            "name": "my-cool-task-run-name",
            "dynamic_key": "0",
            "id": str(client_provided_id),
        }
        response = await client.post(
            "/task_runs/",
            json=task_run_data,
        )
        assert response.status_code == 201
        assert response.json()["id"] == str(client_provided_id)

    async def test_create_task_run_with_same_client_provided_id(
        self,
        flow_run,
        client,
    ):
        client_provided_id = uuid.uuid4()
        task_run_data = {
            "flow_run_id": str(flow_run.id),
            "task_key": "my-task-key",
            "name": "my-cool-task-run-name",
            "dynamic_key": "0",
            "id": str(client_provided_id),
        }
        response = await client.post(
            "/task_runs/",
            json=task_run_data,
        )
        assert response.status_code == 201
        assert response.json()["id"] == str(client_provided_id)

        task_run_data = {
            "flow_run_id": str(flow_run.id),
            "task_key": "my-task-key",
            "name": "my-cool-task-run-name",
            "dynamic_key": "1",
            "id": str(client_provided_id),
        }

        response = await client.post(
            "/task_runs/",
            json=task_run_data,
        )

        assert response.status_code == 409


class TestReadTaskRun:
    async def test_read_task_run(self, flow_run, task_run, client):
        # make sure we we can read the task run correctly
        response = await client.get(f"/task_runs/{task_run.id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == str(task_run.id)
        assert response.json()["flow_run_id"] == str(flow_run.id)

    async def test_read_flow_run_with_state(self, task_run, client, session):
        state_id = uuid4()
        (
            await models.task_runs.set_task_run_state(
                session=session,
                task_run_id=task_run.id,
                state=states.State(id=state_id, type="RUNNING"),
            )
        ).state
        await client.get(f"/task_runs/{task_run.id}")
        assert task_run.state.type.value == "RUNNING"
        assert task_run.state.id == state_id

    async def test_read_task_run_returns_404_if_does_not_exist(self, client):
        response = await client.get(f"/task_runs/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReadTaskRuns:
    async def test_read_task_runs(self, task_run, client):
        response = await client.post("/task_runs/filter")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == str(task_run.id)
        assert response.json()[0]["flow_run_id"] == str(task_run.flow_run_id)

    async def test_read_task_runs_applies_task_run_filter(self, task_run, client):
        task_run_filter = dict(
            task_runs=schemas.filters.TaskRunFilter(
                id=schemas.filters.TaskRunFilterId(any_=[task_run.id])
            ).model_dump(mode="json")
        )
        response = await client.post("/task_runs/filter", json=task_run_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == str(task_run.id)
        assert response.json()[0]["flow_run_id"] == str(task_run.flow_run_id)

        bad_task_run_filter = dict(
            task_runs=schemas.filters.TaskRunFilter(
                id=schemas.filters.TaskRunFilterId(any_=[uuid4()])
            ).model_dump(mode="json")
        )
        response = await client.post("/task_runs/filter", json=bad_task_run_filter)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    async def test_read_task_runs_applies_flow_run_filter(self, task_run, client):
        task_run_filter = dict(
            flow_runs=schemas.filters.FlowRunFilter(
                id=schemas.filters.FlowRunFilterId(any_=[task_run.flow_run_id])
            ).model_dump(mode="json")
        )
        response = await client.post("/task_runs/filter", json=task_run_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == str(task_run.id)
        assert response.json()[0]["flow_run_id"] == str(task_run.flow_run_id)

        bad_task_run_filter = dict(
            flow_runs=schemas.filters.FlowRunFilter(
                id=schemas.filters.FlowRunFilterId(any_=[uuid4()])
            ).model_dump(mode="json")
        )
        response = await client.post("/task_runs/filter", json=bad_task_run_filter)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    async def test_read_task_runs_applies_flow_filter(self, flow, task_run, client):
        task_run_filter = dict(
            flows=schemas.filters.FlowFilter(
                id=schemas.filters.FlowFilterId(any_=[flow.id])
            ).model_dump(mode="json")
        )
        response = await client.post("/task_runs/filter", json=task_run_filter)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == str(task_run.id)
        assert response.json()[0]["flow_run_id"] == str(task_run.flow_run_id)

        bad_task_run_filter = dict(
            flows=schemas.filters.FlowFilter(
                id=schemas.filters.FlowFilterId(any_=[uuid4()])
            ).model_dump(mode="json")
        )
        response = await client.post("/task_runs/filter", json=bad_task_run_filter)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    async def test_read_task_runs_applies_sort(self, flow_run, session, client):
        now = pendulum.now("UTC")
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                name="Task Run 1",
                flow_run_id=flow_run.id,
                task_key="my-key",
                expected_start_time=now.subtract(minutes=5),
                dynamic_key="0",
            ),
        )
        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                name="Task Run 2",
                flow_run_id=flow_run.id,
                task_key="my-key",
                expected_start_time=now.add(minutes=5),
                dynamic_key="1",
            ),
        )
        await session.commit()

        response = await client.post(
            "/task_runs/filter",
            json=dict(
                limit=1, sort=schemas.sorting.TaskRunSort.EXPECTED_START_TIME_DESC.value
            ),
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()[0]["id"] == str(task_run_2.id)

        response = await client.post(
            "/task_runs/filter",
            json=dict(
                limit=1,
                offset=1,
                sort=schemas.sorting.TaskRunSort.EXPECTED_START_TIME_DESC.value,
            ),
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()[0]["id"] == str(task_run_1.id)

        # name asc
        response = await client.post(
            "/task_runs/filter",
            json=dict(
                limit=1,
                sort=schemas.sorting.TaskRunSort.NAME_ASC.value,
            ),
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()[0]["id"] == str(task_run_1.id)

        # name desc
        response = await client.post(
            "/task_runs/filter",
            json=dict(
                limit=1,
                sort=schemas.sorting.TaskRunSort.NAME_DESC.value,
            ),
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()[0]["id"] == str(task_run_2.id)

    @pytest.mark.parametrize(
        "sort", [sort_option.value for sort_option in schemas.sorting.TaskRunSort]
    )
    async def test_read_task_runs_succeeds_for_all_sort_values(
        self, sort, task_run, client
    ):
        response = await client.post("/task_runs/filter", json=dict(sort=sort))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == str(task_run.id)


class TestDeleteTaskRuns:
    async def test_delete_task_runs(self, task_run, client, session):
        # delete the task run
        response = await client.delete(f"/task_runs/{task_run.id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # make sure it's deleted
        task_run_id = task_run.id
        session.expire_all()
        run = await models.task_runs.read_task_run(
            session=session, task_run_id=task_run_id
        )
        assert run is None
        response = await client.get(f"/task_runs/{task_run_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_task_run_returns_404_if_does_not_exist(self, client):
        response = await client.delete(f"/task_runs/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestSetTaskRunState:
    async def test_set_task_run_state(self, task_run, client, session):
        # first ensure the parent flow run is in a running state
        await client.post(
            f"/flow_runs/{task_run.flow_run_id}/set_state",
            json=dict(state=dict(type="RUNNING")),
        )

        response = await client.post(
            f"/task_runs/{task_run.id}/set_state",
            json=dict(state=dict(type="RUNNING", name="Test State")),
        )
        assert response.status_code == status.HTTP_201_CREATED

        api_response = OrchestrationResult.model_validate(response.json())
        assert api_response.status == responses.SetStateStatus.ACCEPT

        task_run_id = task_run.id
        session.expire_all()
        run = await models.task_runs.read_task_run(
            session=session, task_run_id=task_run_id
        )
        assert run.state.type == states.StateType.RUNNING
        assert run.state.name == "Test State"
        assert run.run_count == 1

    async def test_set_task_run_state_without_flow_run_id(self, client, session):
        task_run_data = {
            "flow_run_id": None,
            "task_key": "my-task-key",
            "name": "my-cool-task-run-name",
            "dynamic_key": "0",
        }
        response = await client.post("/task_runs/", json=task_run_data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["flow_run_id"] is None
        assert response.json()["id"]
        assert response.json()["name"] == "my-cool-task-run-name"

        task_run = await models.task_runs.read_task_run(
            session=session, task_run_id=response.json()["id"]
        )
        assert task_run.flow_run_id is None

        orchestration_response = await client.post(
            f"/task_runs/{task_run.id}/set_state",
            json=dict(state=dict(type="RUNNING", name="Test State")),
        )
        assert orchestration_response.status_code == status.HTTP_201_CREATED

        api_response = OrchestrationResult.model_validate(orchestration_response.json())
        assert api_response.status == responses.SetStateStatus.ACCEPT

        task_run_id = task_run.id
        session.expire_all()
        run = await models.task_runs.read_task_run(
            session=session, task_run_id=task_run_id
        )
        assert run.state.type == states.StateType.RUNNING
        assert run.state.name == "Test State"
        assert run.run_count == 1
        assert run.flow_run_id is None

    @pytest.mark.parametrize("proposed_state", ["PENDING", "RUNNING"])
    async def test_setting_task_run_state_twice_works(
        self, task_run, client, session, proposed_state
    ):
        # Task runner infrastructure may kill and restart tasks without informing
        # Prefect. This test checks that a task can re-transition  its current state
        # to ensure restarts occur without error.

        # first, ensure the parent flow run is in a running state
        await client.post(
            f"/flow_runs/{task_run.flow_run_id}/set_state",
            json=dict(state=dict(type="RUNNING")),
        )

        response = await client.post(
            f"/task_runs/{task_run.id}/set_state",
            json=dict(state=dict(type=proposed_state, name="Test State")),
        )
        assert response.status_code == status.HTTP_201_CREATED

        api_response = OrchestrationResult.model_validate(response.json())
        assert api_response.status == responses.SetStateStatus.ACCEPT

        response = await client.post(
            f"/task_runs/{task_run.id}/set_state",
            json=dict(state=dict(type=proposed_state, name="Test State")),
        )
        assert response.status_code == 201

        api_response = OrchestrationResult.model_validate(response.json())
        assert api_response.status == responses.SetStateStatus.ACCEPT

    async def test_failed_becomes_awaiting_retry(
        self, task_run: TaskRun, client, session
    ):
        # set max retries to 1
        # copy to trigger ORM updates
        task_run.empirical_policy = task_run.empirical_policy.model_copy()
        task_run.empirical_policy.retries = 1
        await session.flush()

        (
            await models.task_runs.set_task_run_state(
                session=session,
                task_run_id=task_run.id,
                state=states.Running(),
            )
        ).state
        await session.commit()

        # fail the running task run
        response = await client.post(
            f"/task_runs/{task_run.id}/set_state",
            json=dict(state=dict(type="FAILED")),
        )
        assert response.status_code == status.HTTP_201_CREATED

        api_response = OrchestrationResult.model_validate(response.json())
        assert api_response.status == responses.SetStateStatus.REJECT
        assert api_response.state.name == "AwaitingRetry"
        assert api_response.state.type == states.StateType.SCHEDULED

    async def test_set_task_run_state_force_skips_orchestration(
        self, task_run, client, session
    ):
        # set max retries to 1
        # copy to trigger ORM updates
        task_run.empirical_policy = task_run.empirical_policy.model_copy()
        task_run.empirical_policy.retries = 1
        await session.flush()

        (
            await models.task_runs.set_task_run_state(
                session=session,
                task_run_id=task_run.id,
                state=states.Running(),
            )
        ).state
        await session.commit()

        # fail the running task run
        response = await client.post(
            f"/task_runs/{task_run.id}/set_state",
            json=dict(state=dict(type="FAILED"), force=True),
        )
        assert response.status_code == status.HTTP_201_CREATED

        api_response = OrchestrationResult.model_validate(response.json())
        assert api_response.status == responses.SetStateStatus.ACCEPT
        assert api_response.state.type == states.StateType.FAILED

    async def test_set_task_run_state_returns_404_on_missing_flow_run(
        self, task_run, client, session
    ):
        await models.flow_runs.delete_flow_run(
            session=session, flow_run_id=task_run.flow_run_id
        )
        await session.commit()
        response = await client.post(
            f"/task_runs/{task_run.id}/set_state",
            json=dict(state=dict(type="RUNNING", name="Test State")),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.parametrize(
        "incoming_state_type", ["PENDING", "RUNNING", "CANCELLED", "CANCELLING"]
    )
    async def test_autonomous_task_run_aborts_if_enters_pending_from_disallowed_state(
        self, client, session, incoming_state_type, prefect_client: PrefectClient
    ):
        autonomous_task_run = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=None,  # autonomous task runs have no flow run
                task_key="my-task-key",
                expected_start_time=pendulum.now("UTC"),
                dynamic_key="0",
            ),
        )

        await session.commit()

        state = State(type=incoming_state_type)
        state.state_details.deferred = True
        response_1 = await prefect_client.set_task_run_state(
            task_run_id=autonomous_task_run.id, state=state
        )

        assert response_1.status == responses.SetStateStatus.ACCEPT

        new_state = Pending()
        new_state.state_details.deferred = True
        response_2 = await prefect_client.set_task_run_state(
            task_run_id=autonomous_task_run.id, state=new_state
        )

        assert response_2.status == responses.SetStateStatus.ABORT


class TestTaskRunHistory:
    async def test_history_interval_must_be_one_second_or_larger(self, client):
        response = await client.post(
            "/task_runs/history",
            json=dict(
                history_start=str(pendulum.now("UTC")),
                history_end=str(pendulum.now("UTC").add(days=1)),
                history_interval_seconds=0.9,
            ),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert b"History interval must not be less than 1 second" in response.content

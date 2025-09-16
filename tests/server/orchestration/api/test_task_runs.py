import asyncio
import datetime
import uuid
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from prefect._internal.compatibility.starlette import status
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import Flow, State
from prefect.server import models, schemas
from prefect.server.database.orm_models import FlowRun, TaskRun
from prefect.server.schemas import responses, states
from prefect.server.schemas.responses import OrchestrationResult
from prefect.states import Pending
from prefect.types._datetime import now as now_fn


class TestCreateTaskRun:
    async def test_create_task_run(self, flow_run, client, session):
        task_run_data = {
            "flow_run_id": str(flow_run.id),
            "task_key": "my-task-key",
            "name": "my-cool-task-run-name",
            "dynamic_key": "0",
            "labels": {"env": "dev"},
        }
        response = await client.post("/task_runs/", json=task_run_data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["flow_run_id"] == str(flow_run.id)
        assert response.json()["id"]
        assert response.json()["name"] == "my-cool-task-run-name"
        assert response.json()["labels"] == {
            "env": "dev",
            "prefect.flow.id": str(flow_run.flow_id),
            "prefect.flow-run.id": str(flow_run.id),
        }

        task_run = await models.task_runs.read_task_run(
            session=session, task_run_id=response.json()["id"]
        )
        assert task_run
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
        now = now_fn("UTC")
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                name="Task Run 1",
                flow_run_id=flow_run.id,
                task_key="my-key",
                expected_start_time=now - datetime.timedelta(minutes=5),
                dynamic_key="0",
            ),
        )
        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                name="Task Run 2",
                flow_run_id=flow_run.id,
                task_key="my-key",
                expected_start_time=now + datetime.timedelta(minutes=5),
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


class TestPaginateTaskRuns:
    async def test_paginate_task_runs_basic(
        self, task_run: TaskRun, client: AsyncClient
    ):
        """Test basic pagination functionality with default parameters."""
        response = await client.post("/task_runs/paginate")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["id"] == str(task_run.id)
        assert data["results"][0]["flow_run_id"] == str(task_run.flow_run_id)

    async def test_paginate_task_runs_response_structure(
        self, task_run: TaskRun, client: AsyncClient
    ):
        """Test that the pagination response structure is correct."""
        response = await client.post("/task_runs/paginate")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "results" in data
        assert "count" in data
        assert "limit" in data
        assert "pages" in data
        assert "page" in data

        assert data["count"] == 1
        assert data["page"] == 1
        assert data["pages"] == 1
        assert data["limit"] > 0

    async def test_paginate_task_runs_with_custom_page_and_limit(
        self, flow_run: FlowRun, session: AsyncSession, client: AsyncClient
    ):
        """Test pagination with custom page size and page number."""
        # Create multiple task runs
        now = now_fn("UTC")
        task_runs: list[TaskRun] = []

        for i in range(5):
            task_run = await models.task_runs.create_task_run(
                session=session,
                task_run=schemas.core.TaskRun(
                    name=f"Task Run {i}",
                    flow_run_id=flow_run.id,
                    task_key="my-key",
                    expected_start_time=now + datetime.timedelta(minutes=i),
                    dynamic_key=str(i),
                ),
            )
            task_runs.append(task_run)

        await session.commit()

        # Test with limit=2, page=1
        response = await client.post("/task_runs/paginate", json=dict(limit=2, page=1))
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data["results"]) == 2
        assert data["count"] == 5
        assert data["limit"] == 2
        assert data["pages"] == 3
        assert data["page"] == 1

        # Test with limit=2, page=2
        response = await client.post("/task_runs/paginate", json=dict(limit=2, page=2))
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data["results"]) == 2
        assert data["page"] == 2

        # Test with limit=2, page=3
        response = await client.post("/task_runs/paginate", json=dict(limit=2, page=3))
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data["results"]) == 1  # Only one item on the last page
        assert data["page"] == 3

    async def test_paginate_task_runs_with_task_run_filter(
        self, task_run: TaskRun, client: AsyncClient
    ):
        """Test pagination with task run filter."""
        task_run_filter = dict(
            task_runs=schemas.filters.TaskRunFilter(
                id=schemas.filters.TaskRunFilterId(any_=[task_run.id])
            ).model_dump(mode="json")
        )

        response = await client.post("/task_runs/paginate", json=task_run_filter)
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["id"] == str(task_run.id)
        assert data["count"] == 1

        # Test with a non-matching filter
        bad_task_run_filter = dict(
            task_runs=schemas.filters.TaskRunFilter(
                id=schemas.filters.TaskRunFilterId(any_=[uuid4()])
            ).model_dump(mode="json")
        )

        response = await client.post("/task_runs/paginate", json=bad_task_run_filter)
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data["results"]) == 0
        assert data["count"] == 0

    async def test_paginate_task_runs_with_flow_run_filter(
        self, task_run: TaskRun, client: AsyncClient
    ):
        """Test pagination with flow run filter."""
        flow_run_filter = dict(
            flow_runs=schemas.filters.FlowRunFilter(
                id=schemas.filters.FlowRunFilterId(any_=[task_run.flow_run_id])
            ).model_dump(mode="json")
        )

        response = await client.post("/task_runs/paginate", json=flow_run_filter)
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["id"] == str(task_run.id)
        assert data["count"] == 1

        # Test with a non-matching filter
        bad_flow_run_filter = dict(
            flow_runs=schemas.filters.FlowRunFilter(
                id=schemas.filters.FlowRunFilterId(any_=[uuid4()])
            ).model_dump(mode="json")
        )

        response = await client.post("/task_runs/paginate", json=bad_flow_run_filter)
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data["results"]) == 0
        assert data["count"] == 0

    async def test_paginate_task_runs_with_flow_filter(
        self, flow: Flow, task_run: TaskRun, client: AsyncClient
    ):
        """Test pagination with flow filter."""
        flow_filter = dict(
            flows=schemas.filters.FlowFilter(
                id=schemas.filters.FlowFilterId(any_=[flow.id])
            ).model_dump(mode="json")
        )

        response = await client.post("/task_runs/paginate", json=flow_filter)
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["id"] == str(task_run.id)
        assert data["count"] == 1

        # Test with a non-matching filter
        bad_flow_filter = dict(
            flows=schemas.filters.FlowFilter(
                id=schemas.filters.FlowFilterId(any_=[uuid4()])
            ).model_dump(mode="json")
        )

        response = await client.post("/task_runs/paginate", json=bad_flow_filter)
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data["results"]) == 0
        assert data["count"] == 0

    async def test_paginate_task_runs_applies_sort(
        self, flow_run: FlowRun, session: AsyncSession, client: AsyncClient
    ):
        """Test pagination with sorting."""
        now = now_fn("UTC")
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                name="Task Run 1",
                flow_run_id=flow_run.id,
                task_key="my-key",
                expected_start_time=now - datetime.timedelta(minutes=5),
                dynamic_key="0",
            ),
        )
        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                name="Task Run 2",
                flow_run_id=flow_run.id,
                task_key="my-key",
                expected_start_time=now + datetime.timedelta(minutes=5),
                dynamic_key="1",
            ),
        )
        await session.commit()

        # Test expected_start_time descending
        response = await client.post(
            "/task_runs/paginate",
            json=dict(
                limit=1, sort=schemas.sorting.TaskRunSort.EXPECTED_START_TIME_DESC.value
            ),
        )
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["id"] == str(task_run_2.id)
        assert data["pages"] == 2

        # Test getting the second page
        response = await client.post(
            "/task_runs/paginate",
            json=dict(
                limit=1,
                page=2,
                sort=schemas.sorting.TaskRunSort.EXPECTED_START_TIME_DESC.value,
            ),
        )
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["id"] == str(task_run_1.id)

        # Test name ascending
        response = await client.post(
            "/task_runs/paginate",
            json=dict(
                limit=1,
                sort=schemas.sorting.TaskRunSort.NAME_ASC.value,
            ),
        )
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["id"] == str(task_run_1.id)

        # Test name descending
        response = await client.post(
            "/task_runs/paginate",
            json=dict(
                limit=1,
                sort=schemas.sorting.TaskRunSort.NAME_DESC.value,
            ),
        )
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["id"] == str(task_run_2.id)

    @pytest.mark.parametrize(
        "sort", [sort_option.value for sort_option in schemas.sorting.TaskRunSort]
    )
    async def test_paginate_task_runs_succeeds_for_all_sort_values(
        self, sort: schemas.sorting.TaskRunSort, task_run: TaskRun, client: AsyncClient
    ):
        """Test pagination with all sort values."""
        response = await client.post("/task_runs/paginate", json=dict(sort=sort))
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["id"] == str(task_run.id)

    async def test_paginate_task_runs_with_invalid_page(self, client: AsyncClient):
        """Test pagination with invalid page parameter."""
        response = await client.post("/task_runs/paginate", json=dict(page=0))
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        response = await client.post("/task_runs/paginate", json=dict(page=-1))
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


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

    async def test_delete_task_run_deletes_logs(self, task_run, logs, client, session):
        # make sure we have task run logs
        task_run_logs = [log for log in logs if log.task_run_id is not None]
        assert len(task_run_logs) > 0

        # delete the task run
        response = await client.delete(f"/task_runs/{task_run.id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT, response.text

        async def read_logs():
            # because deletion happens in the background,
            # loop until we get what we expect or we time out
            while True:
                # make sure we no longer have task run logs
                post_delete_logs = await models.logs.read_logs(
                    session=session,
                    log_filter=None,
                )
                # we should get back our non task run logs
                if len(post_delete_logs) == len(logs) - len(task_run_logs):
                    return post_delete_logs
                asyncio.sleep(1)

        logs = await asyncio.wait_for(read_logs(), 10)
        assert all([log.task_run_id is None for log in logs])


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
                expected_start_time=now_fn("UTC"),
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

    async def test_set_task_run_state_with_long_cache_key_rejects_transition(
        self, task_run: TaskRun, client: AsyncClient
    ):
        await client.post(
            f"/flow_runs/{task_run.flow_run_id}/set_state",
            json=dict(state=dict(type="RUNNING")),
        )

        response = await client.post(
            f"/task_runs/{task_run.id}/set_state",
            json=dict(
                state=dict(
                    type="COMPLETED",
                    name="Test State",
                    state_details={"cache_key": "a" * 5000},
                )
            ),
        )
        assert response.status_code == status.HTTP_201_CREATED

        api_response = OrchestrationResult.model_validate(response.json())
        assert api_response.status == responses.SetStateStatus.REJECT
        assert isinstance(api_response.details, responses.StateRejectDetails)
        assert (
            api_response.details.reason
            == "Cache key exceeded maximum allowed length of 2000 characters."
        )


class TestTaskRunHistory:
    async def test_history_interval_must_be_one_second_or_larger(self, client):
        response = await client.post(
            "/task_runs/history",
            json=dict(
                history_start=str(now_fn("UTC")),
                history_end=str(now_fn("UTC") + datetime.timedelta(days=1)),
                history_interval_seconds=0.9,
            ),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert b"History interval must not be less than 1 second" in response.content

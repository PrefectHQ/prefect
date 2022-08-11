from typing import List
from uuid import uuid4

import pendulum
import pydantic
import pytest
from fastapi import status

from prefect.orion import models, schemas
from prefect.orion.schemas.actions import WorkQueueCreate, WorkQueueUpdate


@pytest.fixture
async def work_queue(session):
    work_queue = await models.work_queues.create_work_queue(
        session=session,
        work_queue=schemas.core.WorkQueue(
            name="wq-1",
            description="All about my work queue",
        ),
    )
    await session.commit()
    return work_queue


class TestCreateWorkQueue:
    async def test_create_work_queue(
        self,
        session,
        client,
    ):
        now = pendulum.now(tz="UTC")
        data = WorkQueueCreate(name="wq-1").dict(json_compatible=True)
        response = await client.post("/work_queues/", json=data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["name"] == "wq-1"
        assert response.json()["filter"] is None
        assert pendulum.parse(response.json()["created"]) >= now
        assert pendulum.parse(response.json()["updated"]) >= now
        work_queue_id = response.json()["id"]

        work_queue = await models.work_queues.read_work_queue(
            session=session, work_queue_id=work_queue_id
        )
        assert str(work_queue.id) == work_queue_id
        assert work_queue.name == "wq-1"

    async def test_create_work_queue_raises_error_on_existing_name(
        self, client, work_queue
    ):
        data = WorkQueueCreate(
            name=work_queue.name,
        ).dict(json_compatible=True)
        response = await client.post("/work_queues/", json=data)
        assert response.status_code == status.HTTP_409_CONFLICT

    @pytest.mark.parametrize(
        "name",
        [
            "work/queue",
            r"work%queue",
        ],
    )
    async def test_create_work_queue_with_invalid_characters_fails(self, client, name):
        response = await client.post("/work_queues/", json=dict(name=name))
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert b"contains an invalid character" in response.content


class TestUpdateWorkQueue:
    async def test_update_work_queue(
        self,
        session,
        client,
    ):
        now = pendulum.now(tz="UTC")
        data = WorkQueueCreate(name="wq-1").dict(
            json_compatible=True, exclude_unset=True
        )
        response = await client.post("/work_queues/", json=data)
        work_queue_id = response.json()["id"]

        work_queue = await models.work_queues.read_work_queue(
            session=session, work_queue_id=work_queue_id
        )

        assert work_queue.is_paused is False
        assert work_queue.concurrency_limit is None

        new_data = WorkQueueUpdate(is_paused=True, concurrency_limit=3).dict(
            json_compatible=True, exclude_unset=True
        )
        response = await client.patch(f"/work_queues/{work_queue_id}", json=new_data)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        response = await client.get(f"/work_queues/{work_queue_id}")

        assert response.json()["is_paused"] is True
        assert response.json()["concurrency_limit"] == 3


class TestReadWorkQueue:
    async def test_read_work_queue(self, client, work_queue):
        response = await client.get(f"/work_queues/{work_queue.id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == str(work_queue.id)
        assert response.json()["name"] == "wq-1"

    async def test_read_work_queue_returns_404_if_does_not_exist(self, client):
        response = await client.get(f"/work_queues/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReadWorkQueueByName:
    async def test_read_work_queue_by_name(self, client, work_queue):
        response = await client.get(f"/work_queues/name/{work_queue.name}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == str(work_queue.id)
        assert response.json()["name"] == work_queue.name

    async def test_read_work_queue_returns_404_if_does_not_exist(self, client):
        response = await client.get(f"/work_queues/name/some-made-up-work-queue")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.parametrize(
        "name",
        [
            "work queue",
            "work:queue",
            "work\\queue",
            "work👍queue",
            "work|queue",
        ],
    )
    async def test_read_work_queue_by_name_with_nonstandard_characters(
        self, client, name
    ):
        response = await client.post("/work_queues/", json=dict(name=name))
        work_queue_id = response.json()["id"]

        response = await client.get(f"/work_queues/name/{name}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == work_queue_id

    @pytest.mark.parametrize(
        "name",
        [
            "work/queue",
            "work%queue",
        ],
    )
    async def test_read_work_queue_by_name_with_invalid_characters_fails(
        self, client, name
    ):

        response = await client.get(f"/work_queues/name/{name}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReadWorkQueues:
    @pytest.fixture
    async def work_queues(self, session):
        await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.core.WorkQueue(
                name="wq-1 X",
            ),
        )

        await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.core.WorkQueue(
                name="wq-1 Y",
            ),
        )
        await session.commit()

    async def test_read_work_queues(self, work_queues, client):
        response = await client.post("/work_queues/filter")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 2

    async def test_read_work_queues_applies_limit(self, work_queues, client):
        response = await client.post("/work_queues/filter", json=dict(limit=1))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1

    async def test_read_work_queues_offset(self, work_queues, client, session):
        response = await client.post("/work_queues/filter", json=dict(offset=1))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        # ordered by name by default
        assert response.json()[0]["name"] == "wq-1 Y"

    async def test_read_work_queues_returns_empty_list(self, client):
        response = await client.post("/work_queues/filter")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []


class TestGetRunsInWorkQueue:
    @pytest.fixture
    async def work_queue_2(self, session):
        work_queue = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.core.WorkQueue(name="wq-2"),
        )
        await session.commit()
        return work_queue

    @pytest.fixture
    async def scheduled_flow_runs(self, session, deployment, work_queue, work_queue_2):
        for i in range(3):
            for wq in [work_queue, work_queue_2]:
                await models.flow_runs.create_flow_run(
                    session=session,
                    flow_run=schemas.core.FlowRun(
                        flow_id=deployment.flow_id,
                        deployment_id=deployment.id,
                        work_queue_name=wq.name,
                        state=schemas.states.State(
                            type="SCHEDULED",
                            timestamp=pendulum.now("UTC").add(minutes=i),
                            state_details=dict(
                                scheduled_time=pendulum.now("UTC").add(minutes=i)
                            ),
                        ),
                    ),
                )
        await session.commit()

    @pytest.fixture
    async def running_flow_runs(self, session, deployment, work_queue, work_queue_2):
        for i in range(3):
            for wq in [work_queue, work_queue_2]:
                await models.flow_runs.create_flow_run(
                    session=session,
                    flow_run=schemas.core.FlowRun(
                        flow_id=deployment.flow_id,
                        deployment_id=deployment.id,
                        work_queue_name=wq.name,
                        state=schemas.states.State(
                            type="RUNNING" if i == 0 else "PENDING",
                            timestamp=pendulum.now("UTC").subtract(seconds=10),
                        ),
                    ),
                )
        await session.commit()

    async def test_get_runs_in_queue(
        self, client, work_queue, work_queue_2, scheduled_flow_runs, running_flow_runs
    ):
        response1 = await client.post(f"/work_queues/{work_queue.id}/get_runs")
        assert response1.status_code == status.HTTP_200_OK
        response2 = await client.post(f"/work_queues/{work_queue_2.id}/get_runs")
        assert response2.status_code == status.HTTP_200_OK

        runs_wq1 = pydantic.parse_obj_as(List[schemas.core.FlowRun], response1.json())
        runs_wq2 = pydantic.parse_obj_as(List[schemas.core.FlowRun], response2.json())

        assert len(runs_wq1) == len(runs_wq2) == 3
        assert all(r.work_queue_name == work_queue.name for r in runs_wq1)
        assert all(r.work_queue_name == work_queue_2.name for r in runs_wq2)
        assert set([r.id for r in runs_wq1]) != set([r.id for r in runs_wq2])

    @pytest.mark.parametrize("limit", [2, 0])
    async def test_get_runs_in_queue_limit(
        self,
        client,
        work_queue,
        scheduled_flow_runs,
        running_flow_runs,
        limit,
    ):
        response1 = await client.post(
            f"/work_queues/{work_queue.id}/get_runs", json=dict(limit=limit)
        )
        runs_wq1 = pydantic.parse_obj_as(List[schemas.core.FlowRun], response1.json())
        assert len(runs_wq1) == limit

    async def test_get_runs_in_queue_scheduled_before(
        self, client, work_queue, scheduled_flow_runs, running_flow_runs
    ):
        response1 = await client.post(
            f"/work_queues/{work_queue.id}/get_runs",
            json=dict(scheduled_before=pendulum.now().isoformat()),
        )
        runs_wq1 = pydantic.parse_obj_as(List[schemas.core.FlowRun], response1.json())
        assert len(runs_wq1) == 1

    async def test_get_runs_in_queue_nonexistant(
        self, client, work_queue, scheduled_flow_runs, running_flow_runs
    ):
        response1 = await client.post(f"/work_queues/{uuid4()}/get_runs")
        assert response1.status_code == status.HTTP_404_NOT_FOUND

    async def test_get_runs_in_queue_paused(
        self, client, work_queue, scheduled_flow_runs, running_flow_runs
    ):
        await client.patch(f"/work_queues/{work_queue.id}", json=dict(is_paused=True))

        response1 = await client.post(f"/work_queues/{work_queue.id}/get_runs")
        assert response1.json() == []

    @pytest.mark.parametrize("concurrency_limit", [10, 5, 1])
    async def test_get_runs_in_queue_concurrency_limit(
        self,
        client,
        work_queue,
        scheduled_flow_runs,
        running_flow_runs,
        concurrency_limit,
    ):
        await client.patch(
            f"/work_queues/{work_queue.id}",
            json=dict(concurrency_limit=concurrency_limit),
        )

        response1 = await client.post(f"/work_queues/{work_queue.id}/get_runs")

        assert len(response1.json()) == max(0, min(3, concurrency_limit - 3))

    @pytest.mark.parametrize("limit", [10, 1])
    async def test_get_runs_in_queue_concurrency_limit_and_limit(
        self,
        client,
        work_queue,
        scheduled_flow_runs,
        running_flow_runs,
        limit,
    ):
        await client.patch(
            f"/work_queues/{work_queue.id}",
            json=dict(concurrency_limit=5),
        )
        response1 = await client.post(
            f"/work_queues/{work_queue.id}/get_runs",
            json=dict(limit=limit),
        )

        assert len(response1.json()) == min(limit, 2)

    async def test_read_work_queue_runs_updates_agent_last_activity_time(
        self,
        client,
        work_queue,
        session,
    ):
        now = pendulum.now("UTC")
        fake_agent_id = uuid4()
        response = await client.post(
            f"/work_queues/{work_queue.id}/get_runs",
            json=dict(agent_id=str(fake_agent_id)),
        )
        assert response.status_code == status.HTTP_200_OK

        agent = await models.agents.read_agent(session=session, agent_id=fake_agent_id)
        assert agent.id == fake_agent_id
        assert agent.work_queue_id == work_queue.id
        assert agent.last_activity_time >= now


class TestDeleteWorkQueue:
    async def test_delete_work_queue(self, client, work_queue):
        response = await client.delete(f"/work_queues/{work_queue.id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        response = await client.get(f"/work_queues/{work_queue.id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_work_queue_returns_404_if_does_not_exist(self, client):
        response = await client.delete(f"/work_queues/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

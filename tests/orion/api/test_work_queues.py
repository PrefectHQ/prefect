from uuid import uuid4

import pendulum
import pytest

from prefect.orion import models, schemas
from prefect.orion.schemas.actions import WorkQueueCreate
from prefect.orion.schemas.data import DataDocument


@pytest.fixture
async def work_queue(session):
    work_queue = await models.work_queues.create_work_queue(
        session=session,
        work_queue=schemas.core.WorkQueue(
            name="My WorkQueue",
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
        data = WorkQueueCreate(
            name="My WorkQueue", filter=schemas.core.QueueFilter(tags=["foo", "bar"])
        ).dict(json_compatible=True)
        response = await client.post("/work_queues/", json=data)
        assert response.status_code == 201
        assert response.json()["name"] == "My WorkQueue"
        assert response.json()["filter"]["tags"] == ["foo", "bar"]
        assert pendulum.parse(response.json()["created"]) >= now
        assert pendulum.parse(response.json()["updated"]) >= now
        work_queue_id = response.json()["id"]

        work_queue = await models.work_queues.read_work_queue(
            session=session, work_queue_id=work_queue_id
        )
        assert str(work_queue.id) == work_queue_id
        assert work_queue.name == "My WorkQueue"

    async def test_create_work_queue_raises_error_on_existing_name(self, client):
        data = WorkQueueCreate(
            name="My WorkQueue",
        ).dict(json_compatible=True)
        response = await client.post("/work_queues/", json=data)
        assert response.status_code == 201
        assert response.json()["name"] == "My WorkQueue"
        work_queue_id = response.json()["id"]
        raise Exception("Zach you need to implement this test")

        # TODO - this should raise an error


class TestReadWorkQueue:
    async def test_read_work_queue(self, client, work_queue):
        response = await client.get(f"/work_queues/{work_queue.id}")
        assert response.status_code == 200
        assert response.json()["id"] == str(work_queue.id)
        assert response.json()["name"] == "My WorkQueue"

    async def test_read_work_queue_returns_404_if_does_not_exist(self, client):
        response = await client.get(f"/work_queues/{uuid4()}")
        assert response.status_code == 404


class TestReadWorkQueues:
    @pytest.fixture
    async def work_queues(self, session):
        await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.core.WorkQueue(
                name="My WorkQueue X",
            ),
        )

        await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.core.WorkQueue(
                name="My WorkQueue Y",
            ),
        )
        await session.commit()

    async def test_read_work_queues(self, work_queues, client):
        response = await client.post("/work_queues/filter")
        assert response.status_code == 200
        assert len(response.json()) == 2

    async def test_read_work_queues_applies_limit(self, work_queues, client):
        response = await client.post("/work_queues/filter", json=dict(limit=1))
        assert response.status_code == 200
        assert len(response.json()) == 1

    async def test_read_work_queues_offset(self, work_queues, client, session):
        response = await client.post("/work_queues/filter", json=dict(offset=1))
        assert response.status_code == 200
        assert len(response.json()) == 1
        # ordered by name by default
        assert response.json()[0]["name"] == "My WorkQueue Y"

    async def test_read_work_queues_returns_empty_list(self, client):
        response = await client.post("/work_queues/filter")
        assert response.status_code == 200
        assert response.json() == []


class TestReadWorkQueueRuns:
    pass  # TODO


class TestDeleteWorkQueue:
    async def test_delete_work_queue(self, client, work_queue):
        response = await client.delete(f"/work_queues/{work_queue.id}")
        assert response.status_code == 204

        response = await client.get(f"/work_queues/{work_queue.id}")
        assert response.status_code == 404

    async def test_delete_work_queue_returns_404_if_does_not_exist(self, client):
        response = await client.delete(f"/work_queues/{uuid4()}")
        assert response.status_code == 404

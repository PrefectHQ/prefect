from typing import List

import pendulum
import pydantic
import pytest
import sqlalchemy as sa
from fastapi import status

from prefect.orion import models
from prefect.orion.models import workers_migration
from prefect.orion.schemas.actions import WorkerPoolCreate
from prefect.orion.schemas.core import WorkerPool, WorkerPoolQueue
from prefect.settings import PREFECT_BETA_WORKERS_ENABLED, temporary_settings

RESERVED_POOL_NAMES = [
    "Prefect",
    "Prefect Pool",
    "PrefectPool",
    "Prefect-Pool",
    "prefect",
    "prefect pool",
    "prefectpool",
    "prefect-pool",
]


@pytest.fixture(autouse=True)
def auto_enable_workers(enable_workers):
    """
    Enable workers for testing
    """
    assert PREFECT_BETA_WORKERS_ENABLED


class TestEnableWorkersFlag:
    async def test_flag_defaults_to_false(self):
        with temporary_settings(restore_defaults={PREFECT_BETA_WORKERS_ENABLED}):
            assert not PREFECT_BETA_WORKERS_ENABLED

    async def test_404_when_flag_disabled(self, client):
        with temporary_settings(restore_defaults={PREFECT_BETA_WORKERS_ENABLED}):
            response = await client.post(
                "/beta/workers/pools/", json=dict(name="Pool 1")
            )
            assert response.status_code == status.HTTP_404_NOT_FOUND


class TestCreateWorkerPool:
    async def test_create_worker_pool(self, session, client):
        response = await client.post("/beta/workers/pools/", json=dict(name="Pool 1"))
        assert response.status_code == status.HTTP_201_CREATED
        result = pydantic.parse_obj_as(WorkerPool, response.json())
        assert result.name == "Pool 1"
        assert result.is_paused is False
        assert result.concurrency_limit is None

        model = await models.workers.read_worker_pool(
            session=session, worker_pool_id=result.id
        )
        assert model.name == "Pool 1"

    async def test_create_worker_pool_with_options(self, client):
        response = await client.post(
            "/beta/workers/pools/",
            json=dict(name="Pool 1", is_paused=True, concurrency_limit=5),
        )
        assert response.status_code == status.HTTP_201_CREATED
        result = pydantic.parse_obj_as(WorkerPool, response.json())
        assert result.name == "Pool 1"
        assert result.is_paused is True
        assert result.concurrency_limit == 5

    async def test_create_duplicate_worker_pool(self, client, worker_pool):
        response = await client.post(
            "/beta/workers/pools/", json=dict(name=worker_pool.name, type="PROCESS")
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    @pytest.mark.parametrize("name", ["hi/there", "hi%there"])
    async def test_create_worker_pool_with_invalid_name(self, client, name):
        response = await client.post("/beta/workers/pools/", json=dict(name=name))
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.parametrize("type", [None, "PROCESS", "K8S", "AGENT"])
    async def test_create_typed_worker_pool(self, session, client, type):
        response = await client.post(
            "/beta/workers/pools/", json=dict(name="Pool 1", type=type)
        )
        assert response.status_code == status.HTTP_201_CREATED
        result = pydantic.parse_obj_as(WorkerPool, response.json())
        assert result.type == type

    @pytest.mark.parametrize("name", RESERVED_POOL_NAMES)
    async def test_create_reserved_pool_fails(self, session, client, name):
        response = await client.post("/beta/workers/pools/", json=dict(name=name))
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "reserved for internal use" in response.json()["detail"]


class TestDeleteWorkerPool:
    async def test_delete_worker_pool(self, client, worker_pool, session):
        worker_pool_id = worker_pool.id
        response = await client.delete(f"/beta/workers/pools/{worker_pool.name}")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not await models.workers.read_worker_pool(
            session=session, worker_pool_id=worker_pool_id
        )

    async def test_nonexistent_worker_pool(self, client):
        response = await client.delete("/beta/workers/pools/does-not-exist")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.parametrize("name", RESERVED_POOL_NAMES)
    async def test_delete_reserved_pool_fails(self, session, client, name):
        assert await models.workers.create_worker_pool(
            session=session, worker_pool=WorkerPoolCreate(name=name)
        )
        await session.commit()

        response = await client.delete(f"/beta/workers/pools/{name}")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "reserved for internal use" in response.json()["detail"]

    async def test_reading_agent_pool_creates_it(self, client, session, db):
        """
        Attempts to read the agent pool should create it if it doesn't exist
        """
        count = await session.execute(sa.select(sa.func.count(db.WorkerPool.id)))
        assert count.scalar() == 0

        response = await client.get(
            f"/beta/workers/pools/{workers_migration.AGENT_WORKER_POOL_NAME}"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == workers_migration.AGENT_WORKER_POOL_NAME

        count = await session.execute(sa.select(sa.func.count(db.WorkerPool.id)))
        assert count.scalar() == 1


class TestUpdateWorkerPool:
    async def test_update_worker_pool(self, client, session, worker_pool):
        response = await client.patch(
            f"/beta/workers/pools/{worker_pool.name}",
            json=dict(is_paused=True, concurrency_limit=5),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        session.expunge_all()
        result = await models.workers.read_worker_pool(
            session=session, worker_pool_id=worker_pool.id
        )
        assert result.is_paused is True
        assert result.concurrency_limit == 5

    async def test_update_worker_pool_zero_concurrency(
        self, client, session, worker_pool, db
    ):
        response = await client.patch(
            f"/beta/workers/pools/{worker_pool.name}",
            json=dict(concurrency_limit=0),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        async with db.session_context() as session:
            result = await models.workers.read_worker_pool(
                session=session, worker_pool_id=worker_pool.id
            )
        assert result.concurrency_limit == 0

    async def test_update_worker_pool_invalid_concurrency(
        self, client, session, worker_pool
    ):
        response = await client.patch(
            f"/beta/workers/pools/{worker_pool.name}",
            json=dict(concurrency_limit=-5),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        session.expunge_all()
        result = await models.workers.read_worker_pool(
            session=session, worker_pool_id=worker_pool.id
        )
        assert result.concurrency_limit is None

    @pytest.mark.parametrize("name", RESERVED_POOL_NAMES)
    async def test_update_reserved_pool(self, session, client, name):
        assert await models.workers.create_worker_pool(
            session=session, worker_pool=WorkerPoolCreate(name=name)
        )
        await session.commit()

        # fails if we try to update the description
        response = await client.patch(
            f"/beta/workers/pools/{name}",
            json=dict(description=name, is_paused=True, concurrency_limit=5),
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "reserved for internal use" in response.json()["detail"]

        # succeeds if just pause and concurrency
        response = await client.patch(
            f"/beta/workers/pools/{name}",
            json=dict(is_paused=True, concurrency_limit=5),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT


class TestReadWorkerPool:
    async def test_read_worker_pool(self, client, worker_pool):
        response = await client.get(f"/beta/workers/pools/{worker_pool.name}")
        assert response.status_code == status.HTTP_200_OK
        result = pydantic.parse_obj_as(WorkerPool, response.json())
        assert result.name == worker_pool.name
        assert result.id == worker_pool.id

    async def test_read_invalid_config(self, client):
        response = await client.get("/beta/workers/pools/does-not-exist")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReadWorkerPools:
    @pytest.fixture(autouse=True)
    async def create_worker_pools(self, client):
        for name in ["C", "B", "A"]:
            await client.post("/beta/workers/pools/", json=dict(name=name))

    async def test_read_worker_pools(self, client, session):
        response = await client.post("/beta/workers/pools/filter")
        assert response.status_code == status.HTTP_200_OK
        result = pydantic.parse_obj_as(List[WorkerPool], response.json())
        assert [r.name for r in result] == ["A", "B", "C"]

    async def test_read_worker_pools_with_limit(self, client, session):
        response = await client.post("/beta/workers/pools/filter", json=dict(limit=2))
        assert response.status_code == status.HTTP_200_OK
        result = pydantic.parse_obj_as(List[WorkerPool], response.json())
        assert [r.name for r in result] == ["A", "B"]

    async def test_read_worker_pools_with_offset(self, client, session):
        response = await client.post("/beta/workers/pools/filter", json=dict(offset=1))
        assert response.status_code == status.HTTP_200_OK
        result = pydantic.parse_obj_as(List[WorkerPool], response.json())
        assert [r.name for r in result] == ["B", "C"]


class TestCreateWorkerPoolQueue:
    async def test_create_worker_pool_queue(self, client, worker_pool):
        response = await client.post(
            f"/beta/workers/pools/{worker_pool.name}/queues",
            json=dict(name="test-queue", description="test queue"),
        )
        assert response.status_code == status.HTTP_201_CREATED
        result = pydantic.parse_obj_as(WorkerPoolQueue, response.json())
        assert result.name == "test-queue"
        assert result.description == "test queue"


class TestWorkerProcess:
    async def test_heartbeat_worker(self, client, worker_pool):
        workers_response = await client.post(
            f"/beta/workers/pools/{worker_pool.name}/workers/filter"
        )
        assert workers_response.status_code == status.HTTP_200_OK
        assert len(workers_response.json()) == 0

        dt = pendulum.now()
        response = await client.post(
            f"/beta/workers/pools/{worker_pool.name}/workers/heartbeat",
            json=dict(name="test-worker"),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        workers_response = await client.post(
            f"/beta/workers/pools/{worker_pool.name}/workers/filter"
        )
        assert workers_response.status_code == status.HTTP_200_OK
        assert len(workers_response.json()) == 1
        assert workers_response.json()[0]["name"] == "test-worker"
        assert pendulum.parse(workers_response.json()[0]["last_heartbeat_time"]) > dt

    async def test_heartbeat_worker_requires_name(self, client, worker_pool):
        response = await client.post(
            f"/beta/workers/pools/{worker_pool.name}/workers/heartbeat"
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert b"field required" in response.content

    async def test_heartbeat_worker_upserts_for_same_name(self, client, worker_pool):
        for name in ["test-worker", "test-worker", "test-worker", "another-worker"]:
            response = await client.post(
                f"/beta/workers/pools/{worker_pool.name}/workers/heartbeat",
                json=dict(name=name),
            )

        workers_response = await client.post(
            f"/beta/workers/pools/{worker_pool.name}/workers/filter"
        )
        assert workers_response.status_code == status.HTTP_200_OK
        assert len(workers_response.json()) == 2

    async def test_heartbeat_worker_limit(self, client, worker_pool):
        for name in ["test-worker", "test-worker", "test-worker", "another-worker"]:
            response = await client.post(
                f"/beta/workers/pools/{worker_pool.name}/workers/heartbeat",
                json=dict(name=name),
            )

        workers_response = await client.post(
            f"/beta/workers/pools/{worker_pool.name}/workers/filter", json=dict(limit=1)
        )
        assert workers_response.status_code == status.HTTP_200_OK
        assert len(workers_response.json()) == 1
        assert workers_response.json()[0]["name"] == "another-worker"


class TestMigration:
    async def test_agent_pool(self, client, work_queue):
        pool_response = await client.get(
            f"/beta/workers/pools/{workers_migration.AGENT_WORKER_POOL_NAME}"
        )
        assert pool_response.status_code == status.HTTP_200_OK
        pool = pydantic.parse_obj_as(WorkerPool, pool_response.json())
        assert pool.name == workers_migration.AGENT_WORKER_POOL_NAME == "Prefect Agents"
        assert pool.description == "A worker pool for Prefect Agents"
        assert pool.type == "AGENT"

    async def test_migrate_all_work_queues(self, client, session, db):
        # create three work queues
        await client.post("/work_queues/", json=dict(name="test-queue-1"))
        await client.post("/work_queues/", json=dict(name="test-queue-2"))
        await client.post("/work_queues/", json=dict(name="test-queue-3"))

        # delete any proactive migrations to simulate old queues
        await session.execute(sa.delete(db.WorkerPool))
        await session.execute(sa.delete(db.WorkerPoolQueue))
        await session.commit()

        # migrate all work queues
        response = await client.post("/beta/workers/_migrate_all_agent_work_queues")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # check that all work queues were migrated
        wpqs = await client.get(
            f"/beta/workers/pools/{workers_migration.AGENT_WORKER_POOL_NAME}/queues"
        )
        assert len(wpqs.json()) == 4
        assert [q["name"] for q in wpqs.json()] == [
            "Default Pool",
            "test-queue-1",
            "test-queue-2",
            "test-queue-3",
        ]

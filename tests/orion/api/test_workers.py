from typing import List

import pendulum
import pydantic
import pytest
from fastapi import status

import prefect
from prefect.orion import models, schemas
from prefect.orion.schemas.actions import WorkerPoolCreate
from prefect.orion.schemas.core import WorkerPool, WorkerPoolQueue
from prefect.settings import PREFECT_EXPERIMENTAL_ENABLE_WORKERS, temporary_settings

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
    assert PREFECT_EXPERIMENTAL_ENABLE_WORKERS


class TestEnableWorkersFlag:
    async def test_flag_defaults_to_false(self):
        with temporary_settings(restore_defaults={PREFECT_EXPERIMENTAL_ENABLE_WORKERS}):
            assert not PREFECT_EXPERIMENTAL_ENABLE_WORKERS

    async def test_404_when_flag_disabled(self, client):
        with temporary_settings(restore_defaults={PREFECT_EXPERIMENTAL_ENABLE_WORKERS}):
            response = await client.post(
                "/experimental/worker_pools/", json=dict(name="Pool 1")
            )
            assert response.status_code == status.HTTP_404_NOT_FOUND


class TestCreateWorkerPool:
    async def test_create_worker_pool(self, session, client):
        response = await client.post(
            "/experimental/worker_pools/", json=dict(name="Pool 1")
        )
        assert response.status_code == status.HTTP_201_CREATED
        result = pydantic.parse_obj_as(WorkerPool, response.json())
        assert result.name == "Pool 1"
        assert result.is_paused is False
        assert result.concurrency_limit is None
        assert result.base_job_template == {}

        model = await models.workers.read_worker_pool(
            session=session, worker_pool_id=result.id
        )
        assert model.name == "Pool 1"

    async def test_create_worker_pool_with_options(self, client):
        response = await client.post(
            "/experimental/worker_pools/",
            json=dict(name="Pool 1", is_paused=True, concurrency_limit=5),
        )
        assert response.status_code == status.HTTP_201_CREATED
        result = pydantic.parse_obj_as(WorkerPool, response.json())
        assert result.name == "Pool 1"
        assert result.is_paused is True
        assert result.concurrency_limit == 5

    async def test_create_worker_pool_with_template(self, client):
        response = await client.post(
            "/experimental/worker_pools/",
            json=dict(name="Pool 1", base_job_template={"foo": "bar", "x": ["y"]}),
        )
        assert response.status_code == status.HTTP_201_CREATED
        result = pydantic.parse_obj_as(WorkerPool, response.json())
        assert result.base_job_template == {"foo": "bar", "x": ["y"]}

    async def test_create_duplicate_worker_pool(self, client, worker_pool):
        response = await client.post(
            "/experimental/worker_pools/",
            json=dict(name=worker_pool.name, type="PROCESS"),
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    @pytest.mark.parametrize("name", ["hi/there", "hi%there"])
    async def test_create_worker_pool_with_invalid_name(self, client, name):
        response = await client.post(
            "/experimental/worker_pools/", json=dict(name=name)
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.parametrize("type", [None, "PROCESS", "K8S", "AGENT"])
    async def test_create_typed_worker_pool(self, session, client, type):
        response = await client.post(
            "/experimental/worker_pools/", json=dict(name="Pool 1", type=type)
        )
        assert response.status_code == status.HTTP_201_CREATED
        result = pydantic.parse_obj_as(WorkerPool, response.json())
        assert result.type == type

    @pytest.mark.parametrize("name", RESERVED_POOL_NAMES)
    async def test_create_reserved_pool_fails(self, session, client, name):
        response = await client.post(
            "/experimental/worker_pools/", json=dict(name=name)
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "reserved for internal use" in response.json()["detail"]


class TestDeleteWorkerPool:
    async def test_delete_worker_pool(self, client, worker_pool, session):
        worker_pool_id = worker_pool.id
        response = await client.delete(f"/experimental/worker_pools/{worker_pool.name}")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not await models.workers.read_worker_pool(
            session=session, worker_pool_id=worker_pool_id
        )

    async def test_nonexistent_worker_pool(self, client):
        response = await client.delete("/experimental/worker_pools/does-not-exist")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.parametrize("name", RESERVED_POOL_NAMES)
    async def test_delete_reserved_pool_fails(self, session, client, name):
        assert await models.workers.create_worker_pool(
            session=session, worker_pool=WorkerPoolCreate(name=name)
        )
        await session.commit()

        response = await client.delete(f"/experimental/worker_pools/{name}")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "reserved for internal use" in response.json()["detail"]


class TestUpdateWorkerPool:
    async def test_update_worker_pool(self, client, session, worker_pool):
        response = await client.patch(
            f"/experimental/worker_pools/{worker_pool.name}",
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
            f"/experimental/worker_pools/{worker_pool.name}",
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
            f"/experimental/worker_pools/{worker_pool.name}",
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
            f"/experimental/worker_pools/{name}",
            json=dict(description=name, is_paused=True, concurrency_limit=5),
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "reserved for internal use" in response.json()["detail"]

        # succeeds if just pause and concurrency
        response = await client.patch(
            f"/experimental/worker_pools/{name}",
            json=dict(is_paused=True, concurrency_limit=5),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_update_worker_pool_template(self, session, client):
        name = "Pool 1"
        pool = await models.workers.create_worker_pool(
            session=session,
            worker_pool=WorkerPoolCreate(name=name, base_job_template={"a": "b"}),
        )
        await session.commit()

        response = await client.patch(
            f"/experimental/worker_pools/{name}",
            json=dict(base_job_template={"c": "d"}),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        session.expunge_all()
        result = await models.workers.read_worker_pool(
            session=session, worker_pool_id=pool.id
        )
        assert result.base_job_template == {"c": "d"}


class TestReadWorkerPool:
    async def test_read_worker_pool(self, client, worker_pool):
        response = await client.get(f"/experimental/worker_pools/{worker_pool.name}")
        assert response.status_code == status.HTTP_200_OK
        result = pydantic.parse_obj_as(WorkerPool, response.json())
        assert result.name == worker_pool.name
        assert result.id == worker_pool.id

    async def test_read_invalid_config(self, client):
        response = await client.get("/experimental/worker_pools/does-not-exist")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReadWorkerPools:
    @pytest.fixture(autouse=True)
    async def create_worker_pools(self, client):
        for name in ["C", "B", "A"]:
            await client.post("/experimental/worker_pools/", json=dict(name=name))

    async def test_read_worker_pools(self, client, session):
        response = await client.post("/experimental/worker_pools/filter")
        assert response.status_code == status.HTTP_200_OK
        result = pydantic.parse_obj_as(List[WorkerPool], response.json())
        assert [r.name for r in result] == ["A", "B", "C"]

    async def test_read_worker_pools_with_limit(self, client, session):
        response = await client.post(
            "/experimental/worker_pools/filter", json=dict(limit=2)
        )
        assert response.status_code == status.HTTP_200_OK
        result = pydantic.parse_obj_as(List[WorkerPool], response.json())
        assert [r.name for r in result] == ["A", "B"]

    async def test_read_worker_pools_with_offset(self, client, session):
        response = await client.post(
            "/experimental/worker_pools/filter", json=dict(offset=1)
        )
        assert response.status_code == status.HTTP_200_OK
        result = pydantic.parse_obj_as(List[WorkerPool], response.json())
        assert [r.name for r in result] == ["B", "C"]


class TestCreateWorkerPoolQueue:
    async def test_create_worker_pool_queue(self, client, worker_pool):
        response = await client.post(
            f"/experimental/worker_pools/{worker_pool.name}/queues",
            json=dict(name="test-queue", description="test queue"),
        )
        assert response.status_code == status.HTTP_201_CREATED
        result = pydantic.parse_obj_as(WorkerPoolQueue, response.json())
        assert result.name == "test-queue"
        assert result.description == "test queue"


class TestReadWorkerPoolQueue:
    async def test_read_worker_pool_queue(self, client, worker_pool):
        # Create worker pool queue
        create_response = await client.post(
            f"/experimental/worker_pools/{worker_pool.name}/queues",
            json=dict(name="test-queue", description="test queue"),
        )
        assert create_response.status_code == status.HTTP_201_CREATED

        read_response = await client.get(
            f"/experimental/worker_pools/{worker_pool.name}/queues/test-queue"
        )
        assert read_response.status_code == status.HTTP_200_OK
        result = pydantic.parse_obj_as(WorkerPoolQueue, read_response.json())
        assert result.name == "test-queue"
        assert result.description == "test queue"


class TestUpdateWorkerPoolQueue:
    async def test_update_worker_pool_queue(self, client, worker_pool):
        # Create worker pool queue
        create_response = await client.post(
            f"/experimental/worker_pools/{worker_pool.name}/queues",
            json=dict(name="test-queue", description="test queue"),
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        create_result = pydantic.parse_obj_as(WorkerPoolQueue, create_response.json())
        assert not create_result.is_paused

        # Update worker pool queue
        update_response = await client.patch(
            f"/experimental/worker_pools/{worker_pool.name}/queues/test-queue",
            json=dict(
                name="updated-test-queue",
                description="updated test queue",
                is_paused=True,
            ),
        )
        assert update_response.status_code == status.HTTP_204_NO_CONTENT

        # Read updated worker pool queue
        read_response = await client.get(
            f"/experimental/worker_pools/{worker_pool.name}/queues/updated-test-queue"
        )
        assert read_response.status_code == status.HTTP_200_OK
        result = pydantic.parse_obj_as(WorkerPoolQueue, read_response.json())
        assert result.name == "updated-test-queue"
        assert result.description == "updated test queue"
        assert result.is_paused


class TestWorkerProcess:
    async def test_heartbeat_worker(self, client, worker_pool):
        workers_response = await client.post(
            f"/experimental/worker_pools/{worker_pool.name}/workers/filter"
        )
        assert workers_response.status_code == status.HTTP_200_OK
        assert len(workers_response.json()) == 0

        dt = pendulum.now()
        response = await client.post(
            f"/experimental/worker_pools/{worker_pool.name}/workers/heartbeat",
            json=dict(name="test-worker"),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        workers_response = await client.post(
            f"/experimental/worker_pools/{worker_pool.name}/workers/filter"
        )
        assert workers_response.status_code == status.HTTP_200_OK
        assert len(workers_response.json()) == 1
        assert workers_response.json()[0]["name"] == "test-worker"
        assert pendulum.parse(workers_response.json()[0]["last_heartbeat_time"]) > dt

    async def test_heartbeat_worker_requires_name(self, client, worker_pool):
        response = await client.post(
            f"/experimental/worker_pools/{worker_pool.name}/workers/heartbeat"
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert b"field required" in response.content

    async def test_heartbeat_worker_upserts_for_same_name(self, client, worker_pool):
        for name in ["test-worker", "test-worker", "test-worker", "another-worker"]:
            response = await client.post(
                f"/experimental/worker_pools/{worker_pool.name}/workers/heartbeat",
                json=dict(name=name),
            )

        workers_response = await client.post(
            f"/experimental/worker_pools/{worker_pool.name}/workers/filter"
        )
        assert workers_response.status_code == status.HTTP_200_OK
        assert len(workers_response.json()) == 2

    async def test_heartbeat_worker_limit(self, client, worker_pool):
        for name in ["test-worker", "test-worker", "test-worker", "another-worker"]:
            response = await client.post(
                f"/experimental/worker_pools/{worker_pool.name}/workers/heartbeat",
                json=dict(name=name),
            )

        workers_response = await client.post(
            f"/experimental/worker_pools/{worker_pool.name}/workers/filter",
            json=dict(limit=1),
        )
        assert workers_response.status_code == status.HTTP_200_OK
        assert len(workers_response.json()) == 1
        assert workers_response.json()[0]["name"] == "another-worker"


class TestGetScheduledRuns:
    @pytest.fixture(autouse=True)
    async def setup(self, session, flow):
        """
        Creates:
        - Three different worker pools ("A", "B", "C")
        - Three different queues in each pool ("AA", "AB", "AC", "BA", "BB", "BC", "CA", "CB", "CC")
        - One pending run, one running run, and 5 scheduled runs in each queue
        """

        # create three different worker pools
        wp_a = await models.workers.create_worker_pool(
            session=session,
            worker_pool=schemas.actions.WorkerPoolCreate(name="A"),
        )
        wp_b = await models.workers.create_worker_pool(
            session=session,
            worker_pool=schemas.actions.WorkerPoolCreate(name="B"),
        )
        wp_c = await models.workers.create_worker_pool(
            session=session,
            worker_pool=schemas.actions.WorkerPoolCreate(name="C"),
        )

        # create three different work queues for each config
        wq_aa = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=wp_a.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="AA"),
        )
        wq_ab = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=wp_a.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="AB"),
        )
        wq_ac = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=wp_a.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="AC"),
        )
        wq_ba = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=wp_b.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="BA"),
        )
        wq_bb = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=wp_b.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="BB"),
        )
        wq_bc = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=wp_b.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="BC"),
        )
        wq_ca = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=wp_c.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="CA"),
        )
        wq_cb = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=wp_c.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="CB"),
        )
        wq_cc = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=wp_c.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="CC"),
        )

        # create flow runs
        for wq in [wq_aa, wq_ab, wq_ac, wq_ba, wq_bb, wq_bc, wq_ca, wq_cb, wq_cc]:
            # create a running run
            await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id,
                    state=prefect.states.Running(),
                    worker_pool_queue_id=wq.id,
                ),
            )

            # create a pending run
            await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id,
                    state=prefect.states.Pending(),
                    worker_pool_queue_id=wq.id,
                ),
            )

            # create 5 scheduled runs from two hours ago to three hours in the future
            # we insert them in reverse order to ensure that sorting is taking
            # place (and not just returning the database order)
            for i in range(3, -2, -1):
                await models.flow_runs.create_flow_run(
                    session=session,
                    flow_run=schemas.core.FlowRun(
                        flow_id=flow.id,
                        state=prefect.states.Scheduled(
                            scheduled_time=pendulum.now().add(hours=i)
                        ),
                        worker_pool_queue_id=wq.id,
                    ),
                )
        await session.commit()

        return dict(
            worker_pools=dict(wp_a=wp_a, wp_b=wp_b, wp_c=wp_c),
            worker_pool_queues=dict(
                wq_aa=wq_aa,
                wq_ab=wq_ab,
                wq_ac=wq_ac,
                wq_ba=wq_ba,
                wq_bb=wq_bb,
                wq_bc=wq_bc,
                wq_ca=wq_ca,
                wq_cb=wq_cb,
                wq_cc=wq_cc,
            ),
        )

    @pytest.fixture
    def worker_pools(self, setup):
        return setup["worker_pools"]

    @pytest.fixture
    def worker_pool_queues(self, setup):
        return setup["worker_pool_queues"]

    async def test_get_all_runs(self, client, worker_pools):
        response = await client.post(
            f"/experimental/worker_pools/{worker_pools['wp_a'].name}/get_scheduled_flow_runs",
        )
        assert response.status_code == status.HTTP_200_OK

        data = pydantic.parse_obj_as(
            List[schemas.responses.WorkerFlowRunResponse], response.json()
        )
        assert len(data) == 15

        # runs are not sorted by time because they're sorted by queue priority
        assert data != sorted(data, key=lambda r: r.flow_run.next_scheduled_start_time)

    async def test_get_all_runs_limit(self, client, worker_pools):
        response = await client.post(
            f"/experimental/worker_pools/{worker_pools['wp_a'].name}/get_scheduled_flow_runs",
            json=dict(limit=7),
        )

        data = pydantic.parse_obj_as(
            List[schemas.responses.WorkerFlowRunResponse], response.json()
        )
        assert len(data) == 7

    async def test_get_all_runs_wq_aa(self, client, worker_pools, worker_pool_queues):
        response = await client.post(
            f"/experimental/worker_pools/{worker_pools['wp_a'].name}/get_scheduled_flow_runs",
            json=dict(worker_pool_queue_names=[worker_pool_queues["wq_aa"].name]),
        )

        data = pydantic.parse_obj_as(
            List[schemas.responses.WorkerFlowRunResponse], response.json()
        )
        assert len(data) == 5

    async def test_get_all_runs_wq_aa_wq_ab(
        self, client, worker_pools, worker_pool_queues
    ):
        response = await client.post(
            f"/experimental/worker_pools/{worker_pools['wp_a'].name}/get_scheduled_flow_runs",
            json=dict(
                worker_pool_queue_names=[
                    worker_pool_queues["wq_aa"].name,
                    worker_pool_queues["wq_ab"].name,
                ]
            ),
        )

        data = pydantic.parse_obj_as(
            List[schemas.responses.WorkerFlowRunResponse], response.json()
        )
        assert len(data) == 10

    async def test_get_all_runs_wq_ba_wrong_pool(
        self, client, worker_pools, worker_pool_queues
    ):
        response = await client.post(
            f"/experimental/worker_pools/{worker_pools['wp_a'].name}/get_scheduled_flow_runs",
            json=dict(worker_pool_queue_names=[worker_pool_queues["wq_ba"].name]),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_get_all_runs_scheduled_before(
        self, client, worker_pools, worker_pool_queues
    ):
        response = await client.post(
            f"/experimental/worker_pools/{worker_pools['wp_a'].name}/get_scheduled_flow_runs",
            json=dict(scheduled_before=str(pendulum.now())),
        )

        data = pydantic.parse_obj_as(
            List[schemas.responses.WorkerFlowRunResponse], response.json()
        )
        assert len(data) == 6

    async def test_get_all_runs_scheduled_after(self, client, worker_pools):
        response = await client.post(
            f"/experimental/worker_pools/{worker_pools['wp_a'].name}/get_scheduled_flow_runs",
            json=dict(scheduled_after=str(pendulum.now())),
        )

        data = pydantic.parse_obj_as(
            List[schemas.responses.WorkerFlowRunResponse], response.json()
        )
        assert len(data) == 9

    async def test_get_all_runs_scheduled_before_and_after(self, client, worker_pools):
        response = await client.post(
            f"/experimental/worker_pools/{worker_pools['wp_a'].name}/get_scheduled_flow_runs",
            json=dict(
                scheduled_before=str(pendulum.now().subtract(hours=1)),
                scheduled_after=str(pendulum.now()),
            ),
        )

        data = pydantic.parse_obj_as(
            List[schemas.responses.WorkerFlowRunResponse], response.json()
        )
        assert len(data) == 0

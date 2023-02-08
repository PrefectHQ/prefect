from typing import List

import pendulum
import pydantic
import pytest
from fastapi import status

import prefect
from prefect.orion import models, schemas
from prefect.orion.schemas.actions import WorkPoolCreate
from prefect.orion.schemas.core import WorkPool, WorkQueue

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


class TestCreateWorkPool:
    async def test_create_work_pool(self, session, client):
        response = await client.post(
            "/work_pools/", json=dict(name="Pool 1", type="test")
        )
        assert response.status_code == status.HTTP_201_CREATED
        result = pydantic.parse_obj_as(WorkPool, response.json())
        assert result.name == "Pool 1"
        assert result.is_paused is False
        assert result.concurrency_limit is None
        assert result.base_job_template == {}

        model = await models.workers.read_work_pool(
            session=session, work_pool_id=result.id
        )
        assert model.name == "Pool 1"

    async def test_create_work_pool_with_options(self, client):
        response = await client.post(
            "/work_pools/",
            json=dict(name="Pool 1", type="test", is_paused=True, concurrency_limit=5),
        )
        assert response.status_code == status.HTTP_201_CREATED
        result = pydantic.parse_obj_as(WorkPool, response.json())
        assert result.name == "Pool 1"
        assert result.is_paused is True
        assert result.concurrency_limit == 5

    async def test_create_work_pool_with_template(self, client):
        base_job_template = {
            "job_configuration": {
                "command": "{{ command }}",
            },
            "variables": {
                "properties": {
                    "command": {
                        "type": "array",
                        "title": "Command",
                        "items": {"type": "string"},
                        "default": ["echo", "hello"],
                    }
                },
                "required": [],
            },
        }

        response = await client.post(
            "/work_pools/",
            json=dict(name="Pool 1", type="test", base_job_template=base_job_template),
        )
        assert response.status_code == status.HTTP_201_CREATED
        result = pydantic.parse_obj_as(WorkPool, response.json())
        assert result.base_job_template == base_job_template

    async def test_create_duplicate_work_pool(self, client, work_pool):
        response = await client.post(
            "/work_pools/",
            json=dict(name=work_pool.name, type="PROCESS"),
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    @pytest.mark.parametrize("name", ["hi/there", "hi%there"])
    async def test_create_work_pool_with_invalid_name(self, client, name):
        response = await client.post("/work_pools/", json=dict(name=name))
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.parametrize("type", ["PROCESS", "K8S", "AGENT"])
    async def test_create_typed_work_pool(self, session, client, type):
        response = await client.post(
            "/work_pools/", json=dict(name="Pool 1", type=type)
        )
        assert response.status_code == status.HTTP_201_CREATED
        result = pydantic.parse_obj_as(WorkPool, response.json())
        assert result.type == type

    @pytest.mark.parametrize("name", RESERVED_POOL_NAMES)
    async def test_create_reserved_pool_fails(self, session, client, name):
        response = await client.post("/work_pools/", json=dict(name=name))
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "reserved for internal use" in response.json()["detail"]

    async def test_create_work_pool_template_validation_missing_keys(self, client):
        response = await client.post(
            "/work_pools/",
            json=dict(name="Pool 1", base_job_template={"foo": "bar", "x": ["y"]}),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert (
            "The `base_job_template` must contain both a `job_configuration` key and a `variables` key."
            in response.json()["exception_detail"][0]["msg"]
        )

    async def test_create_work_pool_template_validation_missing_variables(self, client):
        missing_variable_template = {
            "job_configuration": {
                "command": "{{ other_variable }}",
            },
            "variables": {
                "properties": {
                    "command": {
                        "type": "array",
                        "title": "Command",
                        "items": {"type": "string"},
                        "default": ["echo", "hello"],
                    },
                },
                "required": [],
            },
        }
        response = await client.post(
            "/work_pools/",
            json=dict(name="Pool 1", base_job_template=missing_variable_template),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert (
            "The variables specified in the job configuration template must be present as "
            "attributes in the variables class. Your job expects the following variables: "
            "{'other_variable'}, but your template provides: {'command'}"
        ) in response.json()["exception_detail"][0]["msg"]


class TestDeleteWorkPool:
    async def test_delete_work_pool(self, client, work_pool, session):
        work_pool_id = work_pool.id
        response = await client.delete(f"/work_pools/{work_pool.name}")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not await models.workers.read_work_pool(
            session=session, work_pool_id=work_pool_id
        )

    async def test_nonexistent_work_pool(self, client):
        response = await client.delete("/work_pools/does-not-exist")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.parametrize("name", RESERVED_POOL_NAMES)
    async def test_delete_reserved_pool_fails(self, session, client, name):
        assert await models.workers.create_work_pool(
            session=session, work_pool=WorkPoolCreate(name=name)
        )
        await session.commit()

        response = await client.delete(f"/work_pools/{name}")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "reserved for internal use" in response.json()["detail"]


class TestUpdateWorkPool:
    async def test_update_work_pool(self, client, session, work_pool):
        response = await client.patch(
            f"/work_pools/{work_pool.name}",
            json=dict(is_paused=True, concurrency_limit=5),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        session.expunge_all()
        result = await models.workers.read_work_pool(
            session=session, work_pool_id=work_pool.id
        )
        assert result.is_paused is True
        assert result.concurrency_limit == 5

    async def test_update_work_pool_zero_concurrency(
        self, client, session, work_pool, db
    ):
        response = await client.patch(
            f"/work_pools/{work_pool.name}",
            json=dict(concurrency_limit=0),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        async with db.session_context() as session:
            result = await models.workers.read_work_pool(
                session=session, work_pool_id=work_pool.id
            )
        assert result.concurrency_limit == 0

    async def test_update_work_pool_invalid_concurrency(
        self, client, session, work_pool
    ):
        response = await client.patch(
            f"/work_pools/{work_pool.name}",
            json=dict(concurrency_limit=-5),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        session.expunge_all()
        result = await models.workers.read_work_pool(
            session=session, work_pool_id=work_pool.id
        )
        assert result.concurrency_limit is None

    @pytest.mark.parametrize("name", RESERVED_POOL_NAMES)
    async def test_update_reserved_pool(self, session, client, name):
        assert await models.workers.create_work_pool(
            session=session, work_pool=WorkPoolCreate(name=name)
        )
        await session.commit()

        # fails if we try to update the description
        response = await client.patch(
            f"/work_pools/{name}",
            json=dict(description=name, is_paused=True, concurrency_limit=5),
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "reserved for internal use" in response.json()["detail"]

        # succeeds if just pause and concurrency
        response = await client.patch(
            f"/work_pools/{name}",
            json=dict(is_paused=True, concurrency_limit=5),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_update_work_pool_template(self, session, client):
        name = "Pool 1"

        base_job_template = {
            "job_configuration": {
                "command": "{{ command }}",
            },
            "variables": {
                "properties": {
                    "command": {
                        "type": "array",
                        "title": "Command",
                        "items": {"type": "string"},
                        "default": ["echo", "hello"],
                    },
                },
                "required": [],
            },
        }
        pool = await models.workers.create_work_pool(
            session=session,
            work_pool=WorkPoolCreate(name=name, base_job_template=base_job_template),
        )
        await session.commit()

        base_job_template["variables"]["properties"]["command"]["default"] = ["woof!"]
        response = await client.patch(
            f"/work_pools/{name}",
            json=dict(base_job_template=base_job_template),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        session.expunge_all()
        result = await models.workers.read_work_pool(
            session=session, work_pool_id=pool.id
        )
        assert result.base_job_template["variables"]["properties"]["command"][
            "default"
        ] == ["woof!"]

    async def test_update_work_pool_template_validation_missing_keys(
        self, client, session
    ):
        name = "Pool 1"

        pool = await models.workers.create_work_pool(
            session=session,
            work_pool=WorkPoolCreate(name=name),
        )
        await session.commit()

        session.expunge_all()

        response = await client.patch(
            f"/work_pools/{name}",
            json=dict(name=name, base_job_template={"foo": "bar", "x": ["y"]}),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert (
            "The `base_job_template` must contain both a `job_configuration` key and a `variables` key."
            in response.json()["exception_detail"][0]["msg"]
        )

    async def test_create_work_pool_template_validation_missing_variables(
        self, client, session
    ):
        name = "Pool 1"
        missing_variable_template = {
            "job_configuration": {
                "command": "{{ other_variable }}",
            },
            "variables": {
                "properties": {
                    "command": {
                        "type": "array",
                        "title": "Command",
                        "items": {"type": "string"},
                        "default": ["echo", "hello"],
                    },
                },
                "required": [],
            },
        }
        pool = await models.workers.create_work_pool(
            session=session,
            work_pool=WorkPoolCreate(name=name),
        )
        await session.commit()

        session.expunge_all()

        response = await client.patch(
            f"/work_pools/{name}",
            json=dict(name=name, base_job_template=missing_variable_template),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert (
            "The variables specified in the job configuration template must be present as "
            "attributes in the variables class. Your job expects the following variables: "
            "{'other_variable'}, but your template provides: {'command'}"
        ) in response.json()["exception_detail"][0]["msg"]


class TestReadWorkPool:
    async def test_read_work_pool(self, client, work_pool):
        response = await client.get(f"/work_pools/{work_pool.name}")
        assert response.status_code == status.HTTP_200_OK
        result = pydantic.parse_obj_as(WorkPool, response.json())
        assert result.name == work_pool.name
        assert result.id == work_pool.id

    async def test_read_invalid_config(self, client):
        response = await client.get("/work_pools/does-not-exist")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReadWorkPools:
    @pytest.fixture(autouse=True)
    async def create_work_pools(self, client):
        for name in ["C", "B", "A"]:
            await client.post("/work_pools/", json=dict(name=name, type="test"))

    async def test_read_work_pools(self, client, session):
        response = await client.post("/work_pools/filter")
        assert response.status_code == status.HTTP_200_OK
        result = pydantic.parse_obj_as(List[WorkPool], response.json())
        assert [r.name for r in result] == ["A", "B", "C"]

    async def test_read_work_pools_with_limit(self, client, session):
        response = await client.post("/work_pools/filter", json=dict(limit=2))
        assert response.status_code == status.HTTP_200_OK
        result = pydantic.parse_obj_as(List[WorkPool], response.json())
        assert [r.name for r in result] == ["A", "B"]

    async def test_read_work_pools_with_offset(self, client, session):
        response = await client.post("/work_pools/filter", json=dict(offset=1))
        assert response.status_code == status.HTTP_200_OK
        result = pydantic.parse_obj_as(List[WorkPool], response.json())
        assert [r.name for r in result] == ["B", "C"]


class TestCreateWorkQueue:
    async def test_create_work_queue(self, client, work_pool):
        response = await client.post(
            f"/work_pools/{work_pool.name}/queues",
            json=dict(name="test-queue", description="test queue"),
        )
        assert response.status_code == status.HTTP_201_CREATED
        result = pydantic.parse_obj_as(WorkQueue, response.json())
        assert result.name == "test-queue"
        assert result.description == "test queue"


class TestReadWorkQueue:
    async def test_read_work_queue(self, client, work_pool):
        # Create work pool queue
        create_response = await client.post(
            f"/work_pools/{work_pool.name}/queues",
            json=dict(name="test-queue", description="test queue"),
        )
        assert create_response.status_code == status.HTTP_201_CREATED

        read_response = await client.get(
            f"/work_pools/{work_pool.name}/queues/test-queue"
        )
        assert read_response.status_code == status.HTTP_200_OK
        result = pydantic.parse_obj_as(WorkQueue, read_response.json())
        assert result.name == "test-queue"
        assert result.description == "test queue"


class TestUpdateWorkQueue:
    async def test_update_work_queue(self, client, work_pool):
        # Create work pool queue
        create_response = await client.post(
            f"/work_pools/{work_pool.name}/queues",
            json=dict(name="test-queue", description="test queue"),
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        create_result = pydantic.parse_obj_as(WorkQueue, create_response.json())
        assert not create_result.is_paused

        # Update work pool queue
        update_response = await client.patch(
            f"/work_pools/{work_pool.name}/queues/test-queue",
            json=dict(
                name="updated-test-queue",
                description="updated test queue",
                is_paused=True,
            ),
        )
        assert update_response.status_code == status.HTTP_204_NO_CONTENT

        # Read updated work pool queue
        read_response = await client.get(
            f"/work_pools/{work_pool.name}/queues/updated-test-queue"
        )
        assert read_response.status_code == status.HTTP_200_OK
        result = pydantic.parse_obj_as(WorkQueue, read_response.json())
        assert result.name == "updated-test-queue"
        assert result.description == "updated test queue"
        assert result.is_paused


class TestWorkerProcess:
    async def test_heartbeat_worker(self, client, work_pool):
        workers_response = await client.post(
            f"/work_pools/{work_pool.name}/workers/filter"
        )
        assert workers_response.status_code == status.HTTP_200_OK
        assert len(workers_response.json()) == 0

        dt = pendulum.now()
        response = await client.post(
            f"/work_pools/{work_pool.name}/workers/heartbeat",
            json=dict(name="test-worker"),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        workers_response = await client.post(
            f"/work_pools/{work_pool.name}/workers/filter"
        )
        assert workers_response.status_code == status.HTTP_200_OK
        assert len(workers_response.json()) == 1
        assert workers_response.json()[0]["name"] == "test-worker"
        assert pendulum.parse(workers_response.json()[0]["last_heartbeat_time"]) > dt

    async def test_heartbeat_worker_requires_name(self, client, work_pool):
        response = await client.post(f"/work_pools/{work_pool.name}/workers/heartbeat")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert b"field required" in response.content

    async def test_heartbeat_worker_upserts_for_same_name(self, client, work_pool):
        for name in ["test-worker", "test-worker", "test-worker", "another-worker"]:
            response = await client.post(
                f"/work_pools/{work_pool.name}/workers/heartbeat",
                json=dict(name=name),
            )

        workers_response = await client.post(
            f"/work_pools/{work_pool.name}/workers/filter"
        )
        assert workers_response.status_code == status.HTTP_200_OK
        assert len(workers_response.json()) == 2

    async def test_heartbeat_worker_limit(self, client, work_pool):
        for name in ["test-worker", "test-worker", "test-worker", "another-worker"]:
            response = await client.post(
                f"/work_pools/{work_pool.name}/workers/heartbeat",
                json=dict(name=name),
            )

        workers_response = await client.post(
            f"/work_pools/{work_pool.name}/workers/filter",
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
        - Three different work pools ("A", "B", "C")
        - Three different queues in each pool ("AA", "AB", "AC", "BA", "BB", "BC", "CA", "CB", "CC")
        - One pending run, one running run, and 5 scheduled runs in each queue
        """

        # create three different work pools
        wp_a = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(name="A"),
        )
        wp_b = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(name="B"),
        )
        wp_c = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(name="C"),
        )

        # create three different work queues for each config
        wq_aa = await models.workers.create_work_queue(
            session=session,
            work_pool_id=wp_a.id,
            work_queue=schemas.actions.WorkQueueCreate(name="AA"),
        )
        wq_ab = await models.workers.create_work_queue(
            session=session,
            work_pool_id=wp_a.id,
            work_queue=schemas.actions.WorkQueueCreate(name="AB"),
        )
        wq_ac = await models.workers.create_work_queue(
            session=session,
            work_pool_id=wp_a.id,
            work_queue=schemas.actions.WorkQueueCreate(name="AC"),
        )
        wq_ba = await models.workers.create_work_queue(
            session=session,
            work_pool_id=wp_b.id,
            work_queue=schemas.actions.WorkQueueCreate(name="BA"),
        )
        wq_bb = await models.workers.create_work_queue(
            session=session,
            work_pool_id=wp_b.id,
            work_queue=schemas.actions.WorkQueueCreate(name="BB"),
        )
        wq_bc = await models.workers.create_work_queue(
            session=session,
            work_pool_id=wp_b.id,
            work_queue=schemas.actions.WorkQueueCreate(name="BC"),
        )
        wq_ca = await models.workers.create_work_queue(
            session=session,
            work_pool_id=wp_c.id,
            work_queue=schemas.actions.WorkQueueCreate(name="CA"),
        )
        wq_cb = await models.workers.create_work_queue(
            session=session,
            work_pool_id=wp_c.id,
            work_queue=schemas.actions.WorkQueueCreate(name="CB"),
        )
        wq_cc = await models.workers.create_work_queue(
            session=session,
            work_pool_id=wp_c.id,
            work_queue=schemas.actions.WorkQueueCreate(name="CC"),
        )

        # create flow runs
        for wq in [wq_aa, wq_ab, wq_ac, wq_ba, wq_bb, wq_bc, wq_ca, wq_cb, wq_cc]:
            # create a running run
            await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id,
                    state=prefect.states.Running(),
                    work_queue_id=wq.id,
                ),
            )

            # create a pending run
            await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id,
                    state=prefect.states.Pending(),
                    work_queue_id=wq.id,
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
                        work_queue_id=wq.id,
                    ),
                )
        await session.commit()

        return dict(
            work_pools=dict(wp_a=wp_a, wp_b=wp_b, wp_c=wp_c),
            work_queues=dict(
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
    def work_pools(self, setup):
        return setup["work_pools"]

    @pytest.fixture
    def work_queues(self, setup):
        return setup["work_queues"]

    async def test_get_all_runs(self, client, work_pools):
        response = await client.post(
            f"/work_pools/{work_pools['wp_a'].name}/get_scheduled_flow_runs",
        )
        assert response.status_code == status.HTTP_200_OK

        data = pydantic.parse_obj_as(
            List[schemas.responses.WorkerFlowRunResponse], response.json()
        )
        assert len(data) == 15

        # runs are not sorted by time because they're sorted by queue priority
        assert data != sorted(data, key=lambda r: r.flow_run.next_scheduled_start_time)

    async def test_get_all_runs_limit(self, client, work_pools):
        response = await client.post(
            f"/work_pools/{work_pools['wp_a'].name}/get_scheduled_flow_runs",
            json=dict(limit=7),
        )

        data = pydantic.parse_obj_as(
            List[schemas.responses.WorkerFlowRunResponse], response.json()
        )
        assert len(data) == 7

    async def test_get_all_runs_wq_aa(self, client, work_pools, work_queues):
        response = await client.post(
            f"/work_pools/{work_pools['wp_a'].name}/get_scheduled_flow_runs",
            json=dict(work_queue_names=[work_queues["wq_aa"].name]),
        )

        data = pydantic.parse_obj_as(
            List[schemas.responses.WorkerFlowRunResponse], response.json()
        )
        assert len(data) == 5

    async def test_get_all_runs_wq_aa_wq_ab(self, client, work_pools, work_queues):
        response = await client.post(
            f"/work_pools/{work_pools['wp_a'].name}/get_scheduled_flow_runs",
            json=dict(
                work_queue_names=[
                    work_queues["wq_aa"].name,
                    work_queues["wq_ab"].name,
                ]
            ),
        )

        data = pydantic.parse_obj_as(
            List[schemas.responses.WorkerFlowRunResponse], response.json()
        )
        assert len(data) == 10

    async def test_get_all_runs_wq_ba_wrong_pool(self, client, work_pools, work_queues):
        response = await client.post(
            f"/work_pools/{work_pools['wp_a'].name}/get_scheduled_flow_runs",
            json=dict(work_queue_names=[work_queues["wq_ba"].name]),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_get_all_runs_scheduled_before(self, client, work_pools, work_queues):
        response = await client.post(
            f"/work_pools/{work_pools['wp_a'].name}/get_scheduled_flow_runs",
            json=dict(scheduled_before=str(pendulum.now())),
        )

        data = pydantic.parse_obj_as(
            List[schemas.responses.WorkerFlowRunResponse], response.json()
        )
        assert len(data) == 6

    async def test_get_all_runs_scheduled_after(self, client, work_pools):
        response = await client.post(
            f"/work_pools/{work_pools['wp_a'].name}/get_scheduled_flow_runs",
            json=dict(scheduled_after=str(pendulum.now())),
        )

        data = pydantic.parse_obj_as(
            List[schemas.responses.WorkerFlowRunResponse], response.json()
        )
        assert len(data) == 9

    async def test_get_all_runs_scheduled_before_and_after(self, client, work_pools):
        response = await client.post(
            f"/work_pools/{work_pools['wp_a'].name}/get_scheduled_flow_runs",
            json=dict(
                scheduled_before=str(pendulum.now().subtract(hours=1)),
                scheduled_after=str(pendulum.now()),
            ),
        )

        data = pydantic.parse_obj_as(
            List[schemas.responses.WorkerFlowRunResponse], response.json()
        )
        assert len(data) == 0

    async def test_updates_last_polled_on_a_single_work_queue(
        self, client, work_queues, work_pools
    ):
        now = pendulum.now()
        poll_response = await client.post(
            f"/work_pools/{work_pools['wp_a'].name}/get_scheduled_flow_runs",
            json=dict(work_queue_names=[work_queues["wq_aa"].name]),
        )
        assert poll_response.status_code == status.HTTP_200_OK

        work_queue_response = await client.get(
            f"/work_pools/{work_pools['wp_a'].name}/queues/{work_queues['wq_aa'].name}"
        )
        assert work_queue_response.status_code == status.HTTP_200_OK

        work_queue = pydantic.parse_obj_as(WorkQueue, work_queue_response.json())
        work_queues_response = await client.post(
            f"/work_pools/{work_pools['wp_a'].name}/queues/filter"
        )
        assert work_queues_response.status_code == status.HTTP_200_OK

        work_queues = pydantic.parse_obj_as(
            List[WorkQueue], work_queues_response.json()
        )

        for work_queue in work_queues:
            if work_queue.name == "AA":
                assert work_queue.last_polled is not None
                assert work_queue.last_polled > now
            else:
                assert work_queue.last_polled is None

    async def test_updates_last_polled_on_a_multiple_work_queues(
        self, client, work_queues, work_pools
    ):
        now = pendulum.now()
        poll_response = await client.post(
            f"/work_pools/{work_pools['wp_a'].name}/get_scheduled_flow_runs",
            json=dict(
                work_queue_names=[
                    work_queues["wq_aa"].name,
                    work_queues["wq_ab"].name,
                ]
            ),
        )
        assert poll_response.status_code == status.HTTP_200_OK

        work_queues_response = await client.post(
            f"/work_pools/{work_pools['wp_a'].name}/queues/filter"
        )
        assert work_queues_response.status_code == status.HTTP_200_OK

        work_queues = pydantic.parse_obj_as(
            List[WorkQueue], work_queues_response.json()
        )

        for work_queue in work_queues:
            if work_queue.name == "AA" or work_queue.name == "AB":
                assert work_queue.last_polled is not None
                assert work_queue.last_polled > now
            else:
                assert work_queue.last_polled is None

    async def test_updates_last_polled_on_a_full_work_pool(
        self, client, work_queues, work_pools
    ):
        now = pendulum.now()
        poll_response = await client.post(
            f"/work_pools/{work_pools['wp_a'].name}/get_scheduled_flow_runs",
        )
        assert poll_response.status_code == status.HTTP_200_OK

        work_queues_response = await client.post(
            f"/work_pools/{work_pools['wp_a'].name}/queues/filter"
        )
        assert work_queues_response.status_code == status.HTTP_200_OK

        work_queues = pydantic.parse_obj_as(
            List[WorkQueue], work_queues_response.json()
        )

        for work_queue in work_queues:
            assert work_queue.last_polled is not None
            assert work_queue.last_polled > now

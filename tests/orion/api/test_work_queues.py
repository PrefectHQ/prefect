from uuid import uuid4

import pendulum
import pytest

from prefect.orion import models, schemas
from prefect.orion.schemas.actions import WorkQueueCreate, WorkQueueUpdate


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

    async def test_create_work_queue_raises_error_on_existing_name(
        self, client, work_queue
    ):
        data = WorkQueueCreate(
            name=work_queue.name,
        ).dict(json_compatible=True)
        response = await client.post("/work_queues/", json=data)
        assert response.status_code == 409

    @pytest.mark.parametrize(
        "name",
        [
            "work/queue",
            r"work%queue",
        ],
    )
    async def test_create_work_queue_with_invalid_characters_fails(self, client, name):
        response = await client.post("/work_queues/", json=dict(name=name))
        assert response.status_code == 422
        assert b"contains an invalid character" in response.content


class TestUpdateWorkQueue:
    async def test_update_work_queue(
        self,
        session,
        client,
    ):
        now = pendulum.now(tz="UTC")
        data = WorkQueueCreate(
            name="My WorkQueue", filter=schemas.core.QueueFilter(tags=["foo", "bar"])
        ).dict(json_compatible=True, exclude_unset=True)
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

        assert response.status_code == 204

        response = await client.get(f"/work_queues/{work_queue_id}")

        assert response.json()["is_paused"] is True
        assert response.json()["concurrency_limit"] == 3


class TestReadWorkQueue:
    async def test_read_work_queue(self, client, work_queue):
        response = await client.get(f"/work_queues/{work_queue.id}")
        assert response.status_code == 200
        assert response.json()["id"] == str(work_queue.id)
        assert response.json()["name"] == "My WorkQueue"

    async def test_read_work_queue_returns_404_if_does_not_exist(self, client):
        response = await client.get(f"/work_queues/{uuid4()}")
        assert response.status_code == 404


class TestReadWorkQueueByName:
    async def test_read_work_queue_by_name(self, client, work_queue):
        response = await client.get(f"/work_queues/name/{work_queue.name}")
        assert response.status_code == 200
        assert response.json()["id"] == str(work_queue.id)
        assert response.json()["name"] == work_queue.name

    async def test_read_work_queue_returns_404_if_does_not_exist(self, client):
        response = await client.get(f"/work_queues/name/some-made-up-work-queue")
        assert response.status_code == 404

    @pytest.mark.parametrize(
        "name",
        [
            "work queue",
            "work:queue",
            "work\queue",
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
        assert response.status_code == 200
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
    @pytest.fixture
    async def flow_run_1_id(self):
        return uuid4()

    @pytest.fixture
    async def flow_run_2_id(self):
        return uuid4()

    @pytest.fixture(autouse=True)
    async def flow_runs(
        self,
        session,
        deployment,
        flow_run_1_id,
        flow_run_2_id,
    ):

        # flow run 1 is in a SCHEDULED state 5 seconds ago
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                id=flow_run_1_id,
                flow_id=deployment.flow_id,
                deployment_id=deployment.id,
                flow_version="0.1",
                flow_runner=schemas.core.FlowRunnerSettings(
                    type="test", config={"foo": "bar"}
                ),
            ),
        )
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=flow_run_1.id,
            state=schemas.states.State(
                type=schemas.states.StateType.SCHEDULED,
                timestamp=pendulum.now("UTC").subtract(seconds=5),
                state_details=dict(
                    scheduled_time=pendulum.now("UTC").subtract(seconds=1)
                ),
            ),
        )

        # flow run 2 is in a SCHEDULED state 1 minute ago with tags ["tb12", "goat"]
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                id=flow_run_2_id,
                flow_id=deployment.flow_id,
                deployment_id=deployment.id,
                flow_version="0.1",
                tags=["tb12", "goat"],
                next_scheduled_start_time=pendulum.now("UTC").subtract(minutes=1),
            ),
        )
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=flow_run_2.id,
            state=schemas.states.State(
                type=schemas.states.StateType.SCHEDULED,
                timestamp=pendulum.now("UTC").subtract(minutes=1),
                state_details=dict(
                    scheduled_time=pendulum.now("UTC").subtract(minutes=1)
                ),
            ),
        )
        await session.commit()

    async def test_read_work_queue_runs(
        self, client, work_queue, flow_run_1_id, flow_run_2_id
    ):
        response = await client.post(f"/work_queues/{work_queue.id}/get_runs")
        assert response.status_code == 200
        assert {res["id"] for res in response.json()} == {
            str(flow_run_1_id),
            str(flow_run_2_id),
        }

    async def test_read_work_queue_runs_respects_limit(
        self, client, work_queue, flow_run_2_id
    ):
        response = await client.post(
            f"/work_queues/{work_queue.id}/get_runs", json=dict(limit=1)
        )
        assert response.status_code == 200
        assert {res["id"] for res in response.json()} == {
            str(flow_run_2_id),
        }

        # limit should still be constrained by Orion settings though
        response = await client.post(
            f"/work_queues/{work_queue.id}/get_runs", json=dict(limit=9001)
        )
        assert response.status_code == 422

    async def test_read_work_queue_runs_respects_scheduled_before(
        self, client, work_queue
    ):
        response = await client.post(
            f"/work_queues/{work_queue.id}/get_runs",
            json=dict(scheduled_before=str(pendulum.now("UTC").subtract(years=2000))),
        )
        assert response.status_code == 200
        assert len(response.json()) == 0

    async def test_read_work_queue_runs_updates_agent_last_activity_time(
        self,
        client,
        work_queue,
        flow_run_1_id,
        flow_run_2_id,
        session,
    ):
        now = pendulum.now("UTC")
        fake_agent_id = uuid4()
        response = await client.post(
            f"/work_queues/{work_queue.id}/get_runs",
            json=dict(agent_id=str(fake_agent_id)),
        )
        assert response.status_code == 200
        assert {res["id"] for res in response.json()} == {
            str(flow_run_1_id),
            str(flow_run_2_id),
        }

        agent = await models.agents.read_agent(session=session, agent_id=fake_agent_id)
        assert agent.id == fake_agent_id
        assert agent.work_queue_id == work_queue.id
        assert agent.last_activity_time >= now

    async def test_read_work_queue_runs_handles_non_existent_work_queue(self, client):
        response = await client.post(f"/work_queues/{uuid4()}/get_runs")
        assert response.status_code == 404


class TestDeleteWorkQueue:
    async def test_delete_work_queue(self, client, work_queue):
        response = await client.delete(f"/work_queues/{work_queue.id}")
        assert response.status_code == 204

        response = await client.get(f"/work_queues/{work_queue.id}")
        assert response.status_code == 404

    async def test_delete_work_queue_returns_404_if_does_not_exist(self, client):
        response = await client.delete(f"/work_queues/{uuid4()}")
        assert response.status_code == 404

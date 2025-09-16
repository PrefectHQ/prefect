import uuid
from datetime import datetime, timedelta, timezone
from typing import List
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect._internal.compatibility.starlette import status
from prefect.server import models, schemas
from prefect.server.events.clients import AssertingEventsClient
from prefect.server.schemas.actions import WorkQueueCreate, WorkQueueUpdate
from prefect.server.schemas.statuses import WorkQueueStatus
from prefect.utilities.pydantic import parse_obj_as


@pytest.fixture(autouse=True)
def patch_events_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "prefect.server.models.work_queues.PrefectServerEventsClient",
        AssertingEventsClient,
    )


@pytest.fixture
async def paused_work_queue(session: AsyncSession):
    work_queue = await models.work_queues.create_work_queue(
        session=session,
        work_queue=schemas.actions.WorkQueueCreate(
            name="wq-xyz", description="All about my work queue"
        ),
    )
    work_queue.status = WorkQueueStatus.PAUSED
    await session.commit()
    return work_queue


@pytest.fixture
async def not_ready_work_queue(session):
    work_queue = await models.work_queues.create_work_queue(
        session=session,
        work_queue=schemas.actions.WorkQueueCreate(
            name="wq-abc", description="All about my work queue"
        ),
    )
    work_queue.status = WorkQueueStatus.NOT_READY
    await session.commit()
    return work_queue


@pytest.fixture
async def ready_work_queue(session: AsyncSession):
    work_queue = await models.work_queues.create_work_queue(
        session=session,
        work_queue=schemas.actions.WorkQueueCreate(
            name="wq-zzz", description="All about my work queue"
        ),
    )
    work_queue.status = WorkQueueStatus.READY
    await session.commit()
    return work_queue


class TestCreateWorkQueue:
    async def test_create_work_queue(
        self,
        session,
        client,
    ):
        now = datetime.now(timezone.utc)
        data = WorkQueueCreate(name="wq-1").model_dump(mode="json")
        response = await client.post("/work_queues/", json=data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["name"] == "wq-1"
        assert response.json()["filter"] is None
        assert (
            datetime.fromisoformat(response.json()["created"].replace("Z", "+00:00"))
            >= now
        )
        assert (
            datetime.fromisoformat(response.json()["updated"].replace("Z", "+00:00"))
            >= now
        )
        assert response.json()["work_pool_name"] == "default-agent-pool"
        work_queue_id = response.json()["id"]

        work_queue = await models.work_queues.read_work_queue(
            session=session, work_queue_id=work_queue_id
        )
        assert str(work_queue.id) == work_queue_id
        assert work_queue.name == "wq-1"

    async def test_create_work_queue_with_priority(
        self,
        client,
        session,
        work_pool,
    ):
        data = dict(name="my-wpq", priority=99)
        response = await client.post(
            "/work_queues/",
            json=data,
        )
        assert response.status_code == 201
        assert response.json()["priority"] == 99
        work_queue_id = response.json()["id"]

        work_queue = await models.work_queues.read_work_queue(
            session=session, work_queue_id=work_queue_id
        )
        assert work_queue.priority == 99

    async def test_create_work_queue_with_no_priority_when_low_priority_set(
        self,
        client,
        work_pool,
    ):
        response = await client.post("/work_queues/", json=dict(name="wpq-1"))
        # priority 2 because the default queue exists
        assert response.json()["priority"] == 2

        response2 = await client.post("/work_queues/", json=dict(name="wpq-2"))
        assert response2.json()["priority"] == 3

    async def test_create_work_queue_with_no_priority_when_high_priority_set(
        self,
        client,
        session,
        work_pool,
    ):
        response = await client.post(
            "/work_queues/", json=dict(name="wpq-1", priority=99)
        )
        assert response.json()["priority"] == 99
        work_queue_id = response.json()["id"]

        response2 = await client.post("/work_queues/", json=dict(name="wpq-2"))
        assert response2.json()["priority"] == 2

        work_queue = await models.work_queues.read_work_queue(
            session=session, work_queue_id=work_queue_id
        )
        assert work_queue.priority == 99

    async def test_create_work_queue_raises_error_on_existing_name(
        self, client, work_queue
    ):
        data = WorkQueueCreate(
            name=work_queue.name,
        ).model_dump(mode="json")
        response = await client.post("/work_queues/", json=data)
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
        assert b"String should match pattern" in response.content

    async def test_create_work_queue_initially_is_not_ready(self, client):
        response = await client.post("/work_queues/", json=dict(name=str(uuid.uuid4())))
        assert response.status_code == status.HTTP_201_CREATED
        assert "status" in response.json()
        assert response.json()["status"] == "NOT_READY"


class TestUpdateWorkQueue:
    async def test_update_work_queue(
        self,
        session,
        client,
    ):
        data = WorkQueueCreate(name="wq-1").model_dump(mode="json", exclude_unset=True)
        response = await client.post("/work_queues/", json=data)
        work_queue_id = response.json()["id"]

        work_queue = await models.work_queues.read_work_queue(
            session=session, work_queue_id=work_queue_id
        )

        assert work_queue.is_paused is False
        assert work_queue.concurrency_limit is None

        new_data = WorkQueueUpdate(is_paused=True, concurrency_limit=3).model_dump(
            mode="json", exclude_unset=True
        )
        response = await client.patch(f"/work_queues/{work_queue_id}", json=new_data)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        response = await client.get(f"/work_queues/{work_queue_id}")

        assert response.json()["is_paused"] is True
        assert response.json()["concurrency_limit"] == 3

        events = [
            event for client in AssertingEventsClient.all for event in client.events
        ]
        assert len(events) == 1

    async def test_update_work_queue_to_paused(
        self,
        client,
        work_queue,
    ):
        assert work_queue.is_paused is False
        assert work_queue.concurrency_limit is None
        assert work_queue.status == "NOT_READY"

        new_data = schemas.actions.WorkQueueUpdate(
            is_paused=True, concurrency_limit=3
        ).model_dump(mode="json", exclude_unset=True)

        response = await client.patch(
            f"/work_queues/{work_queue.id}",
            json=new_data,
        )

        assert response.status_code == 204

        response = await client.get(f"/work_queues/{work_queue.id}")

        assert response.json()["is_paused"] is True
        assert response.json()["concurrency_limit"] == 3
        assert response.json()["status"] == "PAUSED"

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.work-queue.paused",
            resource={
                "prefect.resource.id": f"prefect.work-queue.{work_queue.id}",
                "prefect.resource.name": work_queue.name,
            },
            related=[
                {
                    "prefect.resource.id": f"prefect.work-pool.{work_queue.work_pool.id}",
                    "prefect.resource.name": work_queue.work_pool.name,
                    "prefect.work-pool.type": work_queue.work_pool.type,
                    "prefect.resource.role": "work-pool",
                }
            ],
        )

    async def test_update_work_queue_to_paused_sets_paused_status(
        self,
        client,
        work_queue,
    ):
        assert work_queue.status == "NOT_READY"

        new_data = schemas.actions.WorkQueueUpdate(
            is_paused=True, concurrency_limit=3
        ).model_dump(mode="json", exclude_unset=True)
        work_queue_response = await client.patch(
            f"/work_queues/{work_queue.id}",
            json=new_data,
        )

        assert work_queue_response.status_code == 204

        work_queue_response = await client.get(f"/work_queues/{work_queue.id}")

        assert work_queue_response.json()["is_paused"] is True
        assert work_queue_response.json()["concurrency_limit"] == 3
        assert work_queue_response.status_code == 200
        assert work_queue_response.json()["status"] == "PAUSED"

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.work-queue.paused",
            resource={
                "prefect.resource.id": f"prefect.work-queue.{work_queue.id}",
                "prefect.resource.name": work_queue.name,
            },
            related=[
                {
                    "prefect.resource.id": f"prefect.work-pool.{work_queue.work_pool.id}",
                    "prefect.resource.name": work_queue.work_pool.name,
                    "prefect.work-pool.type": work_queue.work_pool.type,
                    "prefect.resource.role": "work-pool",
                }
            ],
        )

    async def test_update_work_queue_to_paused_when_already_paused_does_not_emit_event(
        self,
        client,
        paused_work_queue,
    ):
        assert paused_work_queue.status == "PAUSED"

        new_data = schemas.actions.WorkQueueUpdate(
            is_paused=True, concurrency_limit=3
        ).model_dump(mode="json", exclude_unset=True)
        work_queue_response = await client.patch(
            f"/work_queues/{paused_work_queue.id}",
            json=new_data,
        )

        assert work_queue_response.status_code == 204

        work_queue_response = await client.get(f"/work_queues/{paused_work_queue.id}")

        assert work_queue_response.json()["is_paused"] is True
        assert work_queue_response.json()["concurrency_limit"] == 3
        assert work_queue_response.status_code == 200
        assert work_queue_response.json()["status"] == "PAUSED"

        # ensure no events emitted for already paused work queue
        AssertingEventsClient.assert_emitted_event_count(0)

    async def test_update_work_queue_to_unpaused_when_already_unpaused_does_not_emit_event(
        self,
        client,
        ready_work_queue,
    ):
        assert ready_work_queue.status == "READY"

        new_data = schemas.actions.WorkQueueUpdate(
            is_paused=False, concurrency_limit=3
        ).model_dump(mode="json", exclude_unset=True)
        work_queue_response = await client.patch(
            f"/work_queues/{ready_work_queue.id}",
            json=new_data,
        )

        assert work_queue_response.status_code == 204

        work_queue_response = await client.get(f"/work_queues/{ready_work_queue.id}")

        assert work_queue_response.json()["is_paused"] is False
        assert work_queue_response.json()["concurrency_limit"] == 3
        assert work_queue_response.status_code == 200
        assert work_queue_response.json()["status"] == "READY"

        # ensure no events emitted for already unpaused work queue
        AssertingEventsClient.assert_emitted_event_count(0)

    async def test_update_work_queue_to_unpaused_with_no_last_polled_sets_not_ready_status(
        self,
        client,
        work_queue,
    ):
        # first, pause the work pool queue with no last_polled
        pause_data = schemas.actions.WorkQueueUpdate(is_paused=True).model_dump(
            mode="json", exclude_unset=True
        )

        response = await client.patch(
            f"/work_queues/{work_queue.id}",
            json=pause_data,
        )
        assert response.status_code == 204
        response = await client.get(
            f"/work_queues/{work_queue.id}",
        )
        paused_work_queue_response = response.json()
        assert paused_work_queue_response["status"] == "PAUSED"
        assert paused_work_queue_response["is_paused"] is True
        assert paused_work_queue_response["last_polled"] is None

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.work-queue.paused",
            resource={
                "prefect.resource.id": f"prefect.work-queue.{work_queue.id}",
                "prefect.resource.name": work_queue.name,
            },
            related=[
                {
                    "prefect.resource.id": f"prefect.work-pool.{work_queue.work_pool.id}",
                    "prefect.resource.name": work_queue.work_pool.name,
                    "prefect.work-pool.type": work_queue.work_pool.type,
                    "prefect.resource.role": "work-pool",
                }
            ],
        )

        # now unpause the work pool queue with no last_polled
        unpause_data = schemas.actions.WorkQueueUpdate(
            is_paused=False, concurrency_limit=3
        ).model_dump(mode="json", exclude_unset=True)
        response = await client.patch(
            f"/work_queues/{work_queue.id}",
            json=unpause_data,
        )
        assert response.status_code == 204
        unpaused_data_response = await client.get(
            f"/work_queues/{work_queue.id}",
        )
        assert unpaused_data_response.json()["is_paused"] is False
        assert unpaused_data_response.json()["concurrency_limit"] == 3
        assert unpaused_data_response.json()["status"] == "NOT_READY"
        assert unpaused_data_response.json()["last_polled"] is None

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.work-queue.not-ready",
            resource={
                "prefect.resource.id": f"prefect.work-queue.{work_queue.id}",
                "prefect.resource.name": work_queue.name,
            },
            related=[
                {
                    "prefect.resource.id": f"prefect.work-pool.{work_queue.work_pool.id}",
                    "prefect.resource.name": work_queue.work_pool.name,
                    "prefect.work-pool.type": work_queue.work_pool.type,
                    "prefect.resource.role": "work-pool",
                }
            ],
        )

    async def test_update_work_queue_to_unpaused_with_expired_last_polled_sets_not_ready_status(
        self,
        client,
        work_queue,
    ):
        # first, pause the work pool queue with a expired last_polled
        pause_data = schemas.actions.WorkQueueUpdate(
            last_polled=datetime.now(timezone.utc) - timedelta(minutes=2),
            is_paused=True,
        ).model_dump(mode="json", exclude_unset=True)

        response = await client.patch(
            f"/work_queues/{work_queue.id}",
            json=pause_data,
        )
        assert response.status_code == 204
        response = await client.get(
            f"/work_queues/{work_queue.id}",
        )
        paused_work_queue_response = response.json()
        assert paused_work_queue_response["status"] == "PAUSED"
        assert paused_work_queue_response["is_paused"] is True
        assert paused_work_queue_response["last_polled"] is not None

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.work-queue.paused",
            resource={
                "prefect.resource.id": f"prefect.work-queue.{work_queue.id}",
                "prefect.resource.name": work_queue.name,
            },
            related=[
                {
                    "prefect.resource.id": f"prefect.work-pool.{work_queue.work_pool.id}",
                    "prefect.resource.name": work_queue.work_pool.name,
                    "prefect.work-pool.type": work_queue.work_pool.type,
                    "prefect.resource.role": "work-pool",
                }
            ],
        )

        # now unpause the work pool queue with expired last_polled
        unpause_data = schemas.actions.WorkQueueUpdate(
            is_paused=False, concurrency_limit=3
        ).model_dump(mode="json", exclude_unset=True)
        response = await client.patch(
            f"/work_queues/{work_queue.id}",
            json=unpause_data,
        )
        assert response.status_code == 204
        unpaused_data_response = await client.get(
            f"/work_queues/{work_queue.id}",
        )
        assert unpaused_data_response.json()["is_paused"] is False
        assert unpaused_data_response.json()["concurrency_limit"] == 3
        assert unpaused_data_response.json()["status"] == "NOT_READY"

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.work-queue.not-ready",
            resource={
                "prefect.resource.id": f"prefect.work-queue.{work_queue.id}",
                "prefect.resource.name": work_queue.name,
            },
            related=[
                {
                    "prefect.resource.id": f"prefect.work-pool.{work_queue.work_pool.id}",
                    "prefect.resource.name": work_queue.work_pool.name,
                    "prefect.work-pool.type": work_queue.work_pool.type,
                    "prefect.resource.role": "work-pool",
                }
            ],
        )

    async def test_update_work_queue_to_unpaused_with_recent_last_polled_sets_ready_status(
        self,
        client,
        work_queue,
    ):
        # first, pause the work pool queue with a recent last_polled
        pause_data = schemas.actions.WorkQueueUpdate(
            last_polled=datetime.now(timezone.utc), is_paused=True
        ).model_dump(mode="json", exclude_unset=True)

        response = await client.patch(
            f"/work_queues/{work_queue.id}",
            json=pause_data,
        )
        assert response.status_code == 204
        response = await client.get(
            f"/work_queues/{work_queue.id}",
        )
        paused_work_queue_response = response.json()
        assert paused_work_queue_response["status"] == "PAUSED"
        assert paused_work_queue_response["last_polled"] is not None
        assert paused_work_queue_response["is_paused"] is True

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.work-queue.paused",
            resource={
                "prefect.resource.id": f"prefect.work-queue.{work_queue.id}",
                "prefect.resource.name": work_queue.name,
            },
            related=[
                {
                    "prefect.resource.id": f"prefect.work-pool.{work_queue.work_pool.id}",
                    "prefect.resource.name": work_queue.work_pool.name,
                    "prefect.work-pool.type": work_queue.work_pool.type,
                    "prefect.resource.role": "work-pool",
                }
            ],
        )

        # now unpause a recently polled work pool queue
        unpause_data = schemas.actions.WorkQueueUpdate(
            is_paused=False, concurrency_limit=3
        ).model_dump(mode="json", exclude_unset=True)
        response = await client.patch(
            f"/work_queues/{work_queue.id}",
            json=unpause_data,
        )
        assert response.status_code == 204
        unpaused_data_response = await client.get(
            f"/work_queues/{work_queue.id}",
        )
        assert unpaused_data_response.json()["is_paused"] is False
        assert unpaused_data_response.json()["concurrency_limit"] == 3
        assert unpaused_data_response.json()["status"] == "READY"

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.work-queue.ready",
            resource={
                "prefect.resource.id": f"prefect.work-queue.{work_queue.id}",
                "prefect.resource.name": work_queue.name,
            },
            related=[
                {
                    "prefect.resource.id": f"prefect.work-pool.{work_queue.work_pool.id}",
                    "prefect.resource.name": work_queue.work_pool.name,
                    "prefect.work-pool.type": work_queue.work_pool.type,
                    "prefect.resource.role": "work-pool",
                }
            ],
        )


class TestReadWorkQueue:
    async def test_read_work_queue(self, client, work_queue):
        response = await client.get(f"/work_queues/{work_queue.id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == str(work_queue.id)
        assert response.json()["name"] == work_queue.name
        assert response.json()["work_pool_name"] == "default-agent-pool"

    async def test_read_work_queue_returns_404_if_does_not_exist(self, client):
        response = await client.get(f"/work_queues/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReadWorkQueueByName:
    async def test_read_work_queue_by_name(self, client, work_queue):
        response = await client.get(f"/work_queues/name/{work_queue.name}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == str(work_queue.id)
        assert response.json()["name"] == work_queue.name
        assert response.json()["work_pool_name"] == "default-agent-pool"

    async def test_read_work_queue_returns_404_if_does_not_exist(self, client):
        response = await client.get("/work_queues/name/some-made-up-work-queue")
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
            work_queue=schemas.actions.WorkQueueCreate(
                name="wq-1 X",
            ),
        )

        await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.actions.WorkQueueCreate(
                name="wq-1 Y",
            ),
        )

        await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.actions.WorkQueueCreate(
                name="wq-2 Y",
            ),
        )
        await session.commit()

    async def test_read_work_queues(self, work_queues, client):
        response = await client.post("/work_queues/filter")
        assert response.status_code == status.HTTP_200_OK
        # includes default work queue
        assert len(response.json()) == 4
        for wq in response.json():
            assert wq["work_pool_name"] == "default-agent-pool"

    async def test_read_work_queues_applies_limit(self, work_queues, client):
        response = await client.post("/work_queues/filter", json=dict(limit=1))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1

    async def test_read_work_queues_offset(self, work_queues, client, session):
        response = await client.post("/work_queues/filter", json=dict(offset=1))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 3
        # ordered by name by default
        assert response.json()[0]["name"] == "wq-1 X"
        assert response.json()[1]["name"] == "wq-1 Y"
        assert response.json()[2]["name"] == "wq-2 Y"

    async def test_read_work_queues_by_name(self, work_queues, client, session):
        response = await client.post(
            "/work_queues/filter",
            json=dict(work_queues={"name": {"startswith_": ["wq-1"]}}),
        )
        assert response.status_code == status.HTTP_200_OK

        assert {wq["name"] for wq in response.json()} == {"wq-1 X", "wq-1 Y"}

    async def test_read_work_queues_returns_empty_list(self, client):
        response = await client.post("/work_queues/filter")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    async def test_work_queue_old_last_polled_is_in_not_ready_status(
        self,
        client,
        work_queue,
        session,
    ):
        # Update the queue with an old last_polled time
        new_data = WorkQueueUpdate(
            last_polled=datetime.now(timezone.utc) - timedelta(days=1)
        ).model_dump(mode="json", exclude_unset=True)
        response = await client.patch(f"/work_queues/{work_queue.id}", json=new_data)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify the work queue status is changed
        wq_response = await client.get(f"/work_queues/{work_queue.id}")
        assert wq_response.status_code == status.HTTP_200_OK
        assert wq_response.json()["status"] == "NOT_READY"
        assert wq_response.json()["is_paused"] is False


class TestGetRunsInWorkQueue:
    @pytest.fixture
    async def work_queue_2(self, session):
        work_queue = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.actions.WorkQueueCreate(name="wq-2"),
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
                            timestamp=datetime.now(timezone.utc) + timedelta(minutes=i),
                            state_details=dict(
                                scheduled_time=datetime.now(timezone.utc)
                                + timedelta(minutes=i)
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
                            timestamp=datetime.now(timezone.utc)
                            - timedelta(seconds=10),
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

        runs_wq1 = parse_obj_as(
            List[schemas.responses.FlowRunResponse], response1.json()
        )
        runs_wq2 = parse_obj_as(
            List[schemas.responses.FlowRunResponse], response2.json()
        )

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
        runs_wq1 = parse_obj_as(
            List[schemas.responses.FlowRunResponse], response1.json()
        )
        assert len(runs_wq1) == limit

    async def test_get_runs_in_queue_scheduled_before(
        self, client, work_queue, scheduled_flow_runs, running_flow_runs
    ):
        response1 = await client.post(
            f"/work_queues/{work_queue.id}/get_runs",
            json=dict(scheduled_before=datetime.now(timezone.utc).isoformat()),
        )
        runs_wq1 = parse_obj_as(
            List[schemas.responses.FlowRunResponse], response1.json()
        )
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

    async def test_read_work_queue_runs_updates_work_queue_last_polled_time(
        self,
        client,
        work_queue,
        session,
    ):
        now = datetime.now(timezone.utc)
        response = await client.post(
            f"/work_queues/{work_queue.id}/get_runs",
            json=dict(),
        )
        assert response.status_code == status.HTTP_200_OK

        session.expunge_all()
        updated_work_queue = await models.work_queues.read_work_queue(
            session=session, work_queue_id=work_queue.id
        )
        assert updated_work_queue.last_polled > now

        # The Prefect UI often calls this route to see which runs are enqueued.
        # We do not want to record this as an actual poll event.
        ui_response = await client.post(
            f"/work_queues/{work_queue.id}/get_runs",
            json=dict(),
            headers={"X-PREFECT-UI": "true"},
        )
        assert ui_response.status_code == status.HTTP_200_OK

        session.expunge_all()
        ui_updated_work_queue = await models.work_queues.read_work_queue(
            session=session, work_queue_id=work_queue.id
        )
        assert ui_updated_work_queue.last_polled == updated_work_queue.last_polled

    async def test_read_work_queue_runs_associated_deployments_return_status_of_ready(
        self,
        client,
        deployment,
    ):
        work_queue_id = deployment.work_queue_id
        # ensure deployment currently has a not ready status
        deployment_response = await client.get(f"/deployments/{deployment.id}")
        assert deployment_response.status_code == status.HTTP_200_OK
        assert deployment_response.json()["status"] == "NOT_READY"

        # trigger a poll of the work queue, which should update the deployment status
        response = await client.post(
            f"/work_queues/{work_queue_id}/get_runs",
            json=dict(),
        )
        assert response.status_code == status.HTTP_200_OK

        # check that the deployment status is now ready
        updated_deployment_response = await client.get(f"/deployments/{deployment.id}")
        assert updated_deployment_response.status_code == status.HTTP_200_OK
        assert updated_deployment_response.json()["status"] == "READY"

    async def test_read_work_queue_runs_updates_work_queue_status(
        self,
        client,
        work_queue,
        session,
    ):
        # Verify the work queue is initially not ready
        wq_response = await client.get(f"/work_queues/{work_queue.id}")
        assert wq_response.status_code == status.HTTP_200_OK
        assert wq_response.json()["status"] == "NOT_READY"

        # Trigger a polling operation
        response = await client.post(
            f"/work_queues/{work_queue.id}/get_runs",
        )
        assert response.status_code == status.HTTP_200_OK

        # Verify the work queue is now ready
        wq_response = await client.get(f"/work_queues/{work_queue.id}")
        assert wq_response.status_code == status.HTTP_200_OK
        assert wq_response.json()["status"] == "READY"

    async def test_read_work_queue_runs_does_not_update_a_paused_work_queues_status(
        self,
        client,
        work_queue,
        session,
    ):
        # Move the queue into a PAUSED state
        new_data = WorkQueueUpdate(is_paused=True).model_dump(
            mode="json", exclude_unset=True
        )
        response = await client.patch(f"/work_queues/{work_queue.id}", json=new_data)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify the work queue is PAUSED
        wq_response = await client.get(f"/work_queues/{work_queue.id}")
        assert wq_response.status_code == status.HTTP_200_OK
        assert wq_response.json()["status"] == "PAUSED"
        assert wq_response.json()["is_paused"] is True

        # Trigger a polling operation
        response = await client.post(
            f"/work_queues/{work_queue.id}/get_runs",
        )
        assert response.status_code == status.HTTP_200_OK

        # Verify the work queue status is still PAUSED
        wq_response = await client.get(f"/work_queues/{work_queue.id}")
        assert wq_response.status_code == status.HTTP_200_OK
        assert wq_response.json()["status"] == "PAUSED"


class TestDeleteWorkQueue:
    async def test_delete_work_queue(self, client, work_queue):
        response = await client.delete(f"/work_queues/{work_queue.id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        response = await client.get(f"/work_queues/{work_queue.id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_work_queue_returns_404_if_does_not_exist(self, client):
        response = await client.delete(f"/work_queues/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReadWorkQueueStatus:
    @pytest.fixture
    async def recently_polled_work_queue(self, session, work_pool):
        work_queue = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.core.WorkQueue(
                name="wq-1",
                description="All about my work queue",
                last_polled=datetime.now(timezone.utc),
                work_pool_id=work_pool.id,
                priority=1,
            ),
        )
        await session.commit()
        return work_queue

    @pytest.fixture
    async def recently_pool_work_queue_in_different_work_pool(self, session):
        work_pool = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(
                name="another-work-pool",
                description="All about my work pool",
                type="test",
            ),
        )
        work_queue = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.core.WorkQueue(
                name="wq-1",
                description="All about my work queue",
                last_polled=datetime.now(timezone.utc),
                work_pool_id=work_pool.id,
                priority=1,
            ),
        )
        await session.commit()
        return work_queue

    @pytest.fixture
    async def not_recently_polled_work_queue(self, session, work_pool):
        work_queue = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.core.WorkQueue(
                name="wq-1",
                description="All about my work queue",
                last_polled=datetime.now(timezone.utc) - timedelta(days=1),
                work_pool_id=work_pool.id,
                priority=2,
            ),
        )
        await session.commit()
        return work_queue

    @pytest.fixture
    async def work_queue_with_late_runs(self, session, flow, work_pool):
        work_queue = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.core.WorkQueue(
                name="wq-1",
                description="All about my work queue",
                last_polled=datetime.now(timezone.utc),
                work_pool_id=work_pool.id,
                priority=1,
            ),
        )
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.Late(
                    scheduled_time=datetime.now(timezone.utc) - timedelta(minutes=60)
                ),
                work_queue_id=work_queue.id,
            ),
        )
        await session.commit()
        return work_queue

    async def test_read_work_queue_status(self, client, recently_polled_work_queue):
        response = await client.get(
            f"/work_queues/{recently_polled_work_queue.id}/status"
        )

        assert response.status_code == status.HTTP_200_OK

        parsed_response = parse_obj_as(
            schemas.core.WorkQueueStatusDetail, response.json()
        )
        assert parsed_response.healthy is True
        assert parsed_response.late_runs_count == 0
        assert parsed_response.last_polled == recently_polled_work_queue.last_polled

    async def test_read_work_queue_status_unhealthy_due_to_lack_of_polls(
        self, client, not_recently_polled_work_queue
    ):
        response = await client.get(
            f"/work_queues/{not_recently_polled_work_queue.id}/status"
        )

        assert response.status_code == status.HTTP_200_OK

        parsed_response = parse_obj_as(
            schemas.core.WorkQueueStatusDetail, response.json()
        )
        assert parsed_response.healthy is False
        assert parsed_response.late_runs_count == 0
        assert parsed_response.last_polled == not_recently_polled_work_queue.last_polled

    async def test_read_work_queue_status_unhealthy_due_to_late_runs(
        self, client, work_queue_with_late_runs
    ):
        response = await client.get(
            f"/work_queues/{work_queue_with_late_runs.id}/status"
        )

        assert response.status_code == status.HTTP_200_OK

        parsed_response = parse_obj_as(
            schemas.core.WorkQueueStatusDetail, response.json()
        )
        assert parsed_response.healthy is False
        assert parsed_response.late_runs_count == 1
        assert parsed_response.last_polled == work_queue_with_late_runs.last_polled

    async def test_read_work_queue_returns_correct_status_when_work_queues_share_name(
        self,
        client,
        work_queue_with_late_runs,
        recently_pool_work_queue_in_different_work_pool,
    ):
        healthy_response = await client.get(
            f"/work_queues/{recently_pool_work_queue_in_different_work_pool.id}/status"
        )

        assert healthy_response.status_code == status.HTTP_200_OK

        parsed_healthy_response = parse_obj_as(
            schemas.core.WorkQueueStatusDetail, healthy_response.json()
        )
        assert parsed_healthy_response.healthy is True

        unhealthy_response = await client.get(
            f"/work_queues/{work_queue_with_late_runs.id}/status"
        )

        assert unhealthy_response.status_code == status.HTTP_200_OK

        parsed_unhealthy_response = parse_obj_as(
            schemas.core.WorkQueueStatusDetail, unhealthy_response.json()
        )
        assert parsed_unhealthy_response.healthy is False

    async def test_read_work_queue_status_returns_404_if_does_not_exist(self, client):
        response = await client.get(f"/work_queues/{uuid4()}/status")
        assert response.status_code == status.HTTP_404_NOT_FOUND

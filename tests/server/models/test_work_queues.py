import datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from prefect.server import models, schemas
from prefect.server.exceptions import ObjectNotFoundError
from prefect.server.models.workers import DEFAULT_AGENT_WORK_POOL_NAME
from prefect.types._datetime import now


@pytest.fixture
async def work_queue(session):
    work_queue = await models.work_queues.create_work_queue(
        session=session,
        work_queue=schemas.actions.WorkQueueCreate(
            name="wq-1",
            description="All about my work queue",
        ),
    )
    await session.commit()
    return work_queue


class TestCreateWorkQueue:
    async def test_create_work_queue_succeeds(self, session):
        work_queue = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.actions.WorkQueueCreate(name="wq-1"),
        )
        assert work_queue.name == "wq-1"
        # deprecated field
        assert work_queue.filter is None

    async def test_create_work_queue_throws_exception_on_name_conflict(
        self,
        session,
        work_queue,
    ):
        with pytest.raises(IntegrityError):
            await models.work_queues.create_work_queue(
                session=session,
                work_queue=schemas.actions.WorkQueueCreate(
                    name=work_queue.name,
                ),
            )

    async def test_create_work_queue_when_no_default_pool(self, session):
        pool = await models.workers.read_work_pool_by_name(
            session=session, work_pool_name=DEFAULT_AGENT_WORK_POOL_NAME
        )
        if pool is not None:
            await models.workers.delete_work_pool(session=session, work_pool_id=pool.id)
            await session.commit()

        work_queue = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.actions.WorkQueueCreate(name="default"),
        )

        pool_after = await models.workers.read_work_pool_by_name(
            session=session, work_pool_name=DEFAULT_AGENT_WORK_POOL_NAME
        )
        assert pool_after is not None
        assert pool_after.default_queue_id == work_queue.id


class TestReadWorkQueue:
    async def test_read_work_queue_by_id(self, session, work_queue):
        read_work_queue = await models.work_queues.read_work_queue(
            session=session, work_queue_id=work_queue.id
        )
        assert read_work_queue.name == work_queue.name

    async def test_read_work_queue_by_id_returns_none_if_does_not_exist(self, session):
        assert not await models.work_queues.read_work_queue(
            session=session, work_queue_id=uuid4()
        )


class TestReadWorkQueueByName:
    async def test_read_work_queue_by_name(self, session, work_queue):
        read_work_queue = await models.work_queues.read_work_queue_by_name(
            session=session, name=work_queue.name
        )
        assert read_work_queue.id == work_queue.id

    async def test_read_work_queue_by_name_returns_none_if_does_not_exist(
        self, session
    ):
        assert not await models.work_queues.read_work_queue_by_name(
            session=session, name="a name that doesn't exist"
        )


class TestReadWorkQueues:
    @pytest.fixture
    async def work_queues(self, session):
        work_queue_1 = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.actions.WorkQueueCreate(
                name="wq-1 1",
            ),
        )
        work_queue_2 = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.actions.WorkQueueCreate(
                name="wq-1 2",
            ),
        )
        work_queue_3 = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.actions.WorkQueueCreate(
                name="wq-2 1",
            ),
        )
        work_queue_4 = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.actions.WorkQueueCreate(
                name="wq-3 1",
            ),
        )
        await session.commit()
        return [work_queue_1, work_queue_2, work_queue_3, work_queue_4]

    async def test_read_work_queue(self, work_queues, session):
        read_work_queue = await models.work_queues.read_work_queues(session=session)
        assert len(read_work_queue) == len(work_queues) + 1  # +1 for default queue

    async def test_read_work_queue_applies_limit(self, work_queues, session):
        read_work_queue = await models.work_queues.read_work_queues(
            session=session, limit=1, offset=1
        )
        assert {queue.id for queue in read_work_queue} == {work_queues[0].id}

    async def test_read_work_queue_applies_offset(self, work_queues, session):
        read_work_queue = await models.work_queues.read_work_queues(
            session=session, offset=1
        )
        assert {queue.id for queue in read_work_queue} == {
            work_queues[0].id,
            work_queues[1].id,
            work_queues[2].id,
            work_queues[3].id,
        }

    async def test_read_work_queues_name_any(self, work_queues, session):
        read_work_queue = await models.work_queues.read_work_queues(
            session=session,
            work_queue_filter=schemas.filters.WorkQueueFilter(
                name=schemas.filters.WorkQueueFilterName(any_=["wq-1 1", "wq-2 1"])
            ),
        )
        assert {queue.name for queue in read_work_queue} == {"wq-1 1", "wq-2 1"}

    async def test_read_work_queues_name_startswith(self, work_queues, session):
        read_work_queue = await models.work_queues.read_work_queues(
            session=session,
            work_queue_filter=schemas.filters.WorkQueueFilter(
                name=schemas.filters.WorkQueueFilterName(startswith_=["wq-1", "wq-2"])
            ),
        )
        assert {queue.name for queue in read_work_queue} == {
            "wq-1 1",
            "wq-1 2",
            "wq-2 1",
        }

    async def test_read_work_queue_returns_empty_list(self, session):
        read_work_queue = await models.work_queues.read_work_queues(session=session)
        assert len(read_work_queue) == 0


class TestUpdateWorkQueue:
    async def test_update_work_queue(self, session, work_queue):
        result = await models.work_queues.update_work_queue(
            session=session,
            work_queue_id=work_queue.id,
            work_queue=schemas.actions.WorkQueueUpdate(is_paused=True),
        )
        assert result

        updated_queue = await models.work_queues.read_work_queue(
            session=session, work_queue_id=work_queue.id
        )
        assert updated_queue.id == work_queue.id
        # relevant attributes should be updated
        assert updated_queue.is_paused
        # unset attributes should be ignored
        assert updated_queue.description == work_queue.description

    async def test_update_work_queue_without_name(self, session, work_queue):
        assert work_queue.is_paused is False
        assert work_queue.concurrency_limit is None

        result = await models.work_queues.update_work_queue(
            session=session,
            work_queue_id=work_queue.id,
            work_queue=schemas.actions.WorkQueueUpdate(
                concurrency_limit=3,
                is_paused=True,
            ),
        )
        assert result

        updated_queue = await models.work_queues.read_work_queue(
            session=session, work_queue_id=work_queue.id
        )
        # relevant attributes should be updated
        assert updated_queue.is_paused
        assert updated_queue.concurrency_limit == 3
        # unset attributes should be ignored
        assert updated_queue.description == work_queue.description
        assert updated_queue.id == work_queue.id
        assert updated_queue.name == work_queue.name

    async def test_update_work_queue_returns_false_if_does_not_exist(self, session):
        result = await models.work_queues.update_work_queue(
            session=session,
            work_queue_id=str(uuid4()),
            work_queue=schemas.actions.WorkQueueUpdate(),
        )
        assert result is False


class TestDeleteWorkQueue:
    async def test_delete_work_queue(self, session, work_queue):
        assert await models.work_queues.delete_work_queue(
            session=session, work_queue_id=work_queue.id
        )

        # make sure the work_queue is deleted
        result = await models.work_queues.read_work_queue(
            session=session, work_queue_id=work_queue.id
        )
        assert result is None

    async def test_delete_work_queue_returns_false_if_does_not_exist(self, session):
        result = await models.work_queues.delete_work_queue(
            session=session, work_queue_id=str(uuid4())
        )
        assert result is False


class TestGetRunsInWorkQueue:
    running_flow_states = [
        schemas.states.StateType.PENDING,
        schemas.states.StateType.CANCELLING,
        schemas.states.StateType.RUNNING,
    ]

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
                current_time = now("UTC") + datetime.timedelta(minutes=i)
                await models.flow_runs.create_flow_run(
                    session=session,
                    flow_run=schemas.core.FlowRun(
                        flow_id=deployment.flow_id,
                        deployment_id=deployment.id,
                        work_queue_name=wq.name,
                        state=schemas.states.State(
                            type="SCHEDULED",
                            timestamp=current_time,
                            state_details=dict(scheduled_time=current_time),
                        ),
                    ),
                )
        await session.commit()

    @pytest.fixture
    async def running_flow_runs(self, session, deployment, work_queue, work_queue_2):
        for state_type in self.running_flow_states:
            for wq in [work_queue, work_queue_2]:
                await models.flow_runs.create_flow_run(
                    session=session,
                    flow_run=schemas.core.FlowRun(
                        flow_id=deployment.flow_id,
                        deployment_id=deployment.id,
                        work_queue_name=wq.name,
                        state=schemas.states.State(
                            type=state_type,
                            timestamp=now("UTC") - datetime.timedelta(seconds=10),
                        ),
                    ),
                )
        await session.commit()

    async def test_get_runs_in_queue(
        self, session, work_queue, work_queue_2, scheduled_flow_runs, running_flow_runs
    ):
        queue1, runs_wq1 = await models.work_queues.get_runs_in_work_queue(
            session=session, work_queue_id=work_queue.id
        )
        queue2, runs_wq2 = await models.work_queues.get_runs_in_work_queue(
            session=session, work_queue_id=work_queue_2.id
        )

        assert queue1.id == work_queue.id
        assert queue2.id == work_queue_2.id

        assert len(runs_wq1) == len(runs_wq2) == 3
        assert all(r.work_queue_name == work_queue.name for r in runs_wq1)
        assert all(r.work_queue_name == work_queue_2.name for r in runs_wq2)
        assert set([r.id for r in runs_wq1]) != set([r.id for r in runs_wq2])

    @pytest.mark.parametrize("limit", [2, 0])
    async def test_get_runs_in_queue_limit(
        self,
        session,
        work_queue,
        scheduled_flow_runs,
        running_flow_runs,
        limit,
    ):
        _, runs_wq1 = await models.work_queues.get_runs_in_work_queue(
            session=session, work_queue_id=work_queue.id, limit=limit
        )
        assert len(runs_wq1) == limit

    async def test_get_runs_in_queue_scheduled_before(
        self, session, work_queue, scheduled_flow_runs, running_flow_runs
    ):
        _, runs_wq1 = await models.work_queues.get_runs_in_work_queue(
            session=session,
            work_queue_id=work_queue.id,
            scheduled_before=now("UTC"),
        )
        assert len(runs_wq1) == 1

    async def test_get_runs_in_queue_nonexistant(
        self, session, work_queue, scheduled_flow_runs, running_flow_runs
    ):
        with pytest.raises(ObjectNotFoundError):
            await models.work_queues.get_runs_in_work_queue(
                session=session, work_queue_id=uuid4()
            )

    async def test_get_runs_in_queue_paused(
        self, session, work_queue, scheduled_flow_runs, running_flow_runs
    ):
        await models.work_queues.update_work_queue(
            session=session,
            work_queue_id=work_queue.id,
            work_queue=schemas.actions.WorkQueueUpdate(is_paused=True),
        )

        _, runs_wq1 = await models.work_queues.get_runs_in_work_queue(
            session=session, work_queue_id=work_queue.id
        )
        assert runs_wq1 == []

    @pytest.mark.parametrize("concurrency_limit", [10, 5, 1])
    async def test_get_runs_in_queue_concurrency_limit(
        self,
        session,
        work_queue,
        scheduled_flow_runs,
        running_flow_runs,
        concurrency_limit,
    ):
        await models.work_queues.update_work_queue(
            session=session,
            work_queue_id=work_queue.id,
            work_queue=schemas.actions.WorkQueueUpdate(
                concurrency_limit=concurrency_limit
            ),
        )

        _, runs_wq1 = await models.work_queues.get_runs_in_work_queue(
            session=session, work_queue_id=work_queue.id
        )

        assert len(runs_wq1) == max(
            0, min(3, concurrency_limit - len(self.running_flow_states))
        )

    @pytest.mark.parametrize("limit", [10, 1])
    async def test_get_runs_in_queue_concurrency_limit_and_limit(
        self,
        session,
        work_queue,
        scheduled_flow_runs,
        running_flow_runs,
        limit,
    ):
        concurrency_limit = 5

        await models.work_queues.update_work_queue(
            session=session,
            work_queue_id=work_queue.id,
            work_queue=schemas.actions.WorkQueueUpdate(
                concurrency_limit=concurrency_limit
            ),
        )

        _, runs_wq1 = await models.work_queues.get_runs_in_work_queue(
            session=session, work_queue_id=work_queue.id, limit=limit
        )

        assert len(runs_wq1) == min(
            limit, concurrency_limit - len(self.running_flow_states)
        )

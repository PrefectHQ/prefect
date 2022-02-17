from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from prefect.orion import models, schemas


@pytest.fixture
async def work_queue(session):
    work_queue = await models.work_queues.create_work_queue(
        session=session,
        work_queue=schemas.core.WorkQueue(
            name="My WorkQueue",
            description="All about my work queue",
        ),
    )
    return work_queue


class TestCreateWorkQueue:
    async def test_create_work_queue_succeeds(self, session):
        work_queue = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.core.WorkQueue(name="My WorkQueue"),
        )
        assert work_queue.name == "My WorkQueue"

    async def test_create_work_queue_throws_exception_on_name_conflict(
        self,
        session,
        work_queue,
    ):
        with pytest.raises(IntegrityError):
            await models.work_queues.create_work_queue(
                session=session,
                work_queue=schemas.core.WorkQueue(
                    name=work_queue.name,
                ),
            )


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


class TestReadWorkQueues:
    @pytest.fixture
    async def work_queues(self, session):

        work_queue_1 = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.core.WorkQueue(
                name="My WorkQueue 1",
            ),
        )
        work_queue_2 = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.core.WorkQueue(
                name="My WorkQueue 2",
            ),
        )
        await session.commit()
        return [work_queue_1, work_queue_2]

    async def test_read_work_queue(self, work_queues, session):
        read_work_queue = await models.work_queues.read_work_queues(session=session)
        assert len(read_work_queue) == len(work_queues)

    async def test_read_work_queue_applies_limit(self, work_queues, session):
        read_work_queue = await models.work_queues.read_work_queues(
            session=session, limit=1
        )
        assert {queue.id for queue in read_work_queue} == {work_queues[0].id}

    async def test_read_work_queue_applies_offset(self, work_queues, session):
        read_work_queue = await models.work_queues.read_work_queues(
            session=session, offset=1
        )
        assert {queue.id for queue in read_work_queue} == {work_queues[1].id}

    async def test_read_work_queue_returns_empty_list(self, session):
        read_work_queue = await models.work_queues.read_work_queues(session=session)
        assert len(read_work_queue) == 0


class TestUpdateWorkQueue:
    async def test_update_work_queue(self, session, work_queue):
        result = await models.work_queues.update_work_queue(
            session=session,
            work_queue_id=work_queue.id,
            work_queue=schemas.actions.WorkQueueUpdate(
                name="My Paused Queue",
                is_paused=True,
            ),
        )
        assert result

        updated_queue = await models.work_queues.read_work_queue(
            session=session, work_queue_id=work_queue.id
        )
        assert updated_queue.id == work_queue.id
        # relevant attributes should be updated
        assert updated_queue.name == "My Paused Queue"
        assert updated_queue.is_paused
        # unset attributes should be ignored
        assert updated_queue.description == work_queue.description

    async def test_update_work_queue_raises_on_bad_input_data(self, session):
        with pytest.raises(ValueError):
            await models.work_queues.update_work_queue(
                session=session,
                work_queue_id=str(uuid4()),
                work_queue=schemas.core.WorkQueue(name="naughty update data"),
            )

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

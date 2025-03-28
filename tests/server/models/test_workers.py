import datetime
from uuid import uuid4

import pydantic
import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models, schemas
from prefect.types._datetime import now


class TestCreateWorkPool:
    async def test_create_work_pool(self, session: AsyncSession):
        result = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(name="My Test Pool"),
        )

        assert result.name == "My Test Pool"
        assert result.is_paused is False
        assert result.concurrency_limit is None
        assert (
            result.storage_configuration == schemas.core.WorkPoolStorageConfiguration()
        )

    async def test_create_work_pool_with_options(self, session: AsyncSession):
        result = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(
                name="My Test Pool", is_paused=True, concurrency_limit=5
            ),
        )

        assert result.name == "My Test Pool"
        assert result.is_paused is True
        assert result.concurrency_limit == 5

    async def test_create_duplicate_work_pool(
        self, session: AsyncSession, work_pool: schemas.core.WorkPool
    ):
        with pytest.raises(sa.exc.IntegrityError):
            await models.workers.create_work_pool(
                session=session,
                work_pool=schemas.actions.WorkPoolCreate(name=work_pool.name),
            )

    @pytest.mark.parametrize("name", ["hi/there", "hi%there"])
    async def test_create_invalid_name(self, session: AsyncSession, name: str):
        with pytest.raises(
            pydantic.ValidationError, match="String should match pattern"
        ):
            schemas.core.WorkPool(type="process", name=name)

    @pytest.mark.parametrize("type", ["PROCESS", "K8S", "AGENT"])
    async def test_create_typed_worker(self, session: AsyncSession, type: str):
        result = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(
                name="Typed Worker",
                type=type,
            ),
        )
        assert result.type == type


class TestDefaultQueues:
    async def test_creating_a_pool_creates_default_queue(self, session: AsyncSession):
        result = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(name="My Test Pool"),
        )

        # read the default queue
        queue = await models.workers.read_work_queue(
            session=session, work_queue_id=result.default_queue_id
        )

        assert queue.name == "default"
        assert queue.priority == 1

        # check that it is the only queue for the pool
        all_queues = await models.workers.read_work_queues(
            session=session, work_pool_id=result.id
        )
        assert len(all_queues) == 1
        assert all_queues[0].id == result.default_queue_id

    async def test_cant_delete_default_queue(self, session, work_pool):
        with pytest.raises(ValueError, match="(Can't delete a pool's default queue.)"):
            await models.workers.delete_work_queue(
                session=session, work_queue_id=work_pool.default_queue_id
            )

    async def test_cant_delete_default_queue_even_in_db(self, session, work_pool, db):
        """Deleting the default queue is not allowed in the db, even if you bypass the model"""
        with pytest.raises(sa.exc.IntegrityError):
            await session.execute(
                sa.delete(db.WorkQueue).where(
                    db.WorkQueue.id == work_pool.default_queue_id
                )
            )

    async def test_can_rename_default_queue(self, session, work_pool):
        queue = await models.workers.read_work_queue(
            session=session, work_queue_id=work_pool.default_queue_id
        )
        assert queue.name == "default"

        assert await models.workers.update_work_queue(
            session=session,
            work_queue_id=work_pool.default_queue_id,
            work_queue=schemas.actions.WorkQueueUpdate(name="New Name"),
        )
        await session.commit()
        session.expunge_all()

        queue = await models.workers.read_work_queue(
            session=session, work_queue_id=work_pool.default_queue_id
        )
        assert queue.name == "New Name"

    async def test_can_reprioritize_default_queue(self, session, work_pool):
        queue = await models.workers.read_work_queue(
            session=session, work_queue_id=work_pool.default_queue_id
        )
        assert queue.priority == 1

        # create a new queue so we can reprioritize them
        await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="New Queue"),
        )
        assert await models.workers.update_work_queue(
            session=session,
            work_queue_id=work_pool.default_queue_id,
            work_queue=schemas.actions.WorkQueueUpdate(priority=2),
        )
        await session.commit()
        session.expunge_all()

        queue = await models.workers.read_work_queue(
            session=session, work_queue_id=work_pool.default_queue_id
        )
        assert queue.priority == 2


class TestUpdateWorkPool:
    async def test_update_work_pool(self, session, work_pool):
        assert await models.workers.update_work_pool(
            session=session,
            work_pool_id=work_pool.id,
            work_pool=schemas.actions.WorkPoolUpdate(
                is_paused=True, concurrency_limit=5
            ),
            emit_status_change=None,
        )

        result = await models.workers.read_work_pool(
            session=session, work_pool_id=work_pool.id
        )
        assert result.is_paused is True
        assert result.concurrency_limit == 5

    async def test_update_work_pool_invalid_concurrency(
        self, session: AsyncSession, work_pool: schemas.core.WorkPool
    ):
        with pytest.raises(pydantic.ValidationError):
            await models.workers.update_work_pool(
                session=session,
                work_pool_id=work_pool.id,
                work_pool=schemas.actions.WorkPoolUpdate(concurrency_limit=-5),
                emit_status_change=None,
            )

    async def test_update_work_pool_zero_concurrency(
        self, session: AsyncSession, work_pool: schemas.core.WorkPool
    ):
        assert await models.workers.update_work_pool(
            session=session,
            work_pool_id=work_pool.id,
            work_pool=schemas.actions.WorkPoolUpdate(concurrency_limit=0),
            emit_status_change=None,
        )
        result = await models.workers.read_work_pool(
            session=session, work_pool_id=work_pool.id
        )
        assert result.concurrency_limit == 0


class TestReadWorkPool:
    async def test_read_work_pool(
        self, session: AsyncSession, work_pool: schemas.core.WorkPool
    ):
        result = await models.workers.read_work_pool(
            session=session, work_pool_id=work_pool.id
        )
        assert result.name == work_pool.name
        assert result.is_paused is work_pool.is_paused
        assert result.concurrency_limit == work_pool.concurrency_limit


class TestCountWorkPools:
    async def test_count_work_pool(
        self, session: AsyncSession, work_pool: schemas.core.WorkPool
    ):
        result = await models.workers.count_work_pools(
            session=session,
        )
        assert result == 1

        random_name = "not-my-work-pool"
        assert random_name != work_pool.name

        filtered_result = await models.workers.count_work_pools(
            session=session,
            work_pool_filter=schemas.filters.WorkPoolFilter(
                name={"any_": [random_name]}
            ),
        )
        assert filtered_result == 0


class TestDeleteWorkPool:
    async def test_delete_work_pool(self, session, work_pool):
        assert await models.workers.delete_work_pool(
            session=session, work_pool_id=work_pool.id
        )
        assert not await models.workers.read_work_pool(
            session=session, work_pool_id=work_pool.id
        )

    async def test_delete_work_pool_non_existent(self, session, work_pool):
        assert await models.workers.delete_work_pool(
            session=session, work_pool_id=work_pool.id
        )
        assert not await models.workers.delete_work_pool(
            session=session, work_pool_id=work_pool.id
        )


class TestCreateWorkQueue:
    async def test_create_work_queue(self, session, work_pool, db):
        result = await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="A"),
        )

        assert result.name == "A"
        assert result.work_pool_id == work_pool.id
        assert result.is_paused is False
        assert result.concurrency_limit is None

        # this is the second queue created after the default, so it should have priority 2
        assert result.priority == 2

    async def test_create_work_queue_with_options(self, session, work_pool):
        result = await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(
                name="A", is_paused=True, concurrency_limit=5
            ),
        )

        assert result.name == "A"
        assert result.work_pool_id == work_pool.id
        assert result.is_paused is True
        assert result.concurrency_limit == 5

    async def test_create_work_queue_with_priority(self, session, work_pool):
        result = await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="A", priority=1),
        )

        assert result.priority == 1

        default_queue = await models.workers.read_work_queue(
            session=session, work_queue_id=work_pool.default_queue_id
        )
        assert default_queue.priority == 2

    async def test_queues_initialize_with_correct_priority(self, session, work_pool):
        result_1 = await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="A"),
        )
        result_2 = await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="B"),
        )
        result_3 = await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="C"),
        )

        assert result_1.priority == 2
        assert result_2.priority == 3
        assert result_3.priority == 4

    async def test_create_duplicate_work_queue(self, session, work_queue):
        with pytest.raises(sa.exc.IntegrityError):
            await models.workers.create_work_queue(
                session=session,
                work_pool_id=work_queue.work_pool_id,
                work_queue=schemas.actions.WorkQueueCreate(name=work_queue.name),
            )

    @pytest.mark.parametrize("name", ["hi/there", "hi%there"])
    async def test_create_invalid_name(self, session, work_pool, name):
        with pytest.raises(
            pydantic.ValidationError, match="String should match pattern"
        ):
            schemas.actions.WorkQueueCreate(name=name)


class TestReadWorkQueues:
    async def test_read_work_queues(self, session, work_pool):
        await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="C"),
        )
        await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="A"),
        )
        await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="B"),
        )

        result = await models.workers.read_work_queues(
            session=session, work_pool_id=work_pool.id
        )
        assert len(result) == 4
        assert (result[0].name, result[0].priority) == ("default", 1)
        assert (result[1].name, result[1].priority) == ("C", 2)
        assert (result[2].name, result[2].priority) == ("A", 3)
        assert (result[3].name, result[3].priority) == ("B", 4)

    async def test_read_work_queues_sorts_by_priority(self, session, work_pool):
        await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="C"),
        )
        result_2 = await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="A"),
        )
        await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="B"),
        )
        await models.workers.update_work_queue(
            session=session,
            work_queue_id=result_2.id,
            work_queue=schemas.actions.WorkQueueUpdate(priority=100),
        )

        result = await models.workers.read_work_queues(
            session=session, work_pool_id=work_pool.id
        )
        assert len(result) == 4
        assert (result[0].name, result[0].priority) == ("default", 1)
        assert (result[1].name, result[1].priority) == ("C", 2)
        assert (result[2].name, result[2].priority) == ("B", 4)
        assert (result[3].name, result[3].priority) == ("A", 100)


class TestUpdateWorkQueue:
    async def test_update_work_queue(self, session, work_queue):
        assert await models.workers.update_work_queue(
            session=session,
            work_queue_id=work_queue.id,
            work_queue=schemas.actions.WorkQueueUpdate(
                is_paused=True, concurrency_limit=5
            ),
        )

        result = await models.workers.read_work_queue(
            session=session, work_queue_id=work_queue.id
        )
        assert result.is_paused is True
        assert result.concurrency_limit == 5

    async def test_update_work_queue_invalid_concurrency(self, session, work_queue):
        with pytest.raises(pydantic.ValidationError):
            await models.workers.update_work_queue(
                session=session,
                work_queue_id=work_queue.id,
                work_queue=schemas.actions.WorkQueueUpdate(concurrency_limit=-5),
            )

    async def test_update_work_queue_zero_concurrency(self, session, work_queue):
        assert await models.workers.update_work_queue(
            session=session,
            work_queue_id=work_queue.id,
            work_queue=schemas.actions.WorkQueueUpdate(concurrency_limit=0),
        )
        result = await models.workers.read_work_queue(
            session=session, work_queue_id=work_queue.id
        )
        assert result.concurrency_limit == 0


class TestUpdateWorkQueuePriorities:
    @pytest.fixture(autouse=True)
    async def queues(self, session, work_pool):
        queues = {}
        # rename the default queue "A"

        queues["A"] = await models.workers.read_work_queue(
            session=session, work_queue_id=work_pool.default_queue_id
        )
        queues["A"].name = "A"

        # create B-E
        for name in "BCDE":
            queues[name] = await models.workers.create_work_queue(
                session=session,
                work_pool_id=work_pool.id,
                work_queue=schemas.actions.WorkQueueCreate(name=name),
            )
        await session.commit()
        return queues

    @pytest.mark.parametrize(
        "new_priorities",
        [
            {"A": 2},
            {"A": 2, "B": 4},
            {"A": 2, "B": 4, "C": 1},
            {"A": 2, "B": 1},
            {"B": 2, "C": 3, "D": 4, "E": 5},
            {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5},
        ],
    )
    async def test_bulk_update_priorities(
        self, session, work_pool, queues, new_priorities
    ):
        all_queues = await models.workers.read_work_queues(
            session=session, work_pool_id=work_pool.id
        )
        assert len(all_queues) == 5

        await models.workers.bulk_update_work_queue_priorities(
            session=session,
            work_pool_id=work_pool.id,
            new_priorities={queues[k].id: v for k, v in new_priorities.items()},
        )
        await session.commit()

        all_queues = await models.workers.read_work_queues(
            session=session, work_pool_id=work_pool.id
        )
        assert len(all_queues) == 5

        all_queues = {q.name: q for q in all_queues}
        for k, v in new_priorities.items():
            assert all_queues[k].priority == v

    async def test_update_priorities_with_invalid_target_id(
        self, session, work_pool, queues
    ):
        await models.workers.bulk_update_work_queue_priorities(
            session=session,
            work_pool_id=work_pool.id,
            new_priorities={uuid4(): 3, queues["A"].id: 4},
        )
        all_queues = await models.workers.read_work_queues(
            session=session, work_pool_id=work_pool.id
        )
        assert next(q.priority for q in all_queues if q.name == "A") == 4

    async def test_update_priorities_with_duplicate_priorities(
        self, session, work_pool, queues
    ):
        with pytest.raises(ValueError, match="(Duplicate target priorities provided)"):
            await models.workers.bulk_update_work_queue_priorities(
                session=session,
                work_pool_id=work_pool.id,
                new_priorities={queues["A"]: 3, queues["B"].id: 3},
            )

    async def test_update_priorities_with_empty_new_priority(
        self, session, work_pool, queues
    ):
        await models.workers.bulk_update_work_queue_priorities(
            session=session,
            work_pool_id=work_pool.id,
            new_priorities={},
        )
        all_queues = await models.workers.read_work_queues(
            session=session, work_pool_id=work_pool.id
        )
        assert {q.name: q.priority for q in all_queues} == {
            "A": 1,
            "B": 2,
            "C": 3,
            "D": 4,
            "E": 5,
        }

    async def test_update_priorities_with_empty_new_priority_to_recompute(
        self, session, db, work_pool, queues
    ):
        # manually delete a queue (this won't trigger the automatic priority update)
        await session.execute(
            sa.delete(db.WorkQueue).where(db.WorkQueue.id == queues["C"].id)
        )
        await session.commit()

        all_queues = await models.workers.read_work_queues(
            session=session, work_pool_id=work_pool.id
        )
        assert {q.name: q.priority for q in all_queues} == {
            "A": 1,
            "B": 2,
            "D": 4,
            "E": 5,
        }

        await models.workers.bulk_update_work_queue_priorities(
            session=session,
            work_pool_id=work_pool.id,
            new_priorities={},
        )
        all_queues = await models.workers.read_work_queues(
            session=session, work_pool_id=work_pool.id
        )
        assert {q.name: q.priority for q in all_queues} == {
            "A": 1,
            "B": 2,
            "D": 4,
            "E": 5,
        }


class TestDeleteWorkQueue:
    async def test_delete_work_queue(self, session, work_queue):
        assert await models.workers.read_work_queue(
            session=session, work_queue_id=work_queue.id
        )
        assert await models.workers.delete_work_queue(
            session=session, work_queue_id=work_queue.id
        )
        assert not await models.workers.read_work_queue(
            session=session, work_queue_id=work_queue.id
        )

    async def test_nonexistent_delete_work_queue(self, session):
        assert not await models.workers.delete_work_queue(
            session=session, work_queue_id=uuid4()
        )

    async def test_delete_queue_updates_priorities(self, session, work_pool):
        await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="A"),
        )
        result_2 = await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="B"),
        )
        await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="C"),
        )

        # delete queue 2
        assert await models.workers.delete_work_queue(
            session=session, work_queue_id=result_2.id
        )

        # read queues
        result = await models.workers.read_work_queues(
            session=session, work_pool_id=work_pool.id
        )

        assert len(result) == 3
        assert (result[0].name, result[0].priority) == ("default", 1)
        assert (result[1].name, result[1].priority) == ("A", 2)
        assert (result[2].name, result[2].priority) == ("C", 4)


class TestWorkerHeartbeat:
    async def test_worker_heartbeat(self, session, work_pool):
        processes = await models.workers.read_workers(
            session=session, work_pool_id=work_pool.id
        )
        assert not processes

        result = await models.workers.worker_heartbeat(
            session=session, work_pool_id=work_pool.id, worker_name="process X"
        )

        assert result is True

        processes = await models.workers.read_workers(
            session=session, work_pool_id=work_pool.id
        )
        assert len(processes) == 1
        assert processes[0].name == "process X"

    async def test_worker_heartbeat_upsert(self, session, work_pool):
        processes = await models.workers.read_workers(
            session=session, work_pool_id=work_pool.id
        )
        assert not processes

        for _ in range(3):
            await models.workers.worker_heartbeat(
                session=session,
                work_pool_id=work_pool.id,
                worker_name="process X",
            )

        processes = await models.workers.read_workers(
            session=session, work_pool_id=work_pool.id
        )
        assert len(processes) == 1
        assert processes[0].name == "process X"

    async def test_multiple_worker_heartbeats(self, session, work_pool):
        processes = await models.workers.read_workers(
            session=session, work_pool_id=work_pool.id
        )
        assert not processes

        for name in ["X", "Y", "Z"]:
            await models.workers.worker_heartbeat(
                session=session,
                work_pool_id=work_pool.id,
                worker_name=name,
            )

        processes = await models.workers.read_workers(
            session=session, work_pool_id=work_pool.id
        )
        assert len(processes) == 3
        assert processes[0].name == "Z"
        assert processes[1].name == "Y"
        assert processes[2].name == "X"


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
                    state=schemas.states.Running(),
                    work_queue_id=wq.id,
                ),
            )

            # create a pending run
            await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id,
                    state=schemas.states.Pending(),
                    work_queue_id=wq.id,
                ),
            )

            # create scheduled runs
            for i in range(3, -2, -1):
                current_time = now("UTC") + datetime.timedelta(hours=i)
                await models.flow_runs.create_flow_run(
                    session=session,
                    flow_run=schemas.core.FlowRun(
                        flow_id=flow.id,
                        state=schemas.states.Scheduled(scheduled_time=current_time),
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

    async def test_get_all_runs(self, session):
        runs = await models.workers.get_scheduled_flow_runs(session=session)
        assert len(runs) == 45

        # runs are not sorted by time because they're sorted by queue priority
        assert runs != sorted(runs, key=lambda r: r.flow_run.next_scheduled_start_time)

    async def test_get_all_runs_without_queue_priority(self, session):
        runs = await models.workers.get_scheduled_flow_runs(
            session=session, respect_queue_priorities=False
        )
        assert len(runs) == 45

        # runs are sorted by time
        assert runs == sorted(runs, key=lambda r: r.flow_run.next_scheduled_start_time)

    async def test_get_all_runs_limit(self, session):
        runs = await models.workers.get_scheduled_flow_runs(session=session, limit=12)
        assert len(runs) == 12

    async def test_get_all_runs_scheduled_before(self, session):
        runs = await models.workers.get_scheduled_flow_runs(
            session=session, scheduled_before=now("UTC")
        )
        assert len(runs) == 18

    async def test_get_all_runs_scheduled_after(self, session):
        runs = await models.workers.get_scheduled_flow_runs(
            session=session, scheduled_after=now("UTC")
        )
        assert len(runs) == 27

    async def test_get_all_runs_wq_aa(self, session, work_pools, work_queues):
        runs = await models.workers.get_scheduled_flow_runs(
            session=session, work_queue_ids=[work_queues["wq_aa"].id]
        )
        assert len(runs) == 5

    async def test_get_all_runs_wq_aa_wq_ba_wq_cb(
        self, session, work_pools, work_queues
    ):
        runs = await models.workers.get_scheduled_flow_runs(
            session=session,
            work_queue_ids=[
                work_queues["wq_aa"].id,
                work_queues["wq_ba"].id,
                work_queues["wq_cb"].id,
            ],
        )
        assert len(runs) == 15

    async def test_get_all_runs_wp_a(self, session, work_pools, work_queues):
        runs = await models.workers.get_scheduled_flow_runs(
            session=session, work_pool_ids=[work_pools["wp_a"].id]
        )
        assert len(runs) == 15

    async def test_get_all_runs_wp_a_wp_b(self, session, work_pools, work_queues):
        runs = await models.workers.get_scheduled_flow_runs(
            session=session,
            work_pool_ids=[work_pools["wp_a"].id, work_pools["wp_b"].id],
        )
        assert len(runs) == 30

    async def test_get_all_runs_pools_and_queues_combined(
        self, session, work_pools, work_queues
    ):
        runs = await models.workers.get_scheduled_flow_runs(
            session=session,
            work_pool_ids=[work_pools["wp_a"].id],
            work_queue_ids=[work_queues["wq_aa"].id],
        )
        assert len(runs) == 5

    async def test_get_all_runs_pools_and_queues_incompatible(
        self, session, work_pools, work_queues
    ):
        runs = await models.workers.get_scheduled_flow_runs(
            session=session,
            work_pool_ids=[work_pools["wp_b"].id],
            work_queue_ids=[work_queues["wq_aa"].id],
        )
        assert len(runs) == 0


class TestDeleteWorker:
    async def test_delete_worker(self, session, work_pool):
        for i in range(3):
            await models.workers.worker_heartbeat(
                session=session, work_pool_id=work_pool.id, worker_name=f"worker.{i}"
            )
        await models.workers.delete_worker(
            session=session, work_pool_id=work_pool.id, worker_name="worker.1"
        )
        remaining_workers = await models.workers.read_workers(
            session=session, work_pool_id=work_pool.id
        )
        assert len(remaining_workers) == 2
        assert "worker.1" not in map(lambda x: x.name, remaining_workers)

    async def test_delete_nonexistent_worker(self, session, work_pool):
        assert not await models.workers.delete_worker(
            session=session, work_pool_id=work_pool.id, worker_name="worker.1"
        )

from uuid import uuid4

import pendulum
import pydantic
import pytest
import sqlalchemy as sa

import prefect
from prefect.orion import models, schemas


class TestCreateWorkerPool:
    async def test_create_worker_pool(self, session):
        result = await models.workers.create_worker_pool(
            session=session,
            worker_pool=schemas.actions.WorkerPoolCreate(name="My Test Pool"),
        )

        assert result.name == "My Test Pool"
        assert result.is_paused is False
        assert result.concurrency_limit is None

    async def test_create_worker_pool_with_options(self, session):
        result = await models.workers.create_worker_pool(
            session=session,
            worker_pool=schemas.actions.WorkerPoolCreate(
                name="My Test Pool", is_paused=True, concurrency_limit=5
            ),
        )

        assert result.name == "My Test Pool"
        assert result.is_paused is True
        assert result.concurrency_limit == 5

    async def test_create_duplicate_worker_pool(self, session, worker_pool):
        with pytest.raises(sa.exc.IntegrityError):
            await models.workers.create_worker_pool(
                session=session,
                worker_pool=schemas.actions.WorkerPoolCreate(name=worker_pool.name),
            )

    @pytest.mark.parametrize("name", ["hi/there", "hi%there"])
    async def test_create_invalid_name(self, session, name):
        with pytest.raises(pydantic.ValidationError, match="(invalid character)"):
            schemas.core.WorkerPool(name=name)

    @pytest.mark.parametrize("type", [None, "PROCESS", "K8S", "AGENT"])
    async def test_create_typed_worker(self, session, type):
        result = await models.workers.create_worker_pool(
            session=session,
            worker_pool=schemas.actions.WorkerPoolCreate(
                name="Typed Worker",
                type=type,
            ),
        )
        assert result.type == type


class TestDefaultQueues:
    async def test_creating_a_pool_creates_default_queue(self, session):
        result = await models.workers.create_worker_pool(
            session=session,
            worker_pool=schemas.actions.WorkerPoolCreate(name="My Test Pool"),
        )

        # read the default queue
        queue = await models.workers.read_worker_pool_queue(
            session=session, worker_pool_queue_id=result.default_queue_id
        )

        assert queue.name == "Default Queue"
        assert queue.priority == 1

        # check that it is the only queue for the pool
        all_queues = await models.workers.read_worker_pool_queues(
            session=session, worker_pool_id=result.id
        )
        assert len(all_queues) == 1
        assert all_queues[0].id == result.default_queue_id

    async def test_cant_delete_default_queue(self, session, worker_pool):
        with pytest.raises(ValueError, match="(Can't delete a pool's default queue.)"):
            await models.workers.delete_worker_pool_queue(
                session=session, worker_pool_queue_id=worker_pool.default_queue_id
            )

    async def test_cant_delete_default_queue_even_in_db(self, session, worker_pool, db):
        """Deleting the default queue is not allowed in the db, even if you bypass the model"""
        with pytest.raises(sa.exc.IntegrityError):
            await session.execute(
                sa.delete(db.WorkerPoolQueue).where(
                    db.WorkerPoolQueue.id == worker_pool.default_queue_id
                )
            )

    async def test_can_rename_default_queue(self, session, worker_pool):
        queue = await models.workers.read_worker_pool_queue(
            session=session, worker_pool_queue_id=worker_pool.default_queue_id
        )
        assert queue.name == "Default Queue"

        assert await models.workers.update_worker_pool_queue(
            session=session,
            worker_pool_queue_id=worker_pool.default_queue_id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueUpdate(name="New Name"),
        )
        await session.commit()
        session.expunge_all()

        queue = await models.workers.read_worker_pool_queue(
            session=session, worker_pool_queue_id=worker_pool.default_queue_id
        )
        assert queue.name == "New Name"

    async def test_can_reprioritize_default_queue(self, session, worker_pool):
        queue = await models.workers.read_worker_pool_queue(
            session=session, worker_pool_queue_id=worker_pool.default_queue_id
        )
        assert queue.priority == 1

        # create a new queue so we can reprioritize them
        await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=worker_pool.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="New Queue"),
        )
        assert await models.workers.update_worker_pool_queue(
            session=session,
            worker_pool_queue_id=worker_pool.default_queue_id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueUpdate(priority=2),
        )
        await session.commit()
        session.expunge_all()

        queue = await models.workers.read_worker_pool_queue(
            session=session, worker_pool_queue_id=worker_pool.default_queue_id
        )
        assert queue.priority == 2


class TestUpdateWorkerPool:
    async def test_update_worker_pool(self, session, worker_pool):
        assert await models.workers.update_worker_pool(
            session=session,
            worker_pool_id=worker_pool.id,
            worker_pool=schemas.actions.WorkerPoolUpdate(
                is_paused=True, concurrency_limit=5
            ),
        )

        result = await models.workers.read_worker_pool(
            session=session, worker_pool_id=worker_pool.id
        )
        assert result.is_paused is True
        assert result.concurrency_limit == 5

    async def test_update_worker_pool_invalid_concurrency(self, session, worker_pool):
        with pytest.raises(pydantic.ValidationError):
            await models.workers.update_worker_pool(
                session=session,
                worker_pool_id=worker_pool.id,
                worker_pool=schemas.actions.WorkerPoolUpdate(concurrency_limit=-5),
            )

    async def test_update_worker_pool_zero_concurrency(self, session, worker_pool):
        assert await models.workers.update_worker_pool(
            session=session,
            worker_pool_id=worker_pool.id,
            worker_pool=schemas.actions.WorkerPoolUpdate(concurrency_limit=0),
        )
        result = await models.workers.read_worker_pool(
            session=session, worker_pool_id=worker_pool.id
        )
        assert result.concurrency_limit == 0


class TestReadWorkerPool:
    async def test_read_worker_pool(self, session, worker_pool):
        result = await models.workers.read_worker_pool(
            session=session, worker_pool_id=worker_pool.id
        )
        assert result.name == worker_pool.name
        assert result.is_paused is worker_pool.is_paused
        assert result.concurrency_limit == worker_pool.concurrency_limit


class TestDeleteWorkerPool:
    async def test_delete_worker_pool(self, session, worker_pool):
        assert await models.workers.delete_worker_pool(
            session=session, worker_pool_id=worker_pool.id
        )
        assert not await models.workers.read_worker_pool(
            session=session, worker_pool_id=worker_pool.id
        )

    async def test_delete_worker_pool_non_existent(self, session, worker_pool):
        assert await models.workers.delete_worker_pool(
            session=session, worker_pool_id=worker_pool.id
        )
        assert not await models.workers.delete_worker_pool(
            session=session, worker_pool_id=worker_pool.id
        )


class TestCreateWorkerPoolQueue:
    async def test_create_worker_pool_queue(self, session, worker_pool, db):
        result = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=worker_pool.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="A"),
        )

        assert result.name == "A"
        assert result.worker_pool_id == worker_pool.id
        assert result.is_paused is False
        assert result.concurrency_limit is None

        # this is the second queue created after the default, so it should have priority 2
        assert result.priority == 2

    async def test_create_worker_pool_queue_with_options(self, session, worker_pool):
        result = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=worker_pool.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(
                name="A", is_paused=True, concurrency_limit=5
            ),
        )

        assert result.name == "A"
        assert result.worker_pool_id == worker_pool.id
        assert result.is_paused is True
        assert result.concurrency_limit == 5

    async def test_create_worker_pool_queue_with_priority(self, session, worker_pool):
        result = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=worker_pool.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(
                name="A", priority=1
            ),
        )

        assert result.priority == 1

        default_queue = await models.workers.read_worker_pool_queue(
            session=session, worker_pool_queue_id=worker_pool.default_queue_id
        )
        assert default_queue.priority == 2

    async def test_queues_initialize_with_correct_priority(self, session, worker_pool):
        result_1 = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=worker_pool.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="A"),
        )
        result_2 = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=worker_pool.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="B"),
        )
        result_3 = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=worker_pool.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="C"),
        )

        assert result_1.priority == 2
        assert result_2.priority == 3
        assert result_3.priority == 4

    async def test_create_duplicate_worker_pool_queue(self, session, worker_pool_queue):
        with pytest.raises(sa.exc.IntegrityError):
            await models.workers.create_worker_pool_queue(
                session=session,
                worker_pool_id=worker_pool_queue.worker_pool_id,
                worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(
                    name=worker_pool_queue.name
                ),
            )

    @pytest.mark.parametrize("name", ["hi/there", "hi%there"])
    async def test_create_invalid_name(self, session, worker_pool, name):
        with pytest.raises(pydantic.ValidationError, match="(invalid character)"):
            schemas.actions.WorkerPoolQueueCreate(name=name)


class TestReadWorkerPoolQueues:
    async def test_read_worker_pool_queues(self, session, worker_pool):
        await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=worker_pool.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="C"),
        )
        await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=worker_pool.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="A"),
        )
        await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=worker_pool.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="B"),
        )

        result = await models.workers.read_worker_pool_queues(
            session=session, worker_pool_id=worker_pool.id
        )
        assert len(result) == 4
        assert (result[0].name, result[0].priority) == ("Default Queue", 1)
        assert (result[1].name, result[1].priority) == ("C", 2)
        assert (result[2].name, result[2].priority) == ("A", 3)
        assert (result[3].name, result[3].priority) == ("B", 4)

    async def test_read_worker_pool_queues_sorts_by_priority(
        self, session, worker_pool
    ):
        await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=worker_pool.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="C"),
        )
        result_2 = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=worker_pool.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="A"),
        )
        await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=worker_pool.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="B"),
        )
        await models.workers.update_worker_pool_queue(
            session=session,
            worker_pool_queue_id=result_2.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueUpdate(priority=100),
        )

        result = await models.workers.read_worker_pool_queues(
            session=session, worker_pool_id=worker_pool.id
        )
        assert len(result) == 4
        assert (result[0].name, result[0].priority) == ("Default Queue", 1)
        assert (result[1].name, result[1].priority) == ("C", 2)
        assert (result[2].name, result[2].priority) == ("B", 3)
        assert (result[3].name, result[3].priority) == ("A", 4)


class TestUpdateWorkerPoolQueue:
    async def test_update_worker_pool_queue(self, session, worker_pool_queue):
        assert await models.workers.update_worker_pool_queue(
            session=session,
            worker_pool_queue_id=worker_pool_queue.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueUpdate(
                is_paused=True, concurrency_limit=5
            ),
        )

        result = await models.workers.read_worker_pool_queue(
            session=session, worker_pool_queue_id=worker_pool_queue.id
        )
        assert result.is_paused is True
        assert result.concurrency_limit == 5

    async def test_update_worker_pool_queue_invalid_concurrency(
        self, session, worker_pool_queue
    ):
        with pytest.raises(pydantic.ValidationError):
            await models.workers.update_worker_pool_queue(
                session=session,
                worker_pool_queue_id=worker_pool_queue.id,
                worker_pool_queue=schemas.actions.WorkerPoolQueueUpdate(
                    concurrency_limit=-5
                ),
            )

    async def test_update_worker_pool_queue_zero_concurrency(
        self, session, worker_pool_queue
    ):
        assert await models.workers.update_worker_pool_queue(
            session=session,
            worker_pool_queue_id=worker_pool_queue.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueUpdate(
                concurrency_limit=0
            ),
        )
        result = await models.workers.read_worker_pool_queue(
            session=session, worker_pool_queue_id=worker_pool_queue.id
        )
        assert result.concurrency_limit == 0

    async def test_update_worker_pool_queue_priority_is_normalized_for_number_of_queues(
        self, session, worker_pool_queue
    ):
        assert await models.workers.update_worker_pool_queue(
            session=session,
            worker_pool_queue_id=worker_pool_queue.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueUpdate(priority=100),
        )
        result = await models.workers.read_worker_pool_queue(
            session=session, worker_pool_queue_id=worker_pool_queue.id
        )
        assert result.priority == 2


class TestUpdateWorkerPoolQueuePriorities:
    @pytest.fixture(autouse=True)
    async def queues(self, session, worker_pool):
        queues = {}
        # rename the default queue "A"

        queues["A"] = await models.workers.read_worker_pool_queue(
            session=session, worker_pool_queue_id=worker_pool.default_queue_id
        )
        queues["A"].name = "A"

        # create B-E
        for name in "BCDE":
            queues[name] = await models.workers.create_worker_pool_queue(
                session=session,
                worker_pool_id=worker_pool.id,
                worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name=name),
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
        self, session, worker_pool, queues, new_priorities
    ):

        all_queues = await models.workers.read_worker_pool_queues(
            session=session, worker_pool_id=worker_pool.id
        )
        assert len(all_queues) == 5

        await models.workers.bulk_update_worker_pool_queue_priorities(
            session=session,
            worker_pool_id=worker_pool.id,
            new_priorities={queues[k].id: v for k, v in new_priorities.items()},
        )
        await session.commit()

        all_queues = await models.workers.read_worker_pool_queues(
            session=session, worker_pool_id=worker_pool.id
        )
        assert len(all_queues) == 5

        all_queues = {q.name: q for q in all_queues}
        for k, v in new_priorities.items():
            assert all_queues[k].priority == v

    async def test_update_priorities_with_invalid_target_id(
        self, session, worker_pool, queues
    ):
        await models.workers.bulk_update_worker_pool_queue_priorities(
            session=session,
            worker_pool_id=worker_pool.id,
            new_priorities={uuid4(): 3, queues["A"].id: 4},
        )
        all_queues = await models.workers.read_worker_pool_queues(
            session=session, worker_pool_id=worker_pool.id
        )
        assert next(q.priority for q in all_queues if q.name == "A") == 4

    async def test_update_priorities_with_duplicate_priorities(
        self, session, worker_pool, queues
    ):
        with pytest.raises(ValueError, match="(Duplicate target priorities provided)"):
            await models.workers.bulk_update_worker_pool_queue_priorities(
                session=session,
                worker_pool_id=worker_pool.id,
                new_priorities={queues["A"]: 3, queues["B"].id: 3},
            )

    async def test_update_priorities_with_empty_new_priority(
        self, session, worker_pool, queues
    ):
        await models.workers.bulk_update_worker_pool_queue_priorities(
            session=session,
            worker_pool_id=worker_pool.id,
            new_priorities={},
        )
        all_queues = await models.workers.read_worker_pool_queues(
            session=session, worker_pool_id=worker_pool.id
        )
        assert {q.name: q.priority for q in all_queues} == {
            "A": 1,
            "B": 2,
            "C": 3,
            "D": 4,
            "E": 5,
        }

    async def test_update_priorities_with_empty_new_priority_to_recompute(
        self, session, db, worker_pool, queues
    ):
        # manually delete a queue (this won't trigger the automatic priority update)
        await session.execute(
            sa.delete(db.WorkerPoolQueue).where(db.WorkerPoolQueue.id == queues["C"].id)
        )
        await session.commit()

        all_queues = await models.workers.read_worker_pool_queues(
            session=session, worker_pool_id=worker_pool.id
        )
        assert {q.name: q.priority for q in all_queues} == {
            "A": 1,
            "B": 2,
            "D": 4,
            "E": 5,
        }

        await models.workers.bulk_update_worker_pool_queue_priorities(
            session=session,
            worker_pool_id=worker_pool.id,
            new_priorities={},
        )
        all_queues = await models.workers.read_worker_pool_queues(
            session=session, worker_pool_id=worker_pool.id
        )
        assert {q.name: q.priority for q in all_queues} == {
            "A": 1,
            "B": 2,
            "D": 3,
            "E": 4,
        }


class TestDeleteWorkerPoolQueue:
    async def test_delete_worker_pool_queue(self, session, worker_pool_queue):
        assert await models.workers.read_worker_pool_queue(
            session=session, worker_pool_queue_id=worker_pool_queue.id
        )
        assert await models.workers.delete_worker_pool_queue(
            session=session, worker_pool_queue_id=worker_pool_queue.id
        )
        assert not await models.workers.read_worker_pool_queue(
            session=session, worker_pool_queue_id=worker_pool_queue.id
        )

    async def test_nonexistent_delete_worker_pool_queue(self, session):
        assert not await models.workers.delete_worker_pool_queue(
            session=session, worker_pool_queue_id=uuid4()
        )

    async def test_delete_queue_updates_priorities(self, session, worker_pool):
        result_1 = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=worker_pool.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="A"),
        )
        result_2 = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=worker_pool.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="B"),
        )
        result_3 = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=worker_pool.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="C"),
        )

        # delete queue 2
        assert await models.workers.delete_worker_pool_queue(
            session=session, worker_pool_queue_id=result_2.id
        )

        # read queues
        result = await models.workers.read_worker_pool_queues(
            session=session, worker_pool_id=worker_pool.id
        )

        assert len(result) == 3
        assert (result[0].name, result[0].priority) == ("Default Queue", 1)
        assert (result[1].name, result[1].priority) == ("A", 2)
        assert (result[2].name, result[2].priority) == ("C", 3)


class TestWorkerHeartbeat:
    async def test_worker_heartbeat(self, session, worker_pool):
        processes = await models.workers.read_workers(
            session=session, worker_pool_id=worker_pool.id
        )
        assert not processes

        result = await models.workers.worker_heartbeat(
            session=session, worker_pool_id=worker_pool.id, worker_name="process X"
        )

        assert result is True

        processes = await models.workers.read_workers(
            session=session, worker_pool_id=worker_pool.id
        )
        assert len(processes) == 1
        assert processes[0].name == "process X"

    async def test_worker_heartbeat_upsert(self, session, worker_pool):
        processes = await models.workers.read_workers(
            session=session, worker_pool_id=worker_pool.id
        )
        assert not processes

        for _ in range(3):
            await models.workers.worker_heartbeat(
                session=session,
                worker_pool_id=worker_pool.id,
                worker_name="process X",
            )

        processes = await models.workers.read_workers(
            session=session, worker_pool_id=worker_pool.id
        )
        assert len(processes) == 1
        assert processes[0].name == "process X"

    async def test_multiple_worker_heartbeats(self, session, worker_pool):
        processes = await models.workers.read_workers(
            session=session, worker_pool_id=worker_pool.id
        )
        assert not processes

        for name in ["X", "Y", "Z"]:
            await models.workers.worker_heartbeat(
                session=session,
                worker_pool_id=worker_pool.id,
                worker_name=name,
            )

        processes = await models.workers.read_workers(
            session=session, worker_pool_id=worker_pool.id
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
            session=session, scheduled_before=pendulum.now()
        )
        assert len(runs) == 18

    async def test_get_all_runs_scheduled_after(self, session):
        runs = await models.workers.get_scheduled_flow_runs(
            session=session, scheduled_after=pendulum.now()
        )
        assert len(runs) == 27

    async def test_get_all_runs_wq_aa(self, session, worker_pools, worker_pool_queues):
        runs = await models.workers.get_scheduled_flow_runs(
            session=session, worker_pool_queue_ids=[worker_pool_queues["wq_aa"].id]
        )
        assert len(runs) == 5

    async def test_get_all_runs_wq_aa_wq_ba_wq_cb(
        self, session, worker_pools, worker_pool_queues
    ):
        runs = await models.workers.get_scheduled_flow_runs(
            session=session,
            worker_pool_queue_ids=[
                worker_pool_queues["wq_aa"].id,
                worker_pool_queues["wq_ba"].id,
                worker_pool_queues["wq_cb"].id,
            ],
        )
        assert len(runs) == 15

    async def test_get_all_runs_wp_a(self, session, worker_pools, worker_pool_queues):
        runs = await models.workers.get_scheduled_flow_runs(
            session=session, worker_pool_ids=[worker_pools["wp_a"].id]
        )
        assert len(runs) == 15

    async def test_get_all_runs_wp_a_wp_b(
        self, session, worker_pools, worker_pool_queues
    ):
        runs = await models.workers.get_scheduled_flow_runs(
            session=session,
            worker_pool_ids=[worker_pools["wp_a"].id, worker_pools["wp_b"].id],
        )
        assert len(runs) == 30

    async def test_get_all_runs_pools_and_queues_combined(
        self, session, worker_pools, worker_pool_queues
    ):
        runs = await models.workers.get_scheduled_flow_runs(
            session=session,
            worker_pool_ids=[worker_pools["wp_a"].id],
            worker_pool_queue_ids=[worker_pool_queues["wq_aa"].id],
        )
        assert len(runs) == 5

    async def test_get_all_runs_pools_and_queues_incompatible(
        self, session, worker_pools, worker_pool_queues
    ):
        runs = await models.workers.get_scheduled_flow_runs(
            session=session,
            worker_pool_ids=[worker_pools["wp_b"].id],
            worker_pool_queue_ids=[worker_pool_queues["wq_aa"].id],
        )
        assert len(runs) == 0

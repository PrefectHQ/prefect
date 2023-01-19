from typing import List

import pendulum
import pytest

from prefect.orion import models, schemas
from prefect.states import Scheduled
from prefect.workers.base import BaseWorker

SUBMITTED_FLOW_RUNS = {}


@pytest.fixture
def prefect_caplog(caplog):
    # TODO: Determine a better pattern for this and expose for all tests
    import logging

    logger = logging.getLogger("prefect")
    logger.propagate = True

    try:
        yield caplog
    finally:
        logger.propagate = False


@pytest.fixture(autouse=True)
def clear_submitted_flow_runs():
    try:
        yield
    finally:
        SUBMITTED_FLOW_RUNS.clear()


class MyWorker(BaseWorker):
    # don't try to run this as a test!
    __test__ = False

    async def submit_scheduled_flow_runs(
        self, flow_run_response: List[schemas.responses.WorkerFlowRunResponse]
    ):
        """
        Simulate submitting flow runs by putting them in a dictionary that can
        be accessed by the unit test
        """
        SUBMITTED_FLOW_RUNS.setdefault(self, []).extend(flow_run_response)


class TestBaseWorker:
    def test_baseworker_uses_default_pool_name(self):
        assert BaseWorker.default_pool_name == "Default Pool"
        assert BaseWorker().worker_pool_name == "Default Pool"

    def test_subclass_can_override_default_pool_name(self):
        class TestWorker(BaseWorker):
            default_pool_name = "abc"

        assert TestWorker.default_pool_name == "abc"
        assert TestWorker().worker_pool_name == "abc"

    async def test_baseworker_requires_submit_method(self):
        with pytest.raises(NotImplementedError):
            await BaseWorker().submit_scheduled_flow_runs([])

    async def test_worker_creates_worker_pool(self, session):
        name = "a new test pool"
        assert not await models.workers.read_worker_pool_by_name(
            session=session, worker_pool_name=name
        )
        worker = MyWorker(worker_pool_name="a new test pool")
        await worker.start(loops=1)

        # pool exists now
        assert await models.workers.read_worker_pool_by_name(
            session=session, worker_pool_name=name
        )

    async def test_worker_can_be_told_not_to_create_pool(self, session, prefect_caplog):
        name = "a new test pool"
        assert not await models.workers.read_worker_pool_by_name(
            session=session, worker_pool_name=name
        )
        worker = MyWorker(
            worker_pool_name="a new test pool",
            create_pool_if_not_found=False,
        )
        await worker.start(loops=1)

        assert not await models.workers.read_worker_pool_by_name(
            session=session, worker_pool_name=name
        )

        assert f"Worker pool '{name}' not found!" in prefect_caplog.text


class TestGetScheduledRuns:
    @pytest.fixture(autouse=True)
    async def setup(self, session):
        wp1 = await models.workers.create_worker_pool(
            session=session, worker_pool=schemas.actions.WorkerPoolCreate(name="wp1")
        )
        wp2 = await models.workers.create_worker_pool(
            session=session, worker_pool=schemas.actions.WorkerPoolCreate(name="wp2")
        )

        q1 = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=wp1.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="q1"),
        )
        q2 = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=wp1.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="q2"),
        )
        q3 = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=wp2.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="q3"),
        )

        await session.commit()
        return wp1, wp2, q1, q2, q3

    async def test_worker_loads_runs_from_all_queues_in_pool(
        self, session, flow, setup
    ):
        wp1, wp2, q1, q2, q3 = setup

        fr1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id, state=Scheduled(), worker_pool_queue_id=q1.id
            ),
        )
        fr2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id, state=Scheduled(), worker_pool_queue_id=q2.id
            ),
        )
        fr3 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id, state=Scheduled(), worker_pool_queue_id=q3.id
            ),
        )

        await session.commit()

        worker1 = MyWorker(worker_pool_name=wp1.name)
        worker2 = MyWorker(worker_pool_name=wp2.name)

        await worker1.start(loops=1)
        await worker2.start(loops=1)

        assert [r.flow_run.id for r in SUBMITTED_FLOW_RUNS[worker1]] == [fr1.id, fr2.id]
        assert [r.flow_run.id for r in SUBMITTED_FLOW_RUNS[worker2]] == [fr3.id]

    async def test_prefetch(self, session, flow, setup):
        wp1, wp2, q1, q2, q3 = setup
        worker = MyWorker(worker_pool_name=wp1.name)

        fr1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=Scheduled(
                    scheduled_time=pendulum.now().add(seconds=worker.prefetch_seconds)
                ),
                worker_pool_queue_id=q1.id,
            ),
        )
        fr2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=Scheduled(
                    # add 10 seconds to ensure it's not picked up even if this test is slow
                    scheduled_time=pendulum.now().add(
                        seconds=worker.prefetch_seconds + 10
                    )
                ),
                worker_pool_queue_id=q2.id,
            ),
        )

        await session.commit()

        await worker.start(loops=1)

        # only the first run is picked up this time
        assert [r.flow_run.id for r in SUBMITTED_FLOW_RUNS[worker]] == [fr1.id]

    async def test_worker_heartbeat(self, session, setup):
        wp1, wp2, *_ = setup
        worker11 = MyWorker(worker_pool_name=wp1.name)
        worker12 = MyWorker(worker_pool_name=wp1.name)
        worker21 = MyWorker(worker_pool_name=wp2.name)

        assert not await models.workers.read_workers(
            session=session, worker_pool_id=wp1.id
        )
        assert not await models.workers.read_workers(
            session=session, worker_pool_id=wp2.id
        )

        # run each worker
        for worker in [worker11, worker12, worker21]:
            await worker.start(loops=1)

        wp1_workers = await models.workers.read_workers(
            session=session, worker_pool_id=wp1.id
        )
        assert len(wp1_workers) == 2
        assert wp1_workers[0].name == worker12.name
        assert wp1_workers[1].name == worker11.name

        wp2_workers = await models.workers.read_workers(
            session=session, worker_pool_id=wp2.id
        )
        assert len(wp2_workers) == 1
        assert wp2_workers[0].name == worker21.name

    async def test_worker_loads_queues(self, session, setup):
        wp1, wp2, q1, q2, *_ = setup
        worker = MyWorker(worker_pool_name=wp1.name)

        # worker has not refreshed yet
        assert len(worker.worker_pool_queues) == 0

        # refresh worker to find 3 queues in the pool
        await worker.heartbeat_worker()
        assert len(worker.worker_pool_queues) == 3

        await models.workers.delete_worker_pool_queue(
            session=session, worker_pool_queue_id=q1.id
        )
        await session.commit()

        # now there are 2 queues in the pool
        await worker.heartbeat_worker()
        assert len(worker.worker_pool_queues) == 2

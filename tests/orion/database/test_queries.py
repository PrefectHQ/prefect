import pendulum
import pytest
import sqlalchemy as sa

import prefect
from prefect.orion import models, schemas
from prefect.orion.database.interface import OrionDBInterface


class TestGetRunsInQueueQuery:
    @pytest.fixture
    async def work_queue_1(self, session):
        return await models.work_queues.create_work_queue(
            session=session, work_queue=schemas.core.WorkQueue(name="q1")
        )

    @pytest.fixture
    async def work_queue_2(self, session):
        return await models.work_queues.create_work_queue(
            session=session, work_queue=schemas.core.WorkQueue(name="q2")
        )

    @pytest.fixture
    async def deployment_1(self, session, flow, work_queue_1):
        return await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="d1", flow_id=flow.id, work_queue_name=work_queue_1.name
            ),
        )

    @pytest.fixture
    async def deployment_2(self, session, flow, work_queue_1):
        return await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="d2", flow_id=flow.id, work_queue_name=work_queue_1.name
            ),
        )

    @pytest.fixture
    async def deployment_3(self, session, flow, work_queue_2):
        return await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="d3", flow_id=flow.id, work_queue_name=work_queue_2.name
            ),
        )

    @pytest.fixture
    async def fr_1(self, session, deployment_1):
        return await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                name="fr1",
                flow_id=deployment_1.flow_id,
                deployment_id=deployment_1.id,
                work_queue_name=deployment_1.work_queue_name,
                state=schemas.states.Scheduled(pendulum.now("UTC").subtract(minutes=2)),
            ),
        )

    @pytest.fixture
    async def fr_2(self, session, deployment_2):
        return await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                name="fr2",
                flow_id=deployment_2.flow_id,
                deployment_id=deployment_2.id,
                work_queue_name=deployment_2.work_queue_name,
                state=schemas.states.Scheduled(pendulum.now("UTC").subtract(minutes=1)),
            ),
        )

    @pytest.fixture
    async def fr_3(self, session, deployment_3):
        return await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                name="fr3",
                flow_id=deployment_3.flow_id,
                deployment_id=deployment_3.id,
                work_queue_name=deployment_3.work_queue_name,
                state=schemas.states.Scheduled(pendulum.now("UTC")),
            ),
        )

    @pytest.fixture(autouse=True)
    async def commit_all(self, session, fr_1, fr_2, fr_3):
        await session.commit()

    async def test_get_runs_in_queue_query(
        self, session, db, fr_1, fr_2, fr_3, work_queue_1, work_queue_2
    ):
        query = db.queries.get_scheduled_flow_runs_from_work_queues(db=db)
        result = await session.execute(query)
        runs = result.all()

        assert [r[0].id for r in runs] == [fr_1.id, fr_2.id, fr_3.id]
        assert [r.work_queue_id for r in runs] == [
            work_queue_1.id,
            work_queue_1.id,
            work_queue_2.id,
        ]

    async def test_get_runs_in_queue_query_with_scalars(
        self, session, db, fr_1, fr_2, fr_3, work_queue_1, work_queue_2
    ):
        query = db.queries.get_scheduled_flow_runs_from_work_queues(db=db)
        result = await session.execute(query)
        # will only capture the flow run object
        runs = result.scalars().unique().all()

        assert [r.id for r in runs] == [fr_1.id, fr_2.id, fr_3.id]

    async def test_get_runs_in_queue_limit(self, session, db, fr_1, fr_2, fr_3):
        query = db.queries.get_scheduled_flow_runs_from_work_queues(
            db=db, limit_per_queue=1
        )
        result = await session.execute(query)
        runs = result.all()

        assert [r[0].id for r in runs] == [fr_1.id, fr_3.id]

    async def test_get_runs_in_queue_limit_sorts_correctly(
        self, session, db, deployment_1
    ):
        """
        Tests that the query sorts by scheduled time correctly; the unit tests with a small nubmer of runs
        can return the correct order even though no sort is applied.

        https://github.com/PrefectHQ/prefect/pull/7457
        """

        # clear all runs
        await session.execute(sa.delete(db.FlowRun))

        now = pendulum.now("UTC")

        # add a bunch of runs whose physical order is the opposite of the order they should be returned in
        # in order to make it more likely (but not guaranteed!) that unsorted queries return the wrong value
        for i in range(10, -10, -1):
            await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    name="fr1",
                    flow_id=deployment_1.flow_id,
                    deployment_id=deployment_1.id,
                    work_queue_name=deployment_1.work_queue_name,
                    state=schemas.states.Scheduled(now.add(minutes=i)),
                ),
            )

        await session.commit()

        query = db.queries.get_scheduled_flow_runs_from_work_queues(
            db=db, limit_per_queue=1
        )
        result = await session.execute(query)
        runs = result.all()

        assert len(runs) == 1
        assert runs[0][0].next_scheduled_start_time == now.subtract(minutes=9)

    async def test_get_runs_in_queue_scheduled_before(
        self, session, db, fr_1, fr_2, fr_3
    ):
        query = db.queries.get_scheduled_flow_runs_from_work_queues(
            db=db, scheduled_before=pendulum.now().subtract(seconds=90)
        )
        result = await session.execute(query)
        runs = result.all()

        assert [r[0].id for r in runs] == [fr_1.id]

    async def test_get_runs_in_queue_work_queue_ids(
        self, session, db, fr_1, fr_2, fr_3, work_queue_2
    ):
        query = db.queries.get_scheduled_flow_runs_from_work_queues(
            db=db, work_queue_ids=[work_queue_2.id]
        )
        result = await session.execute(query)
        runs = result.all()

        assert [r[0].id for r in runs] == [fr_3.id]

    async def test_use_query_to_filter_deployments(
        self, session, db, fr_1, fr_2, fr_3, work_queue_2
    ):
        query = db.queries.get_scheduled_flow_runs_from_work_queues(
            db=db, work_queue_ids=[work_queue_2.id]
        )
        # join query to deployments and filter for d3
        query = query.cte("scheduled_runs_query")
        query = (
            sa.select(sa.orm.aliased(db.FlowRun, query))
            .join(db.Deployment, query.c.deployment_id == db.Deployment.id)
            .where(db.Deployment.name == "d3")
        )
        result = await session.execute(query)

        runs = result.all()

        assert [r[0].id for r in runs] == [fr_3.id]

    async def test_query_skips_locked(self, db):
        """Concurrent queries should not both receive runs"""
        if db.database_config.connection_url.startswith("sqlite"):
            pytest.skip("FOR UDPATE SKIP LOCKED is not supported on SQLite")

        query = db.queries.get_scheduled_flow_runs_from_work_queues(db=db)

        session1 = await db.session()
        session2 = await db.session()
        async with session1:
            async with session2:
                async with session1.begin():
                    async with session2.begin():
                        result1 = (await session1.execute(query)).all()
                        result2 = (await session2.execute(query)).all()

        assert len(result1) == 3
        assert len(result2) == 0


class TestGetRunsFromWorkerPoolQueueQuery:
    @pytest.fixture(autouse=True)
    async def setup(self, session, flow):

        # create three different worker configs
        wc_a = await models.workers.create_worker_pool(
            session=session,
            worker_pool=schemas.actions.WorkerPoolCreate(name="A"),
        )
        wc_b = await models.workers.create_worker_pool(
            session=session,
            worker_pool=schemas.actions.WorkerPoolCreate(name="B"),
        )
        wc_c = await models.workers.create_worker_pool(
            session=session,
            worker_pool=schemas.actions.WorkerPoolCreate(name="C"),
        )

        # create three different work queues for each config
        wq_aa = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=wc_a.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="AA"),
        )
        wq_ab = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=wc_a.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="AB"),
        )
        wq_ac = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=wc_a.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="AC"),
        )
        wq_ba = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=wc_b.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="BA"),
        )
        wq_bb = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=wc_b.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="BB"),
        )
        wq_bc = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=wc_b.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="BC"),
        )
        wq_ca = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=wc_c.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="CA"),
        )
        wq_cb = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=wc_c.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(name="CB"),
        )
        wq_cc = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=wc_c.id,
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

            # create 5 scheduled runs
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
            worker_pools=dict(wc_a=wc_a, wc_b=wc_b, wc_c=wc_c),
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

    async def test_get_all_runs(
        self, session, db: OrionDBInterface, worker_pools, worker_pool_queues
    ):
        runs = await db.queries.get_scheduled_flow_runs_from_worker_pool(
            session=session, db=db
        )
        assert len(runs) == 45

        # runs should be sorted
        assert runs == sorted(runs, key=lambda r: r.flow_run.next_scheduled_start_time)

    @pytest.mark.parametrize("limit", [100, 10, 0])
    async def test_get_all_runs_with_limit(
        self, session, db: OrionDBInterface, worker_pools, worker_pool_queues, limit
    ):
        all_runs = await db.queries.get_scheduled_flow_runs_from_worker_pool(
            session=session, db=db
        )
        runs = await db.queries.get_scheduled_flow_runs_from_worker_pool(
            session=session, db=db, limit=min(limit, 45)
        )
        assert len(runs) == min(limit, 45)

        # the returned runs should be the same as the first set from the all_runs query
        assert [r.flow_run.id for r in runs] == [
            r.flow_run.id for r in all_runs[:limit]
        ]

    async def test_get_wc_a_runs(
        self, session, db: OrionDBInterface, worker_pools, worker_pool_queues
    ):
        runs = await db.queries.get_scheduled_flow_runs_from_worker_pool(
            session=session, db=db, worker_pool_ids=[worker_pools["wc_a"].id]
        )
        assert len(runs) == 15

    async def test_get_wc_a_b_and_c_runs(
        self, session, db: OrionDBInterface, worker_pools, worker_pool_queues
    ):
        runs = await db.queries.get_scheduled_flow_runs_from_worker_pool(
            session=session,
            db=db,
            worker_pool_ids=[
                worker_pools["wc_a"].id,
                worker_pools["wc_b"].id,
                worker_pools["wc_c"].id,
            ],
        )
        assert len(runs) == 45

    async def test_get_wq_aa_runs(
        self, session, db: OrionDBInterface, worker_pools, worker_pool_queues
    ):
        runs = await db.queries.get_scheduled_flow_runs_from_worker_pool(
            session=session,
            db=db,
            worker_pool_queue_ids=[worker_pool_queues["wq_aa"].id],
        )
        assert len(runs) == 5
        assert all(
            r.worker_pool_queue_id == worker_pool_queues["wq_aa"].id for r in runs
        )

    async def test_get_wq_aa_runs_with_all_wc_also_provided(
        self, session, db: OrionDBInterface, worker_pools, worker_pool_queues
    ):
        runs = await db.queries.get_scheduled_flow_runs_from_worker_pool(
            session=session,
            db=db,
            worker_pool_ids=[
                worker_pools["wc_a"].id,
                worker_pools["wc_b"].id,
                worker_pools["wc_c"].id,
            ],
            worker_pool_queue_ids=[worker_pool_queues["wq_aa"].id],
        )
        assert len(runs) == 5
        assert all(
            r.worker_pool_queue_id == worker_pool_queues["wq_aa"].id for r in runs
        )

    async def test_get_wq_aa_runs_when_queue_is_paused(
        self, session, db: OrionDBInterface, worker_pools, worker_pool_queues
    ):
        assert await models.workers.update_worker_pool_queue(
            session=session,
            worker_pool_queue_id=worker_pool_queues["wq_aa"].id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueUpdate(is_paused=True),
        )
        runs = await db.queries.get_scheduled_flow_runs_from_worker_pool(
            session=session,
            db=db,
            worker_pool_queue_ids=[worker_pool_queues["wq_aa"].id],
        )
        assert len(runs) == 0

    async def test_get_wq_aa_runs_when_worker_is_paused(
        self, session, db: OrionDBInterface, worker_pools, worker_pool_queues
    ):
        assert await models.workers.update_worker_pool(
            session=session,
            worker_pool_id=worker_pools["wc_a"].id,
            worker_pool=schemas.actions.WorkerPoolUpdate(is_paused=True),
        )
        runs = await db.queries.get_scheduled_flow_runs_from_worker_pool(
            session=session,
            db=db,
            worker_pool_queue_ids=[worker_pool_queues["wq_aa"].id],
        )
        assert len(runs) == 0

    @pytest.mark.parametrize("concurrency_limit,expected", [(10, 5), (5, 3), (2, 0)])
    async def test_get_wq_aa_runs_when_queue_has_concurrency(
        self,
        session,
        db: OrionDBInterface,
        worker_pools,
        worker_pool_queues,
        concurrency_limit,
        expected,
    ):
        assert await models.workers.update_worker_pool_queue(
            session=session,
            worker_pool_queue_id=worker_pool_queues["wq_aa"].id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueUpdate(
                concurrency_limit=concurrency_limit
            ),
        )
        await session.commit()
        runs = await db.queries.get_scheduled_flow_runs_from_worker_pool(
            session=session,
            db=db,
            worker_pool_queue_ids=[worker_pool_queues["wq_aa"].id],
        )
        assert len(runs) == expected

    @pytest.mark.parametrize(
        "concurrency_limit,expected", [(20, 5), (10, 4), (7, 1), (2, 0)]
    )
    async def test_get_wq_aa_runs_when_worker_has_concurrency(
        self,
        session,
        db: OrionDBInterface,
        worker_pools,
        worker_pool_queues,
        concurrency_limit,
        expected,
    ):
        assert await models.workers.update_worker_pool(
            session=session,
            worker_pool_id=worker_pools["wc_a"].id,
            worker_pool=schemas.actions.WorkerPoolUpdate(
                concurrency_limit=concurrency_limit
            ),
        )
        runs = await db.queries.get_scheduled_flow_runs_from_worker_pool(
            session=session,
            db=db,
            worker_pool_queue_ids=[worker_pool_queues["wq_aa"].id],
        )
        assert len(runs) == expected

    @pytest.mark.parametrize(
        "concurrency_limit,expected", [(25, 15), (16, 10), (7, 1), (2, 0)]
    )
    async def test_get_wc_a_runs_when_worker_has_concurrency(
        self,
        session,
        db: OrionDBInterface,
        worker_pools,
        worker_pool_queues,
        concurrency_limit,
        expected,
    ):
        assert await models.workers.update_worker_pool(
            session=session,
            worker_pool_id=worker_pools["wc_a"].id,
            worker_pool=schemas.actions.WorkerPoolUpdate(
                concurrency_limit=concurrency_limit
            ),
        )
        runs = await db.queries.get_scheduled_flow_runs_from_worker_pool(
            session=session,
            db=db,
            worker_pool_ids=[worker_pools["wc_a"].id],
        )
        assert len(runs) == expected

    @pytest.mark.parametrize("limit", [100, 7, 0])
    async def test_worker_limit(
        self, session, db: OrionDBInterface, worker_pools, worker_pool_queues, limit
    ):
        runs = await db.queries.get_scheduled_flow_runs_from_worker_pool(
            session=session, db=db, worker_limit=limit
        )
        assert len(runs) == min(15, limit) * 3
        for wc in worker_pools.values():
            assert sum(1 for r in runs if r.worker_pool_id == wc.id) == min(15, limit)

    async def test_worker_limit_with_pause(
        self, session, db: OrionDBInterface, worker_pools, worker_pool_queues
    ):
        assert await models.workers.update_worker_pool(
            session=session,
            worker_pool_id=worker_pools["wc_a"].id,
            worker_pool=schemas.actions.WorkerPoolUpdate(is_paused=True),
        )

        runs = await db.queries.get_scheduled_flow_runs_from_worker_pool(
            session=session, db=db, worker_limit=7
        )

        assert len(runs) == 14
        assert sum(1 for r in runs if r.worker_pool_id == worker_pools["wc_a"].id) == 0
        assert sum(1 for r in runs if r.worker_pool_id == worker_pools["wc_b"].id) == 7
        assert sum(1 for r in runs if r.worker_pool_id == worker_pools["wc_c"].id) == 7

    @pytest.mark.parametrize("limit", [100, 3, 0])
    async def test_queue_limit(
        self, session, db: OrionDBInterface, worker_pools, worker_pool_queues, limit
    ):
        runs = await db.queries.get_scheduled_flow_runs_from_worker_pool(
            session=session, db=db, queue_limit=limit
        )
        assert len(runs) == min(5, limit) * 9
        for wq in worker_pool_queues.values():
            assert sum(1 for r in runs if r.worker_pool_queue_id == wq.id) == min(
                5, limit
            )

    async def test_queue_limit_with_pause(
        self, session, db: OrionDBInterface, worker_pools, worker_pool_queues
    ):
        assert await models.workers.update_worker_pool_queue(
            session=session,
            worker_pool_queue_id=worker_pool_queues["wq_aa"].id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueUpdate(is_paused=True),
        )
        runs = await db.queries.get_scheduled_flow_runs_from_worker_pool(
            session=session, db=db, queue_limit=3
        )
        assert len(runs) == 24
        assert (
            sum(
                1
                for r in runs
                if r.worker_pool_queue_id == worker_pool_queues["wq_aa"].id
            )
            == 0
        )

    async def test_runs_are_returned_from_queues_according_to_priority(
        self, session, db: OrionDBInterface, worker_pools, worker_pool_queues
    ):
        runs = await db.queries.get_scheduled_flow_runs_from_worker_pool(
            session=session,
            db=db,
            worker_pool_ids=[worker_pools["wc_a"].id],
            respect_queue_priorities=True,
        )

        assert len(runs) == 15

        # the first 6 results correspond to all three queues
        assert runs[0].worker_pool_queue_id == worker_pool_queues["wq_aa"].id
        assert runs[1].worker_pool_queue_id == worker_pool_queues["wq_ab"].id
        assert runs[2].worker_pool_queue_id == worker_pool_queues["wq_ac"].id
        assert runs[3].worker_pool_queue_id == worker_pool_queues["wq_aa"].id
        assert runs[4].worker_pool_queue_id == worker_pool_queues["wq_ab"].id
        assert runs[5].worker_pool_queue_id == worker_pool_queues["wq_ac"].id

        limited_runs = await db.queries.get_scheduled_flow_runs_from_worker_pool(
            session=session,
            db=db,
            worker_pool_ids=[worker_pools["wc_a"].id],
            limit=6,
            respect_queue_priorities=True,
        )

        assert len(limited_runs) == 6

        # the first 6 results now include all 5 runs from the highest-priority
        # queue (AA) and only one run from the next-priority queue (AB)
        # (note they are selected by priority but ordered by scheduled start time)
        assert limited_runs[0].worker_pool_queue_id == worker_pool_queues["wq_aa"].id
        assert limited_runs[1].worker_pool_queue_id == worker_pool_queues["wq_ab"].id
        assert limited_runs[2].worker_pool_queue_id == worker_pool_queues["wq_aa"].id
        assert limited_runs[3].worker_pool_queue_id == worker_pool_queues["wq_aa"].id
        assert limited_runs[4].worker_pool_queue_id == worker_pool_queues["wq_aa"].id
        assert limited_runs[5].worker_pool_queue_id == worker_pool_queues["wq_aa"].id

    async def test_concurrent_reads(self, db):
        """
        Concurrent queries should not both receive runs. In this case one query
        receives some runs and the other receives none because the lock is taken
        before the limit is applied.
        """
        if db.database_config.connection_url.startswith("sqlite"):
            pytest.skip("FOR UDPATE SKIP LOCKED is not supported on SQLite")

        query = db.queries.get_scheduled_flow_runs_from_work_queues(db=db)

        async with db.session_context(begin_transaction=True) as session1:
            async with db.session_context(begin_transaction=True) as session2:
                runs1 = await db.queries.get_scheduled_flow_runs_from_worker_pool(
                    session=session1, db=db, limit=35
                )
                runs2 = await db.queries.get_scheduled_flow_runs_from_worker_pool(
                    session=session2, db=db
                )

        assert len(runs1) == 35
        assert len(runs2) == 0

    async def test_concurrent_reads_with_overlap(self, db):
        """
        Concurrent queries should not both receive runs. In this case, the limit
        is applied at the same time that the lock is taken, so the first query
        sees 18 runs and the second query sees the others.
        """
        if db.database_config.connection_url.startswith("sqlite"):
            pytest.skip("FOR UDPATE SKIP LOCKED is not supported on SQLite")

        query = db.queries.get_scheduled_flow_runs_from_work_queues(db=db)

        async with db.session_context(begin_transaction=True) as session1:
            async with db.session_context(begin_transaction=True) as session2:
                runs1 = await db.queries.get_scheduled_flow_runs_from_worker_pool(
                    session=session1, db=db, queue_limit=2
                )
                runs2 = await db.queries.get_scheduled_flow_runs_from_worker_pool(
                    session=session2, db=db
                )

        assert len(runs1) == 18
        assert len(runs2) == 27

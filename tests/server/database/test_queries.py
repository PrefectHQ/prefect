from datetime import timedelta

import pytest
import sqlalchemy as sa

from prefect.server import models, schemas
from prefect.server.database import PrefectDBInterface
from prefect.types._datetime import now


class TestGetRunsInQueueQuery:
    @pytest.fixture
    async def work_queue_1(self, session):
        return await models.work_queues.create_work_queue(
            session=session, work_queue=schemas.actions.WorkQueueCreate(name="q1")
        )

    @pytest.fixture
    async def work_queue_2(self, session):
        return await models.work_queues.create_work_queue(
            session=session, work_queue=schemas.actions.WorkQueueCreate(name="q2")
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
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                name="fr1",
                flow_id=deployment_1.flow_id,
                deployment_id=deployment_1.id,
                work_queue_name=deployment_1.work_queue_name,
                state=schemas.states.Scheduled(now("UTC") - timedelta(minutes=2)),
            ),
        )
        return flow_run

    @pytest.fixture
    async def fr_2(self, session, deployment_2):
        return await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                name="fr2",
                flow_id=deployment_2.flow_id,
                deployment_id=deployment_2.id,
                work_queue_name=deployment_2.work_queue_name,
                state=schemas.states.Scheduled(now("UTC") - timedelta(minutes=1)),
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
                state=schemas.states.Scheduled(now("UTC")),
            ),
        )

    @pytest.fixture(autouse=True)
    async def commit_all(self, session, fr_1, fr_2, fr_3):
        await session.commit()

    async def test_get_runs_in_queue_query(
        self, session, db, fr_1, fr_2, fr_3, work_queue_1, work_queue_2
    ):
        query = db.queries.get_scheduled_flow_runs_from_work_queues()
        result = await session.execute(query)
        runs = result.all()

        assert [r[0].id for r in runs] == [fr_1.id, fr_2.id, fr_3.id]
        assert [r.wq_id for r in runs] == [
            work_queue_1.id,
            work_queue_1.id,
            work_queue_2.id,
        ]

    async def test_get_runs_in_queue_query_with_scalars(
        self, session, db, fr_1, fr_2, fr_3, work_queue_1, work_queue_2
    ):
        query = db.queries.get_scheduled_flow_runs_from_work_queues()
        result = await session.execute(query)
        # will only capture the flow run object
        runs = result.scalars().unique().all()

        assert [r.id for r in runs] == [fr_1.id, fr_2.id, fr_3.id]

    async def test_get_runs_in_queue_limit(self, session, db, fr_1, fr_2, fr_3):
        query = db.queries.get_scheduled_flow_runs_from_work_queues(limit_per_queue=1)
        result = await session.execute(query)
        runs = result.all()

        assert [r[0].id for r in runs] == [fr_1.id, fr_3.id]

    async def test_get_runs_in_queue_limit_sorts_correctly(
        self, session, db, deployment_1
    ):
        """
        Tests that the query sorts by scheduled time correctly; the unit tests with a small number of runs
        can return the correct order even though no sort is applied.

        https://github.com/PrefectHQ/prefect/pull/7457
        """

        # clear all runs
        await session.execute(sa.delete(db.FlowRun))

        right_now = now("UTC")

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
                    state=schemas.states.Scheduled(right_now + timedelta(minutes=i)),
                ),
            )

        await session.commit()

        query = db.queries.get_scheduled_flow_runs_from_work_queues(limit_per_queue=1)
        result = await session.execute(query)
        runs = result.all()

        assert len(runs) == 1
        assert runs[0][0].next_scheduled_start_time == right_now - timedelta(minutes=9)

    async def test_get_runs_in_queue_scheduled_before(
        self, session, db, fr_1, fr_2, fr_3
    ):
        query = db.queries.get_scheduled_flow_runs_from_work_queues(
            scheduled_before=now("UTC") - timedelta(seconds=90)
        )
        result = await session.execute(query)
        runs = result.all()

        assert [r[0].id for r in runs] == [fr_1.id]

    async def test_get_runs_in_queue_work_queue_ids(
        self, session, db, fr_1, fr_2, fr_3, work_queue_2
    ):
        query = db.queries.get_scheduled_flow_runs_from_work_queues(
            work_queue_ids=[work_queue_2.id]
        )
        result = await session.execute(query)
        runs = result.all()

        assert [r[0].id for r in runs] == [fr_3.id]

    async def test_use_query_to_filter_deployments(
        self, session, db, fr_1, fr_2, fr_3, work_queue_2
    ):
        query = db.queries.get_scheduled_flow_runs_from_work_queues(
            work_queue_ids=[work_queue_2.id]
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
            pytest.skip("FOR UPDATE SKIP LOCKED is not supported on SQLite")

        query = db.queries.get_scheduled_flow_runs_from_work_queues()

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


class TestGetRunsFromWorkQueueQuery:
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
                    state=schemas.states.Running().model_dump(
                        exclude={"created", "updated"}
                    ),
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

            # create 5 scheduled runs from two hours ago to three hours in the future
            # we insert them in reverse order to ensure that sorting is taking
            # place (and not just returning the database order)
            for i in range(3, -2, -1):
                await models.flow_runs.create_flow_run(
                    session=session,
                    flow_run=schemas.core.FlowRun(
                        flow_id=flow.id,
                        state=schemas.states.Scheduled(
                            scheduled_time=now("UTC") + timedelta(hours=i)
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

    async def test_get_all_runs(
        self, session, db: PrefectDBInterface, work_pools, work_queues
    ):
        runs = await db.queries.get_scheduled_flow_runs_from_work_pool(session=session)
        assert len(runs) == 45

        # runs should be sorted
        assert runs == sorted(runs, key=lambda r: r.flow_run.next_scheduled_start_time)

    @pytest.mark.parametrize("limit", [100, 10, 0])
    async def test_get_all_runs_with_limit(
        self, session, db: PrefectDBInterface, work_pools, work_queues, limit
    ):
        all_runs = await db.queries.get_scheduled_flow_runs_from_work_pool(
            session=session
        )
        runs = await db.queries.get_scheduled_flow_runs_from_work_pool(
            session=session, limit=min(limit, 45)
        )
        assert len(runs) == min(limit, 45)

        # the returned runs should be the same as the first set from the all_runs query
        assert [r.flow_run.id for r in runs] == [
            r.flow_run.id for r in all_runs[:limit]
        ]

    async def test_get_wc_a_runs(
        self, session, db: PrefectDBInterface, work_pools, work_queues
    ):
        runs = await db.queries.get_scheduled_flow_runs_from_work_pool(
            session=session, work_pool_ids=[work_pools["wp_a"].id]
        )
        assert len(runs) == 15

    async def test_get_wc_a_b_and_c_runs(
        self, session, db: PrefectDBInterface, work_pools, work_queues
    ):
        runs = await db.queries.get_scheduled_flow_runs_from_work_pool(
            session=session,
            work_pool_ids=[
                work_pools["wp_a"].id,
                work_pools["wp_b"].id,
                work_pools["wp_c"].id,
            ],
        )
        assert len(runs) == 45

    async def test_get_wq_aa_runs(
        self, session, db: PrefectDBInterface, work_pools, work_queues
    ):
        runs = await db.queries.get_scheduled_flow_runs_from_work_pool(
            session=session,
            work_queue_ids=[work_queues["wq_aa"].id],
        )
        assert len(runs) == 5
        assert all(r.work_queue_id == work_queues["wq_aa"].id for r in runs)

    async def test_get_wq_aa_runs_with_all_wc_also_provided(
        self, session, db: PrefectDBInterface, work_pools, work_queues
    ):
        runs = await db.queries.get_scheduled_flow_runs_from_work_pool(
            session=session,
            work_pool_ids=[
                work_pools["wp_a"].id,
                work_pools["wp_b"].id,
                work_pools["wp_c"].id,
            ],
            work_queue_ids=[work_queues["wq_aa"].id],
        )
        assert len(runs) == 5
        assert all(r.work_queue_id == work_queues["wq_aa"].id for r in runs)

    async def test_get_wq_aa_runs_when_queue_is_paused(
        self, session, db: PrefectDBInterface, work_pools, work_queues
    ):
        assert await models.workers.update_work_queue(
            session=session,
            work_queue_id=work_queues["wq_aa"].id,
            work_queue=schemas.actions.WorkQueueUpdate(is_paused=True),
        )
        runs = await db.queries.get_scheduled_flow_runs_from_work_pool(
            session=session,
            work_queue_ids=[work_queues["wq_aa"].id],
        )
        assert len(runs) == 0

    async def test_get_wq_aa_runs_when_worker_is_paused(
        self, session, db: PrefectDBInterface, work_pools, work_queues
    ):
        assert await models.workers.update_work_pool(
            session=session,
            work_pool_id=work_pools["wp_a"].id,
            work_pool=schemas.actions.WorkPoolUpdate(is_paused=True),
            emit_status_change=None,
        )
        runs = await db.queries.get_scheduled_flow_runs_from_work_pool(
            session=session,
            work_queue_ids=[work_queues["wq_aa"].id],
        )
        assert len(runs) == 0

    @pytest.mark.parametrize("concurrency_limit,expected", [(10, 5), (5, 3), (2, 0)])
    async def test_get_wq_aa_runs_when_queue_has_concurrency(
        self,
        session,
        db: PrefectDBInterface,
        work_pools,
        work_queues,
        concurrency_limit,
        expected,
    ):
        assert await models.workers.update_work_queue(
            session=session,
            work_queue_id=work_queues["wq_aa"].id,
            work_queue=schemas.actions.WorkQueueUpdate(
                concurrency_limit=concurrency_limit
            ),
        )
        await session.commit()
        runs = await db.queries.get_scheduled_flow_runs_from_work_pool(
            session=session,
            work_queue_ids=[work_queues["wq_aa"].id],
        )
        assert len(runs) == expected

    @pytest.mark.parametrize(
        "concurrency_limit,expected", [(20, 5), (10, 4), (7, 1), (2, 0)]
    )
    async def test_get_wq_aa_runs_when_worker_has_concurrency(
        self,
        session,
        db: PrefectDBInterface,
        work_pools,
        work_queues,
        concurrency_limit,
        expected,
    ):
        assert await models.workers.update_work_pool(
            session=session,
            work_pool_id=work_pools["wp_a"].id,
            work_pool=schemas.actions.WorkPoolUpdate(
                concurrency_limit=concurrency_limit
            ),
            emit_status_change=None,
        )
        runs = await db.queries.get_scheduled_flow_runs_from_work_pool(
            session=session,
            work_queue_ids=[work_queues["wq_aa"].id],
        )
        assert len(runs) == expected

    @pytest.mark.parametrize(
        "concurrency_limit,expected", [(25, 15), (16, 10), (7, 1), (2, 0)]
    )
    async def test_get_wc_a_runs_when_worker_has_concurrency(
        self,
        session,
        db: PrefectDBInterface,
        work_pools,
        work_queues,
        concurrency_limit,
        expected,
    ):
        assert await models.workers.update_work_pool(
            session=session,
            work_pool_id=work_pools["wp_a"].id,
            work_pool=schemas.actions.WorkPoolUpdate(
                concurrency_limit=concurrency_limit
            ),
            emit_status_change=None,
        )
        runs = await db.queries.get_scheduled_flow_runs_from_work_pool(
            session=session,
            work_pool_ids=[work_pools["wp_a"].id],
        )
        assert len(runs) == expected

    @pytest.mark.parametrize("limit", [100, 7, 0])
    async def test_worker_limit(
        self, session, db: PrefectDBInterface, work_pools, work_queues, limit
    ):
        runs = await db.queries.get_scheduled_flow_runs_from_work_pool(
            session=session, worker_limit=limit
        )
        assert len(runs) == min(15, limit) * 3
        for wc in work_pools.values():
            assert sum(1 for r in runs if r.work_pool_id == wc.id) == min(15, limit)

    async def test_worker_limit_with_pause(
        self, session, db: PrefectDBInterface, work_pools, work_queues
    ):
        assert await models.workers.update_work_pool(
            session=session,
            work_pool_id=work_pools["wp_a"].id,
            work_pool=schemas.actions.WorkPoolUpdate(is_paused=True),
            emit_status_change=None,
        )

        runs = await db.queries.get_scheduled_flow_runs_from_work_pool(
            session=session, worker_limit=7
        )

        assert len(runs) == 14
        assert sum(1 for r in runs if r.work_pool_id == work_pools["wp_a"].id) == 0
        assert sum(1 for r in runs if r.work_pool_id == work_pools["wp_b"].id) == 7
        assert sum(1 for r in runs if r.work_pool_id == work_pools["wp_c"].id) == 7

    @pytest.mark.parametrize("limit", [100, 3, 0])
    async def test_queue_limit(
        self, session, db: PrefectDBInterface, work_pools, work_queues, limit
    ):
        runs = await db.queries.get_scheduled_flow_runs_from_work_pool(
            session=session, queue_limit=limit
        )
        assert len(runs) == min(5, limit) * 9
        for wq in work_queues.values():
            assert sum(1 for r in runs if r.work_queue_id == wq.id) == min(5, limit)

    async def test_queue_limit_with_pause(
        self, session, db: PrefectDBInterface, work_pools, work_queues
    ):
        assert await models.workers.update_work_queue(
            session=session,
            work_queue_id=work_queues["wq_aa"].id,
            work_queue=schemas.actions.WorkQueueUpdate(is_paused=True),
        )
        runs = await db.queries.get_scheduled_flow_runs_from_work_pool(
            session=session, queue_limit=3
        )
        assert len(runs) == 24
        assert sum(1 for r in runs if r.work_queue_id == work_queues["wq_aa"].id) == 0

    # test both default and explicit False
    @pytest.mark.parametrize("respect_priorities", [False, None])
    async def test_runs_are_returned_from_queues_ignoring_priority(
        self,
        session,
        db: PrefectDBInterface,
        work_pools,
        work_queues,
        respect_priorities,
    ):
        wq_aa, wq_ab, wq_ac = (
            work_queues["wq_aa"],
            work_queues["wq_ab"],
            work_queues["wq_ac"],
        )

        runs = await db.queries.get_scheduled_flow_runs_from_work_pool(
            session=session,
            work_pool_ids=[work_pools["wp_a"].id],
            respect_queue_priorities=respect_priorities,
        )

        assert len(runs) == 15

        # first 3 runs are from all three queues
        assert all(
            [r.work_queue_id in (wq_aa.id, wq_ab.id, wq_ac.id) for r in runs[:3]]
        )
        # runs are in time order
        assert sorted(runs, key=lambda r: r.flow_run.next_scheduled_start_time) == runs

    async def test_runs_are_returned_from_queues_according_to_priority(
        self, session, db: PrefectDBInterface, work_pools, work_queues
    ):
        wq_aa, wq_ab, wq_ac = (
            work_queues["wq_aa"],
            work_queues["wq_ab"],
            work_queues["wq_ac"],
        )

        runs = await db.queries.get_scheduled_flow_runs_from_work_pool(
            session=session,
            work_pool_ids=[work_pools["wp_a"].id],
            respect_queue_priorities=True,
        )

        assert len(runs) == 15

        # first 5 runs are from wq_aa
        assert all([r.work_queue_id == wq_aa.id for r in runs[:5]])
        # next 5 runs are from wq_ab
        assert all([r.work_queue_id == wq_ab.id for r in runs[5:10]])
        # next 5 runs are from wq_ac
        assert all([r.work_queue_id == wq_ac.id for r in runs[10:15]])

        # runs are not in time order
        assert sorted(runs, key=lambda r: r.flow_run.next_scheduled_start_time) != runs

    async def test_runs_are_returned_from_queues_according_to_priority_across_multiple_pools(
        self, session, db: PrefectDBInterface, work_pools, work_queues
    ):
        wq_aa, wq_ab, wq_ac, wq_ba, wq_bb, wq_bc = (
            work_queues["wq_aa"],
            work_queues["wq_ab"],
            work_queues["wq_ac"],
            work_queues["wq_ba"],
            work_queues["wq_bb"],
            work_queues["wq_bc"],
        )

        runs = await db.queries.get_scheduled_flow_runs_from_work_pool(
            session=session,
            work_pool_ids=[work_pools["wp_a"].id, work_pools["wp_b"].id],
            respect_queue_priorities=True,
        )

        assert len(runs) == 30

        # first 10 runs are from wq_aa or wq_ba
        assert all([r.work_queue_id in (wq_aa.id, wq_ba.id) for r in runs[:10]])
        # next 10 runs are from wq_ab or wq_bb
        assert all([r.work_queue_id in (wq_ab.id, wq_bb.id) for r in runs[10:20]])
        # next 10 runs are from wq_ac or wq_bc
        assert all([r.work_queue_id in (wq_ac.id, wq_bc.id) for r in runs[20:30]])

        # runs are not in time order
        assert sorted(runs, key=lambda r: r.flow_run.next_scheduled_start_time) != runs

    async def test_concurrent_reads(self, db: PrefectDBInterface):
        """
        Concurrent queries should not both receive runs. In this case one query
        receives some runs and the other receives none because the lock is taken
        before the limit is applied.
        """
        if db.database_config.connection_url.startswith("sqlite"):
            pytest.skip("FOR UPDATE SKIP LOCKED is not supported on SQLite")

        db.queries.get_scheduled_flow_runs_from_work_queues()

        async with db.session_context(begin_transaction=True) as session1:
            async with db.session_context(begin_transaction=True) as session2:
                runs1 = await db.queries.get_scheduled_flow_runs_from_work_pool(
                    session=session1, limit=35
                )
                runs2 = await db.queries.get_scheduled_flow_runs_from_work_pool(
                    session=session2
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
            pytest.skip("FOR UPDATE SKIP LOCKED is not supported on SQLite")

        db.queries.get_scheduled_flow_runs_from_work_queues()

        async with db.session_context(begin_transaction=True) as session1:
            async with db.session_context(begin_transaction=True) as session2:
                runs1 = await db.queries.get_scheduled_flow_runs_from_work_pool(
                    session=session1, queue_limit=2
                )
                runs2 = await db.queries.get_scheduled_flow_runs_from_work_pool(
                    session=session2
                )

        assert len(runs1) == 18
        assert len(runs2) == 27

    @pytest.mark.parametrize(
        "hours,expected", [(100, 45), (3, 45), (1, 27), (-1, 9), (-10, 0)]
    )
    async def test_scheduled_before(
        self, session, db: PrefectDBInterface, hours, expected
    ):
        runs = await db.queries.get_scheduled_flow_runs_from_work_pool(
            session=session,
            scheduled_before=now("UTC") + timedelta(hours=hours),
        )
        assert len(runs) == expected

    @pytest.mark.parametrize(
        "hours,expected", [(-100, 45), (-3, 45), (0, 27), (2, 9), (10, 0)]
    )
    async def test_scheduled_after(
        self, session, db: PrefectDBInterface, hours, expected
    ):
        runs = await db.queries.get_scheduled_flow_runs_from_work_pool(
            session=session,
            scheduled_after=now("UTC") + timedelta(hours=hours),
        )
        assert len(runs) == expected

    async def test_scheduled_before_and_after(self, session, db: PrefectDBInterface):
        runs = await db.queries.get_scheduled_flow_runs_from_work_pool(
            session=session,
            # criteria should match no runs
            scheduled_before=now("UTC") - timedelta(hours=1),
            scheduled_after=now("UTC") + timedelta(hours=1),
        )
        assert len(runs) == 0

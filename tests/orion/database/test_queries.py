import pendulum
import pytest
import sqlalchemy as sa

from prefect.orion import models, schemas


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

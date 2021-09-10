from prefect.orion.utilities.database import Base, get_session_factory
import pendulum
import pytest

from prefect.orion import models
from prefect.orion.schemas import core, filters, states


@pytest.fixture(autouse=True, scope="module")
async def clear_db():
    """Prevent automatic database-clearing behavior after every test"""
    pass


@pytest.fixture(autouse=True, scope="module")
async def create_flows(database_engine):

    session_factory = await get_session_factory(bind=database_engine)
    async with session_factory() as session:

        create_flow = lambda flow: models.flows.create_flow(session=session, flow=flow)
        create_flow_run = lambda flow_run: models.flow_runs.create_flow_run(
            session=session, flow_run=flow_run
        )
        create_task_run = lambda task_run: models.task_runs.create_task_run(
            session=session, task_run=task_run
        )

        flow_1 = await create_flow(
            flow=core.Flow(name="my-flow-1", tags=["db", "blue"])
        )
        flow_2 = await create_flow(flow=core.Flow(name="my-flow-2", tags=["db"]))
        flow_3 = await create_flow(flow=core.Flow(name="my-flow-3"))

        # ---- flow 1

        fr_1_1 = await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=flow_1.id,
                tags=["db", "blue"],
                state=states.Completed(),
            )
        )

        fr_1_2 = await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=flow_1.id,
                tags=["db", "blue"],
                state=states.Completed(),
            )
        )
        fr_1_3 = await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=flow_1.id,
                tags=["db", "red"],
                state=states.Failed(),
            )
        )
        fr_1_4 = await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=flow_1.id,
                tags=["red"],
                state=states.Running(),
            )
        )
        fr_1_5 = await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=flow_1.id,
                state=states.Running(),
            )
        )

        # ---- flow 2

        fr_2_1 = await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=flow_2.id,
                tags=["db", "blue"],
                state=states.Completed(),
            )
        )

        fr_2_2 = await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=flow_2.id,
                tags=["red"],
                state=states.Running(),
            )
        )
        fr_2_3 = await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=flow_2.id,
                tags=["db", "red"],
                state=states.Failed(),
            )
        )

        # ---- flow 3

        fr_3_1 = await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=flow_3.id,
                tags=[],
                state=states.Completed(),
            )
        )

        fr_3_2 = await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=flow_3.id,
                tags=["db", "red"],
                state=states.Scheduled(scheduled_time=pendulum.now()),
            )
        )

        # --- task runs

        await create_task_run(
            task_run=core.TaskRun(
                flow_run_id=fr_1_1.id,
                task_key="a",
                state=states.Running(),
            )
        )
        await create_task_run(
            task_run=core.TaskRun(
                flow_run_id=fr_1_1.id,
                task_key="b",
                state=states.Completed(),
            )
        )
        await create_task_run(
            task_run=core.TaskRun(
                flow_run_id=fr_1_1.id,
                task_key="c",
                state=states.Completed(),
            )
        )

        await create_task_run(
            task_run=core.TaskRun(
                flow_run_id=fr_2_2.id,
                task_key="a",
                state=states.Running(),
            )
        )
        await create_task_run(
            task_run=core.TaskRun(
                flow_run_id=fr_2_2.id,
                task_key="b",
                state=states.Completed(),
            )
        )
        await create_task_run(
            task_run=core.TaskRun(
                flow_run_id=fr_2_2.id,
                task_key="c",
                state=states.Completed(),
            )
        )

        await create_task_run(
            task_run=core.TaskRun(
                flow_run_id=fr_3_1.id,
                task_key="a",
                state=states.Failed(),
            )
        )
        await session.commit()

        yield

    # clear data
    async with database_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


class TestCountFlows:
    async def test_count_flows(self, session):
        count = await models.flows.count_flows(session=session)
        assert count == 3

    async def test_count_flows_with_name_filter(self, session):
        count = await models.flows.count_flows(
            session=session,
            flow_filter=filters.FlowFilter(names=["my-flow-1", "my-flow-2"]),
        )
        assert count == 2

        count = await models.flows.count_flows(
            session=session,
            flow_filter=filters.FlowFilter(names=["my-flow-1", "my-flow-100"]),
        )
        assert count == 1

        count = await models.flows.count_flows(
            session=session, flow_filter=filters.FlowFilter(names=["my-flow-1"])
        )
        assert count == 1

    async def test_count_flows_with_tag_filter(self, session):
        count = await models.flows.count_flows(
            session=session, flow_filter=filters.FlowFilter(tags_all=["db"])
        )
        assert count == 2

        count = await models.flows.count_flows(
            session=session,
            flow_filter=filters.FlowFilter(tags_all=["db", "blue"]),
        )
        assert count == 1

        count = await models.flows.count_flows(
            session=session,
            flow_filter=filters.FlowFilter(tags_all=["db", "red"]),
        )
        assert count == 0

    async def test_count_flows_with_flow_run_tag_filter(self, session):
        count = await models.flows.count_flows(
            session=session,
            flow_run_filter=filters.FlowRunFilter(tags_all=["db", "red"]),
        )
        assert count == 3

        count = await models.flows.count_flows(
            session=session,
            flow_run_filter=filters.FlowRunFilter(tags_all=["db", "blue"]),
        )
        assert count == 2

        count = await models.flows.count_flows(
            session=session,
            flow_run_filter=filters.FlowRunFilter(tags_all=[]),
        )
        assert count == 2

    async def test_count_flows_with_flow_run_and_task_run_filters_applies_both(
        self, session
    ):
        """Ensures that flow run and task run filters are combined, not taken independently"""
        count = await models.flows.count_flows(
            session=session, task_run_filter=filters.TaskRunFilter(states=["FAILED"])
        )
        assert count == 1

        count = await models.flows.count_flows(
            session=session,
            flow_run_filter=filters.FlowRunFilter(tags_all=["xyz"]),
            task_run_filter=filters.TaskRunFilter(states=["FAILED"]),
        )
        assert count == 0


class TestCountFlowRun:
    async def test_count_flow_runs(self, session):
        count = await models.flow_runs.count_flow_runs(session=session)
        assert count == 10

    async def test_count_flow_runs_with_flow_name_filter(self, session):
        count = await models.flow_runs.count_flow_runs(
            session=session,
            flow_filter=filters.FlowFilter(names=["my-flow-1", "my-flow-2"]),
        )
        assert count == 8

        count = await models.flow_runs.count_flow_runs(
            session=session,
            flow_filter=filters.FlowFilter(names=["my-flow-1", "my-flow-100"]),
        )
        assert count == 5

        count = await models.flow_runs.count_flow_runs(
            session=session, flow_filter=filters.FlowFilter(names=["my-flow-1"])
        )
        assert count == 5

    async def test_count_flow_runs_with_flow_tag_filter(self, session):
        count = await models.flow_runs.count_flow_runs(
            session=session, flow_filter=filters.FlowFilter(tags_all=["db"])
        )
        assert count == 8

        count = await models.flow_runs.count_flow_runs(
            session=session,
            flow_filter=filters.FlowFilter(tags_all=["db", "blue"]),
        )
        assert count == 5

        count = await models.flow_runs.count_flow_runs(
            session=session,
            flow_filter=filters.FlowFilter(tags_all=["db", "red"]),
        )
        assert count == 0

    async def test_count_flow_runs_with_flow_run_tag_filter(self, session):
        count = await models.flow_runs.count_flow_runs(
            session=session,
            flow_run_filter=filters.FlowRunFilter(tags_all=["db", "red"]),
        )
        assert count == 3

        count = await models.flow_runs.count_flow_runs(
            session=session,
            flow_run_filter=filters.FlowRunFilter(tags_all=["db", "blue"]),
        )
        assert count == 3

        count = await models.flow_runs.count_flow_runs(
            session=session,
            flow_run_filter=filters.FlowRunFilter(tags_all=[]),
        )
        assert count == 2

    async def test_count_flow_runs_with_flows_and_task_filters(self, session):
        """Ensures that flow and task run filters are combined, not taken independently"""
        count = await models.flow_runs.count_flow_runs(
            session=session, task_run_filter=filters.TaskRunFilter(states=["FAILED"])
        )
        assert count == 1

        count = await models.flow_runs.count_flow_runs(
            session=session,
            flow_filter=filters.FlowFilter(tags_all=["xyz"]),
            task_run_filter=filters.TaskRunFilter(states=["FAILED"]),
        )
        assert count == 0


class TestCountTaskRuns:
    async def test_count_task_runs(self, session):
        count = await models.task_runs.count_task_runs(session=session)
        assert count == 7

    async def test_count_task_runs_with_name_filter(self, session):
        count = await models.task_runs.count_task_runs(
            session=session,
            flow_filter=filters.FlowFilter(names=["my-flow-1", "my-flow-2"]),
        )
        assert count == 6

        count = await models.task_runs.count_task_runs(
            session=session,
            flow_filter=filters.FlowFilter(names=["my-flow-1", "my-flow-100"]),
        )
        assert count == 3

        count = await models.task_runs.count_task_runs(
            session=session, flow_filter=filters.FlowFilter(names=["my-flow-1"])
        )
        assert count == 3

    async def test_count_task_runs_with_tag_filter(self, session):
        count = await models.task_runs.count_task_runs(
            session=session, flow_filter=filters.FlowFilter(tags_all=["db"])
        )
        assert count == 6

        count = await models.task_runs.count_task_runs(
            session=session,
            flow_filter=filters.FlowFilter(tags_all=["db", "blue"]),
        )
        assert count == 3

        count = await models.task_runs.count_task_runs(
            session=session,
            flow_filter=filters.FlowFilter(tags_all=["db", "red"]),
        )
        assert count == 0

    async def test_count_task_runs_with_flow_run_tag_filter(self, session):
        count = await models.task_runs.count_task_runs(
            session=session,
            flow_run_filter=filters.FlowRunFilter(tags_all=["db", "red"]),
        )
        assert count == 0

        count = await models.task_runs.count_task_runs(
            session=session,
            flow_run_filter=filters.FlowRunFilter(tags_all=["db", "blue"]),
        )
        assert count == 3

        count = await models.task_runs.count_task_runs(
            session=session,
            flow_run_filter=filters.FlowRunFilter(tags_all=[]),
        )
        assert count == 1

    async def test_count_task_runs_with_flow_run_and_flow_filters_applies_both(
        self, session
    ):
        """Ensures that flow and flow run filters are combined, not taken independently"""
        count = await models.task_runs.count_task_runs(
            session=session, flow_run_filter=filters.FlowRunFilter(states=["COMPLETED"])
        )
        assert count == 4

        count = await models.task_runs.count_task_runs(
            session=session,
            flow_filter=filters.FlowFilter(tags_all=["xyz"]),
            flow_run_filter=filters.FlowRunFilter(states=["COMPLETED"]),
        )
        assert count == 0

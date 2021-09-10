import pydantic
import json
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


class TestCountFlowsModels:

    params = [
        [{}, 3],
        [dict(flow_filter=filters.FlowFilter(names=["my-flow-1", "my-flow-2"])), 2],
        [dict(flow_filter=filters.FlowFilter(names=["my-flow-1", "my-flow-100"])), 1],
        [dict(flow_filter=filters.FlowFilter(names=["my-flow-1"])), 1],
        [dict(flow_filter=filters.FlowFilter(tags_all=["db"])), 2],
        [dict(flow_filter=filters.FlowFilter(tags_all=["db", "blue"])), 1],
        [dict(flow_filter=filters.FlowFilter(tags_all=["db", "red"])), 0],
        [dict(flow_run_filter=filters.FlowRunFilter(tags_all=["db", "red"])), 3],
        [dict(flow_run_filter=filters.FlowRunFilter(tags_all=["db", "blue"])), 2],
        # possibly odd behavior
        [dict(flow_run_filter=filters.FlowRunFilter(tags_all=[])), 2],
        # next two check that filters are applied as an intersection not a union
        [dict(task_run_filter=filters.TaskRunFilter(states=["FAILED"])), 1],
        [
            dict(
                task_run_filter=filters.TaskRunFilter(states=["FAILED"]),
                flow_run_filter=filters.FlowRunFilter(tags_all=["xyz"]),
            ),
            0,
        ],
    ]

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_models_count(self, session, kwargs, expected):
        count = await models.flows.count_flows(session=session, **kwargs)
        assert count == expected

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_api_count(self, client, kwargs, expected):
        adjusted_kwargs = {}
        for k, v in kwargs.items():
            if k == "flow_filter":
                k = "flows"
            elif k == "flow_run_filter":
                k = "flow_runs"
            elif k == "task_run_filter":
                k = "task_runs"
            adjusted_kwargs[k] = v

        repsonse = await client.get(
            "/flows/count",
            json=json.loads(
                json.dumps(
                    adjusted_kwargs,
                    default=pydantic.json.pydantic_encoder,
                )
            ),
        )
        assert repsonse.json() == expected


class TestCountFlowRunModels:

    params = [
        [{}, 10],
        [dict(flow_filter=filters.FlowFilter(names=["my-flow-1", "my-flow-2"])), 8],
        [dict(flow_filter=filters.FlowFilter(names=["my-flow-1", "my-flow-100"])), 5],
        [dict(flow_filter=filters.FlowFilter(names=["my-flow-1"])), 5],
        [dict(flow_filter=filters.FlowFilter(tags_all=["db"])), 8],
        [dict(flow_filter=filters.FlowFilter(tags_all=["db", "blue"])), 5],
        [dict(flow_filter=filters.FlowFilter(tags_all=["db", "red"])), 0],
        [dict(flow_run_filter=filters.FlowRunFilter(tags_all=["db", "red"])), 3],
        [dict(flow_run_filter=filters.FlowRunFilter(tags_all=["db", "blue"])), 3],
        # possibly odd behavior
        [dict(flow_run_filter=filters.FlowRunFilter(tags_all=[])), 2],
        # next two check that filters are applied as an intersection not a union
        [dict(task_run_filter=filters.TaskRunFilter(states=["FAILED"])), 1],
        [
            dict(
                task_run_filter=filters.TaskRunFilter(states=["FAILED"]),
                flow_filter=filters.FlowFilter(tags_all=["xyz"]),
            ),
            0,
        ],
    ]

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_models_count(self, session, kwargs, expected):
        count = await models.flow_runs.count_flow_runs(session=session, **kwargs)
        assert count == expected

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_api_count(self, client, kwargs, expected):
        adjusted_kwargs = {}
        for k, v in kwargs.items():
            if k == "flow_filter":
                k = "flows"
            elif k == "flow_run_filter":
                k = "flow_runs"
            elif k == "task_run_filter":
                k = "task_runs"
            adjusted_kwargs[k] = v

        repsonse = await client.get(
            "/flow_runs/count",
            json=json.loads(
                json.dumps(adjusted_kwargs, default=pydantic.json.pydantic_encoder)
            ),
        )
        assert repsonse.json() == expected


class TestCountTaskRunsModels:

    params = [
        [{}, 7],
        [dict(flow_filter=filters.FlowFilter(names=["my-flow-1", "my-flow-2"])), 6],
        [dict(flow_filter=filters.FlowFilter(names=["my-flow-1", "my-flow-100"])), 3],
        [dict(flow_filter=filters.FlowFilter(names=["my-flow-1"])), 3],
        [dict(flow_filter=filters.FlowFilter(tags_all=["db"])), 6],
        [dict(flow_filter=filters.FlowFilter(tags_all=["db", "blue"])), 3],
        [dict(flow_filter=filters.FlowFilter(tags_all=["db", "red"])), 0],
        [dict(flow_run_filter=filters.FlowRunFilter(tags_all=["db", "red"])), 0],
        [dict(flow_run_filter=filters.FlowRunFilter(tags_all=["db", "blue"])), 3],
        # possibly odd behavior
        [dict(flow_run_filter=filters.FlowRunFilter(tags_all=[])), 1],
        # next two check that filters are applied as an intersection not a union
        [dict(flow_run_filter=filters.FlowRunFilter(states=["COMPLETED"])), 4],
        [
            dict(
                flow_run_filter=filters.FlowRunFilter(states=["COMPLETED"]),
                flow_filter=filters.FlowFilter(tags_all=["xyz"]),
            ),
            0,
        ],
    ]

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_models_count(self, session, kwargs, expected):
        count = await models.task_runs.count_task_runs(session=session, **kwargs)
        assert count == expected

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_api_count(self, client, kwargs, expected):
        adjusted_kwargs = {}
        for k, v in kwargs.items():
            if k == "flow_filter":
                k = "flows"
            elif k == "flow_run_filter":
                k = "flow_runs"
            elif k == "task_run_filter":
                k = "task_runs"
            adjusted_kwargs[k] = v
        repsonse = await client.get(
            "/task_runs/count",
            json=json.loads(
                json.dumps(adjusted_kwargs, default=pydantic.json.pydantic_encoder)
            ),
        )
        assert repsonse.json() == expected

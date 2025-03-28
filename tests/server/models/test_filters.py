import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from pydantic_core import from_json, to_json
from sqlalchemy.exc import InterfaceError

import prefect.server
from prefect.client.orchestration import get_client
from prefect.server import models
from prefect.server.schemas import actions, core, filters, schedules, states
from prefect.types._datetime import now


@pytest.fixture(autouse=True, scope="module")
async def clear_db(db):
    """Clear DB only once before running tests in this module."""
    max_retries = 3
    retry_delay = 1

    for attempt in range(max_retries):
        try:
            async with db.session_context(begin_transaction=True) as session:
                await session.execute(db.Agent.__table__.delete())
                await session.execute(db.WorkPool.__table__.delete())

                for table in reversed(db.Base.metadata.sorted_tables):
                    await session.execute(table.delete())
                break
        except InterfaceError:
            if attempt < max_retries - 1:
                print(
                    "Connection issue. Retrying entire deletion operation"
                    f" ({attempt + 1}/{max_retries})..."
                )
                await asyncio.sleep(retry_delay)
            else:
                raise

    yield


d_1_1_id = uuid4()
d_1_2_id = uuid4()
d_3_1_id = uuid4()


def adjust_kwargs_for_client(kwargs):
    adjusted_kwargs = {}
    for k, v in kwargs.items():
        if k == "flow_filter":
            k = "flows"
        elif k == "flow_run_filter":
            k = "flow_runs"
        elif k == "task_run_filter":
            k = "task_runs"
        elif k == "deployment_filter":
            k = "deployments"
        elif k == "work_pool_filter":
            k = "work_pools"
        elif k == "work_queue_filter":
            k = "work_pool_queues"
        else:
            raise ValueError("Unrecognized filter")
        adjusted_kwargs[k] = v
    return from_json(to_json(adjusted_kwargs))


@pytest.fixture(autouse=True, scope="module")
async def data(flow_function, db):
    # This fixture uses the prefix of `test-` whenever the value is going to be
    # used for a filter in the actual tests below ensuring that the
    # auto-generated names never conflict.

    async with db.session_context(begin_transaction=True) as session:

        def create_flow(flow):
            return models.flows.create_flow(session=session, flow=flow)

        def create_deployment(deployment):
            return models.deployments.create_deployment(
                session=session, deployment=deployment
            )

        def create_flow_run(flow_run):
            return models.flow_runs.create_flow_run(session=session, flow_run=flow_run)

        def create_task_run(task_run):
            return models.task_runs.create_task_run(session=session, task_run=task_run)

        wp = await models.workers.create_work_pool(
            session=session, work_pool=actions.WorkPoolCreate(name="Test Pool")
        )

        f_1 = await create_flow(flow=core.Flow(name="f-1", tags=["db", "blue"]))
        f_2 = await create_flow(flow=core.Flow(name="f-2", tags=["db"]))
        f_3 = await create_flow(flow=core.Flow(name="f-3"))

        # ---- deployments
        d_1_1 = await create_deployment(
            deployment=core.Deployment(
                id=d_1_1_id,
                name="d-1-1",
                flow_id=f_1.id,
                schedules=[
                    core.DeploymentSchedule(
                        schedule=schedules.IntervalSchedule(interval=timedelta(days=1))
                    )
                ],
                paused=False,
            )
        )
        d_1_2 = await create_deployment(
            deployment=core.Deployment(
                id=d_1_2_id,
                name="d-1-2",
                flow_id=f_1.id,
                paused=True,
                work_queue_name="test-queue-for-filters",
            )
        )
        d_3_1 = await create_deployment(
            deployment=core.Deployment(
                id=d_3_1_id,
                name="d-3-1",
                flow_id=f_3.id,
                schedules=[
                    core.DeploymentSchedule(
                        schedule=schedules.IntervalSchedule(interval=timedelta(days=1))
                    )
                ],
                paused=False,
                work_queue_id=wp.default_queue_id,
            )
        )

        # ---- flow 1

        fr_1_1 = await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=f_1.id,
                name="test-happy-duck",
                tags=["db", "blue"],
                state=prefect.server.schemas.states.Completed(),
                deployment_id=d_1_1.id,
            )
        )

        await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=f_1.id,
                name="sad-duck",
                tags=["db", "blue"],
                state=prefect.server.schemas.states.Completed(),
            )
        )
        await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=f_1.id,
                name="test-happy-mallard",
                tags=["db", "red"],
                state=prefect.server.schemas.states.Failed(),
                deployment_id=d_1_1.id,
            )
        )
        await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=f_1.id,
                tags=["red"],
                state=prefect.server.schemas.states.Running(),
            )
        )
        await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=f_1.id,
                state=prefect.server.schemas.states.Running(),
                deployment_id=d_1_2.id,
            )
        )

        # ---- flow 2

        await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=f_2.id,
                name="another-test-happy-duck",
                tags=["db", "blue"],
                state=prefect.server.schemas.states.Completed(),
            )
        )

        fr_2_2 = await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=f_2.id,
                name="another-sad-duck",
                tags=["red"],
                state=prefect.server.schemas.states.Running(),
            )
        )
        await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=f_2.id,
                tags=["db", "red"],
                state=prefect.server.schemas.states.Failed(),
            )
        )

        # ---- flow 3

        fr_3_1 = await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=f_3.id,
                tags=[],
                state=prefect.server.schemas.states.Completed(),
                deployment_id=d_3_1.id,
                work_queue_id=wp.default_queue_id,
            )
        )

        await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=f_3.id,
                tags=["db", "red"],
                state=prefect.server.schemas.states.Scheduled(
                    scheduled_time=now("UTC")
                ),
            )
        )

        # --- task runs

        await create_task_run(
            task_run=core.TaskRun(
                flow_run_id=fr_1_1.id,
                name="task-run-1",
                task_key="a",
                state=states.Running(),
                dynamic_key="0",
            )
        )
        await create_task_run(
            task_run=core.TaskRun(
                flow_run_id=fr_1_1.id,
                name="task-run-2",
                task_key="b",
                state=prefect.server.schemas.states.Completed(),
                dynamic_key="0",
            )
        )
        await create_task_run(
            task_run=core.TaskRun(
                name="task-run-2a",
                flow_run_id=fr_1_1.id,
                task_key="c",
                state=prefect.server.schemas.states.Completed(),
                dynamic_key="0",
            )
        )

        await create_task_run(
            task_run=core.TaskRun(
                flow_run_id=fr_2_2.id,
                task_key="a",
                state=prefect.server.schemas.states.Running(),
                dynamic_key="0",
            )
        )
        await create_task_run(
            task_run=core.TaskRun(
                flow_run_id=fr_2_2.id,
                task_key="b",
                state=prefect.server.schemas.states.Completed(),
                dynamic_key="0",
            )
        )
        await create_task_run(
            task_run=core.TaskRun(
                flow_run_id=fr_2_2.id,
                task_key="c",
                state=prefect.server.schemas.states.Completed(),
                dynamic_key="0",
            )
        )

        await create_task_run(
            task_run=core.TaskRun(
                flow_run_id=fr_3_1.id,
                task_key="a",
                state=prefect.server.schemas.states.Failed(),
                dynamic_key="0",
            )
        )

        # ----------------- create a subflow run and parent tasks
        f_4 = await create_flow(flow=core.Flow(name="f-4"))

        # create a parent flow run
        fr1 = await create_flow_run(
            flow_run=core.FlowRun(flow_id=f_4.id),
        )
        await create_task_run(
            task_run=core.TaskRun(flow_run_id=fr1.id, task_key="a", dynamic_key="0")
        )
        tr2 = await create_task_run(
            task_run=core.TaskRun(flow_run_id=fr1.id, task_key="b", dynamic_key="0")
        )

        # create a subflow corresponding to tr2
        fr2 = await create_flow_run(
            flow_run=core.FlowRun(flow_id=f_4.id, parent_task_run_id=tr2.id),
        )
        await create_task_run(
            task_run=core.TaskRun(flow_run_id=fr2.id, task_key="a", dynamic_key="0")
        )

    yield

    # ----------------- clear data

    async with db.session_context(begin_transaction=True) as session:
        # work pool has a circular dependency on pool queue; delete it first
        await session.execute(db.WorkPool.__table__.delete())

        for table in reversed(db.Base.metadata.sorted_tables):
            await session.execute(table.delete())


class TestCountFlowsModels:
    params = [
        [{}, 4],
        [dict(flow_filter=filters.FlowFilter(name=dict(any_=["f-1", "f-2"]))), 2],
        [dict(flow_filter=filters.FlowFilter(name=dict(any_=["f-1", "f-100"]))), 1],
        [dict(flow_filter=filters.FlowFilter(name=dict(any_=["f-1"]))), 1],
        [dict(flow_filter=filters.FlowFilter(name=dict(like_="f"))), 4],
        [dict(flow_filter=filters.FlowFilter(name=dict(like_="1"))), 1],
        [dict(flow_filter=filters.FlowFilter(tags=dict(all_=["db"]))), 2],
        [dict(flow_filter=filters.FlowFilter(tags=dict(all_=["db", "blue"]))), 1],
        [dict(flow_filter=filters.FlowFilter(tags=dict(all_=["db", "red"]))), 0],
        [dict(flow_run_filter=filters.FlowRunFilter(tags=dict(all_=["db", "red"]))), 3],
        [
            dict(flow_run_filter=filters.FlowRunFilter(tags=dict(all_=["db", "blue"]))),
            2,
        ],
        [dict(flow_run_filter=filters.FlowRunFilter(tags=dict(is_null_=True))), 3],
        [
            dict(flow_run_filter=filters.FlowRunFilter(name=dict(like_="test-happy"))),
            2,
        ],
        [
            dict(
                flow_run_filter=filters.FlowRunFilter(
                    name=dict(like_="test-happy-mallard")
                )
            ),
            1,
        ],
        [dict(task_run_filter=filters.TaskRunFilter(name=dict(like_="2a"))), 1],
        [dict(deployment_filter=filters.DeploymentFilter(id=dict(any_=[d_1_1_id]))), 1],
        [dict(deployment_filter=filters.DeploymentFilter(name=dict(like_="d-1"))), 1],
        # next two check that filters are applied as an intersection not a union
        [
            dict(
                task_run_filter=filters.TaskRunFilter(
                    state=dict(type=dict(any_=["FAILED"]))
                )
            ),
            1,
        ],
        [
            dict(
                task_run_filter=filters.TaskRunFilter(
                    state=dict(type=dict(any_=["FAILED"]))
                ),
                flow_run_filter=filters.FlowRunFilter(tags=dict(all_=["xyz"])),
            ),
            0,
        ],
        [
            dict(
                flow_run_filter=filters.FlowRunFilter(
                    deployment_id=dict(any_=[d_1_1_id, d_1_2_id])
                )
            ),
            1,
        ],
        [
            dict(
                flow_run_filter=filters.FlowRunFilter(
                    deployment_id=dict(any_=[d_1_1_id, d_3_1_id])
                )
            ),
            2,
        ],
        # flow that have subflows (via task attribute)
        [
            dict(
                task_run_filter=filters.TaskRunFilter(subflow_runs=dict(exists_=True))
            ),
            1,
        ],
        # flows that have subflows (via flow run attribute)
        [
            dict(
                flow_run_filter=filters.FlowRunFilter(
                    parent_task_run_id=dict(is_null_=False)
                )
            ),
            1,
        ],
        # empty filter
        [dict(flow_filter=filters.FlowFilter()), 4],
        # multiple empty filters
        [
            dict(
                flow_filter=filters.FlowFilter(),
                flow_run_filter=filters.FlowRunFilter(),
            ),
            4,
        ],
    ]

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_python_client_filter(self, kwargs, expected):
        async with get_client() as client:
            flows = await client.read_flows(**kwargs)
            assert len(flows) == expected

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_models_count(self, session, kwargs, expected):
        count = await models.flows.count_flows(session=session, **kwargs)
        assert count == expected

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_models_read(self, session, kwargs, expected):
        read = await models.flows.read_flows(session=session, **kwargs)
        assert len({r.id for r in read}) == expected

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_api_count(self, client, kwargs, expected):
        adjusted_kwargs = adjust_kwargs_for_client(kwargs)

        response = await client.post(
            "/flows/count",
            json=adjusted_kwargs,
        )
        assert response.json() == expected

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_api_read(self, client, kwargs, expected):
        adjusted_kwargs = adjust_kwargs_for_client(kwargs)

        response = await client.post(
            "/flows/filter",
            json=adjusted_kwargs,
        )
        assert len({r["id"] for r in response.json()}) == expected


class TestCountFlowRunModels:
    params = [
        [{}, 12],
        [dict(flow_filter=filters.FlowFilter(name=dict(any_=["f-1", "f-2"]))), 8],
        [dict(flow_filter=filters.FlowFilter(name=dict(any_=["f-1", "f-100"]))), 5],
        [dict(flow_filter=filters.FlowFilter(name=dict(any_=["f-1"]))), 5],
        [dict(flow_filter=filters.FlowFilter(name=dict(like_="f-"))), 12],
        [dict(flow_filter=filters.FlowFilter(tags=dict(all_=["db"]))), 8],
        [dict(flow_filter=filters.FlowFilter(tags=dict(all_=["db", "blue"]))), 5],
        [dict(flow_filter=filters.FlowFilter(tags=dict(all_=["db", "red"]))), 0],
        [dict(flow_run_filter=filters.FlowRunFilter(tags=dict(all_=["db", "red"]))), 3],
        [
            dict(flow_run_filter=filters.FlowRunFilter(tags=dict(all_=["db", "blue"]))),
            3,
        ],
        [dict(flow_run_filter=filters.FlowRunFilter(tags=dict(is_null_=True))), 4],
        [
            dict(flow_run_filter=filters.FlowRunFilter(name=dict(like_="test-happy"))),
            3,
        ],
        [
            dict(
                flow_run_filter=filters.FlowRunFilter(
                    name=dict(like_="test-happy-mallard")
                )
            ),
            1,
        ],
        [dict(task_run_filter=filters.TaskRunFilter(name=dict(like_="2a"))), 1],
        [dict(deployment_filter=filters.DeploymentFilter(id=dict(any_=[d_1_1_id]))), 2],
        [dict(deployment_filter=filters.DeploymentFilter(name=dict(like_="d_1"))), 3],
        # next two check that filters are applied as an intersection not a union
        [
            dict(
                task_run_filter=filters.TaskRunFilter(
                    state=dict(type=dict(any_=["FAILED"]))
                )
            ),
            1,
        ],
        [
            dict(
                task_run_filter=filters.TaskRunFilter(
                    state=dict(type=dict(any_=["FAILED"]))
                ),
                flow_filter=filters.FlowFilter(tags=dict(all_=["xyz"])),
            ),
            0,
        ],
        # search for completed states with "NOT-COMPLETED" as the name, should return nothing
        [
            dict(
                flow_run_filter=filters.FlowRunFilter(
                    state=dict(
                        type=dict(any_=["COMPLETED"]), name=dict(any_=["NOT-COMPLETED"])
                    )
                )
            ),
            0,
        ],
        [
            dict(
                flow_run_filter=filters.FlowRunFilter(
                    state=dict(name=dict(any_=["Completed"]))
                )
            ),
            4,
        ],
        [
            dict(
                flow_run_filter=filters.FlowRunFilter(
                    state=dict(name=dict(any_=["Failed"]))
                )
            ),
            2,
        ],
        [
            dict(
                flow_run_filter=filters.FlowRunFilter(
                    state=dict(name=dict(any_=["Failed", "Completed"]))
                )
            ),
            6,
        ],
        [
            dict(
                flow_run_filter=filters.FlowRunFilter(
                    state=dict(
                        type=dict(any_=["FAILED"]),
                        name=dict(any_=["Failed", "Completed"]),
                    )
                )
            ),
            2,
        ],
        [
            dict(
                flow_run_filter=filters.FlowRunFilter(
                    deployment_id=dict(any_=[d_1_1_id, d_1_2_id])
                )
            ),
            3,
        ],
        [
            dict(
                flow_run_filter=filters.FlowRunFilter(
                    deployment_id=dict(any_=[d_1_1_id, d_3_1_id])
                )
            ),
            3,
        ],
        # flow runs that are subflows (via task attribute)
        [
            dict(
                task_run_filter=filters.TaskRunFilter(subflow_runs=dict(exists_=True))
            ),
            1,
        ],
        # flow runs that are subflows (via flow run attribute)
        [
            dict(
                flow_run_filter=filters.FlowRunFilter(
                    parent_task_run_id=dict(is_null_=False)
                )
            ),
            1,
        ],
        # empty filter
        [dict(flow_filter=filters.FlowFilter()), 12],
        # multiple empty filters
        [
            dict(
                flow_filter=filters.FlowFilter(),
                flow_run_filter=filters.FlowRunFilter(),
            ),
            12,
        ],
        [
            dict(
                work_pool_filter=filters.WorkPoolFilter(name=dict(any_=["Test Pool"]))
            ),
            1,
        ],
        [
            dict(
                work_queue_filter=filters.WorkQueueFilter(name=dict(any_=["default"]))
            ),
            1,
        ],
        [
            dict(
                work_pool_filter=filters.WorkPoolFilter(name=dict(any_=["Test Pool"])),
                work_queue_filter=filters.WorkQueueFilter(name=dict(any_=["default"])),
            ),
            1,
        ],
        [
            dict(
                work_pool_filter=filters.WorkPoolFilter(
                    name=dict(any_=["A pool that doesn't exist"])
                ),
                work_queue_filter=filters.WorkQueueFilter(name=dict(any_=["default"])),
            ),
            0,
        ],
        [
            dict(
                work_pool_filter=filters.WorkPoolFilter(name=dict(any_=["Test Pool"])),
                work_queue_filter=filters.WorkQueueFilter(
                    name=dict(any_=["a queue that doesn't exist"])
                ),
            ),
            0,
        ],
    ]

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_python_client_filter(self, kwargs, expected):
        async with get_client() as client:
            flow_runs = await client.read_flow_runs(**kwargs)
            assert len(flow_runs) == expected

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_models_count(self, session, kwargs, expected):
        count = await models.flow_runs.count_flow_runs(session=session, **kwargs)
        assert count == expected

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_models_read(self, session, kwargs, expected):
        read = await models.flow_runs.read_flow_runs(session=session, **kwargs)
        assert len({r.id for r in read}) == expected

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_api_count(self, client, kwargs, expected):
        adjusted_kwargs = adjust_kwargs_for_client(kwargs)

        response = await client.post("/flow_runs/count", json=adjusted_kwargs)
        assert response.json() == expected

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_api_read(self, client, kwargs, expected):
        adjusted_kwargs = adjust_kwargs_for_client(kwargs)

        response = await client.post(
            "/flow_runs/filter",
            json=adjusted_kwargs,
        )
        assert len({r["id"] for r in response.json()}) == expected


class TestCountTaskRunsModels:
    params = [
        [{}, 10],
        [dict(flow_filter=filters.FlowFilter(name=dict(any_=["f-1", "f-2"]))), 6],
        [dict(flow_filter=filters.FlowFilter(name=dict(any_=["f-1", "f-100"]))), 3],
        [dict(flow_filter=filters.FlowFilter(name=dict(any_=["f-1"]))), 3],
        [dict(flow_filter=filters.FlowFilter(name=dict(like_="f-"))), 10],
        [dict(task_run_filter=filters.TaskRunFilter(name=dict(like_="task-run"))), 3],
        [dict(task_run_filter=filters.TaskRunFilter(name=dict(like_="run-2"))), 2],
        [dict(task_run_filter=filters.TaskRunFilter(name=dict(like_="2a"))), 1],
        [dict(flow_filter=filters.FlowFilter(tags=dict(all_=["db"]))), 6],
        [dict(flow_filter=filters.FlowFilter(tags=dict(all_=["db", "blue"]))), 3],
        [dict(flow_filter=filters.FlowFilter(tags=dict(all_=["db", "red"]))), 0],
        [dict(flow_run_filter=filters.FlowRunFilter(tags=dict(all_=["db", "red"]))), 0],
        [
            dict(flow_run_filter=filters.FlowRunFilter(tags=dict(all_=["db", "blue"]))),
            3,
        ],
        [
            dict(flow_run_filter=filters.FlowRunFilter(name=dict(like_="test-happy"))),
            3,
        ],
        [
            dict(
                flow_run_filter=filters.FlowRunFilter(
                    name=dict(like_="test-happy-mallard")
                )
            ),
            0,
        ],
        [dict(deployment_filter=filters.DeploymentFilter(id=dict(any_=[d_1_1_id]))), 3],
        [dict(deployment_filter=filters.DeploymentFilter(name=dict(like_="d_1"))), 3],
        [dict(flow_run_filter=filters.FlowRunFilter(tags=dict(is_null_=True))), 4],
        [
            dict(
                flow_run_filter=filters.FlowRunFilter(
                    state=dict(type=dict(any_=["COMPLETED"]))
                )
            ),
            4,
        ],
        # search for completed states with "NOT-COMPLETED" as the name, should return nothing
        [
            dict(
                flow_run_filter=filters.FlowRunFilter(
                    state=dict(
                        type=dict(any_=["COMPLETED"]), name=dict(any_=["NOT-COMPLETED"])
                    )
                )
            ),
            0,
        ],
        [
            dict(
                flow_run_filter=filters.FlowRunFilter(
                    state=dict(name=dict(any_=["Completed"]))
                )
            ),
            4,
        ],
        [
            dict(
                flow_run_filter=filters.FlowRunFilter(
                    state=dict(type=dict(any_=["COMPLETED"]))
                ),
                flow_filter=filters.FlowFilter(tags=dict(all_=["xyz"])),
            ),
            0,
        ],
        [
            dict(
                flow_run_filter=filters.FlowRunFilter(
                    deployment_id=dict(any_=[d_1_1_id, d_1_2_id])
                )
            ),
            3,
        ],
        [
            dict(
                flow_run_filter=filters.FlowRunFilter(
                    deployment_id=dict(any_=[d_1_1_id, d_3_1_id])
                )
            ),
            4,
        ],
        # task runs with subflow children
        [
            dict(
                task_run_filter=filters.TaskRunFilter(subflow_runs=dict(exists_=True))
            ),
            1,
        ],
        # task runs without subflow children
        [
            dict(
                task_run_filter=filters.TaskRunFilter(subflow_runs=dict(exists_=False))
            ),
            9,
        ],
        # task runs with subflow children and the tag 'subflow'
        [
            dict(
                task_run_filter=filters.TaskRunFilter(
                    subflow_runs=dict(exists_=True), tags=dict(all_=["subflow"])
                )
            ),
            0,
        ],
        # empty filter
        [dict(flow_filter=filters.FlowFilter()), 10],
        # multiple empty filters
        [
            dict(
                flow_filter=filters.FlowFilter(),
                flow_run_filter=filters.FlowRunFilter(),
            ),
            10,
        ],
    ]

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_python_client_filter(self, kwargs, expected):
        async with get_client() as client:
            task_runs = await client.read_task_runs(**kwargs)
            assert len(task_runs) == expected

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_models_count(self, session, kwargs, expected):
        count = await models.task_runs.count_task_runs(session=session, **kwargs)
        assert count == expected

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_models_read(self, session, kwargs, expected):
        read = await models.task_runs.read_task_runs(session=session, **kwargs)
        assert len({r.id for r in read}) == expected

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_api_count(self, client, kwargs, expected):
        adjusted_kwargs = adjust_kwargs_for_client(kwargs)
        response = await client.post(
            "/task_runs/count",
            json=adjusted_kwargs,
        )
        assert response.json() == expected

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_api_read(self, client, kwargs, expected):
        adjusted_kwargs = adjust_kwargs_for_client(kwargs)

        response = await client.post(
            "/task_runs/filter",
            json=adjusted_kwargs,
        )
        assert len({r["id"] for r in response.json()}) == expected


class TestCountDeploymentModels:
    params = [
        [{}, 3],
        [
            dict(deployment_filter=filters.DeploymentFilter(name=dict(any_=["d-1-1"]))),
            1,
        ],
        [
            dict(deployment_filter=filters.DeploymentFilter(name=dict(like_="d-"))),
            3,
        ],
        [
            dict(deployment_filter=filters.DeploymentFilter(name=dict(like_="-1-2"))),
            1,
        ],
        [
            dict(
                deployment_filter=filters.DeploymentFilter(
                    name=dict(any_=["d-1-1", "d-1-2"])
                )
            ),
            2,
        ],
        [
            dict(
                deployment_filter=filters.DeploymentFilter(name=dict(any_=["zaphod"]))
            ),
            0,
        ],
        [dict(flow_filter=filters.FlowFilter(name=dict(any_=["f-1", "f-2"]))), 2],
        [dict(flow_filter=filters.FlowFilter(name=dict(any_=["f-1", "f-100"]))), 2],
        [dict(flow_filter=filters.FlowFilter(name=dict(any_=["f-3"]))), 1],
        [dict(flow_filter=filters.FlowFilter(name=dict(like_="f-"))), 3],
        [dict(flow_filter=filters.FlowFilter(name=dict(like_="f-2"))), 0],
        [dict(flow_filter=filters.FlowFilter(tags=dict(all_=["db"]))), 2],
        [dict(flow_filter=filters.FlowFilter(tags=dict(all_=["db", "red"]))), 0],
        [dict(flow_run_filter=filters.FlowRunFilter(name=dict(like_="test-happy"))), 1],
        [dict(flow_run_filter=filters.FlowRunFilter(name=dict(like_="nothing!"))), 0],
        [
            dict(
                flow_run_filter=filters.FlowRunFilter(
                    deployment_id=dict(any_=[d_1_1_id, d_1_2_id, uuid4()])
                )
            ),
            2,
        ],
        [
            dict(
                task_run_filter=filters.TaskRunFilter(
                    state=dict(type=dict(any_=["FAILED"]))
                )
            ),
            1,
        ],
        # next two check that filters are applied as an intersection not a union
        [
            dict(
                deployment_filter=filters.DeploymentFilter(name=dict(any_=["d-1-1"])),
                flow_filter=filters.FlowFilter(name=dict(any_=["f-1", "f-2"])),
            ),
            1,
        ],
        [
            dict(
                deployment_filter=filters.DeploymentFilter(name=dict(any_=["d-1-1"])),
                flow_filter=filters.FlowFilter(name=dict(any_=["f-2"])),
            ),
            0,
        ],
        [
            dict(
                work_pool_filter=filters.WorkPoolFilter(name=dict(any_=["Test Pool"]))
            ),
            1,
        ],
        [
            dict(
                work_queue_filter=filters.WorkQueueFilter(name=dict(any_=["default"]))
            ),
            1,
        ],
        [
            dict(
                work_pool_filter=filters.WorkPoolFilter(name=dict(any_=["Test Pool"])),
                work_queue_filter=filters.WorkQueueFilter(name=dict(any_=["default"])),
            ),
            1,
        ],
        [
            dict(
                work_pool_filter=filters.WorkPoolFilter(
                    name=dict(any_=["A pool that doesn't exist"])
                ),
                work_queue_filter=filters.WorkQueueFilter(name=dict(any_=["default"])),
            ),
            0,
        ],
        [
            dict(
                work_pool_filter=filters.WorkPoolFilter(name=dict(any_=["Test Pool"])),
                work_queue_filter=filters.WorkQueueFilter(
                    name=dict(any_=["a queue that doesn't exist"])
                ),
            ),
            0,
        ],
        # empty filter
        [dict(flow_filter=filters.FlowFilter()), 3],
        # multiple empty filters
        [
            dict(
                flow_filter=filters.FlowFilter(),
                flow_run_filter=filters.FlowRunFilter(),
            ),
            3,
        ],
    ]

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_python_client_filter(self, kwargs, expected):
        async with get_client() as client:
            deployments = await client.read_deployments(**kwargs)
            assert len(deployments) == expected

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_models_count(self, session, kwargs, expected):
        count = await models.deployments.count_deployments(session=session, **kwargs)
        assert count == expected

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_models_read(self, session, kwargs, expected):
        read = await models.deployments.read_deployments(session=session, **kwargs)
        assert len({r.id for r in read}) == expected

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_api_count(self, client, kwargs, expected):
        adjusted_kwargs = adjust_kwargs_for_client(kwargs)

        response = await client.post(
            "/deployments/count",
            json=adjusted_kwargs,
        )

        assert response.json() == expected

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_api_read(self, client, kwargs, expected):
        adjusted_kwargs = adjust_kwargs_for_client(kwargs)

        response = await client.post(
            "/deployments/filter",
            json=adjusted_kwargs,
        )
        assert len({r["id"] for r in response.json()}) == expected

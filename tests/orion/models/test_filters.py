from uuid import uuid4
from datetime import timedelta
import pydantic
import json
from prefect.orion.schemas.data import DataDocument
import pendulum
import pytest

from prefect.client import OrionClient
from prefect.orion import models
from prefect.orion.schemas import core, filters, states, schedules


@pytest.fixture(autouse=True, scope="module")
async def clear_db():
    """Prevent automatic database-clearing behavior after every test"""
    pass


d_1_1_id = uuid4()
d_1_2_id = uuid4()
d_3_1_id = uuid4()


@pytest.fixture(autouse=True, scope="module")
async def data(database_engine, flow_function, db_config):

    session_factory = await db_config.session_factory()
    async with session_factory() as session:

        create_flow = lambda flow: models.flows.create_flow(session=session, flow=flow)
        create_deployment = lambda deployment: models.deployments.create_deployment(
            session=session, deployment=deployment
        )
        create_flow_run = lambda flow_run: models.flow_runs.create_flow_run(
            session=session, flow_run=flow_run
        )
        create_task_run = lambda task_run: models.task_runs.create_task_run(
            session=session, task_run=task_run
        )

        f_1 = await create_flow(flow=core.Flow(name="f-1", tags=["db", "blue"]))
        f_2 = await create_flow(flow=core.Flow(name="f-2", tags=["db"]))
        f_3 = await create_flow(flow=core.Flow(name="f-3"))

        # ---- deployments
        flow_data = DataDocument.encode("cloudpickle", flow_function)

        d_1_1 = await create_deployment(
            deployment=core.Deployment(
                id=d_1_1_id,
                name="d-1-1",
                flow_id=f_1.id,
                flow_data=flow_data,
                schedule=schedules.IntervalSchedule(interval=timedelta(days=1)),
                is_schedule_active=True,
            )
        )
        d_1_2 = await create_deployment(
            deployment=core.Deployment(
                id=d_1_2_id,
                name="d-1-2",
                flow_data=flow_data,
                flow_id=f_1.id,
                is_schedule_active=False,
            )
        )
        d_3_1 = await create_deployment(
            deployment=core.Deployment(
                id=d_3_1_id,
                name="d-3-1",
                flow_data=flow_data,
                flow_id=f_3.id,
                schedule=schedules.IntervalSchedule(interval=timedelta(days=1)),
                is_schedule_active=True,
            )
        )

        # ---- flow 1

        fr_1_1 = await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=f_1.id,
                tags=["db", "blue"],
                state=states.Completed(),
                deployment_id=d_1_1.id,
            )
        )

        fr_1_2 = await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=f_1.id,
                tags=["db", "blue"],
                state=states.Completed(),
            )
        )
        fr_1_3 = await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=f_1.id,
                tags=["db", "red"],
                state=states.Failed(),
                deployment_id=d_1_1.id,
            )
        )
        fr_1_4 = await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=f_1.id,
                tags=["red"],
                state=states.Running(),
            )
        )
        fr_1_5 = await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=f_1.id, state=states.Running(), deployment_id=d_1_2.id
            )
        )

        # ---- flow 2

        fr_2_1 = await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=f_2.id,
                tags=["db", "blue"],
                state=states.Completed(),
            )
        )

        fr_2_2 = await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=f_2.id,
                tags=["red"],
                state=states.Running(),
            )
        )
        fr_2_3 = await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=f_2.id,
                tags=["db", "red"],
                state=states.Failed(),
            )
        )

        # ---- flow 3

        fr_3_1 = await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=f_3.id,
                tags=[],
                state=states.Completed(),
                deployment_id=d_3_1.id,
            )
        )

        fr_3_2 = await create_flow_run(
            flow_run=core.FlowRun(
                flow_id=f_3.id,
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
                dynamic_key="0",
            )
        )
        await create_task_run(
            task_run=core.TaskRun(
                flow_run_id=fr_1_1.id,
                task_key="b",
                state=states.Completed(),
                dynamic_key="0",
            )
        )
        await create_task_run(
            task_run=core.TaskRun(
                flow_run_id=fr_1_1.id,
                task_key="c",
                state=states.Completed(),
                dynamic_key="0",
            )
        )

        await create_task_run(
            task_run=core.TaskRun(
                flow_run_id=fr_2_2.id,
                task_key="a",
                state=states.Running(),
                dynamic_key="0",
            )
        )
        await create_task_run(
            task_run=core.TaskRun(
                flow_run_id=fr_2_2.id,
                task_key="b",
                state=states.Completed(),
                dynamic_key="0",
            )
        )
        await create_task_run(
            task_run=core.TaskRun(
                flow_run_id=fr_2_2.id,
                task_key="c",
                state=states.Completed(),
                dynamic_key="0",
            )
        )

        await create_task_run(
            task_run=core.TaskRun(
                flow_run_id=fr_3_1.id,
                task_key="a",
                state=states.Failed(),
                dynamic_key="0",
            )
        )

        # ----------------- create a subflow run and parent tasks
        f_4 = await create_flow(flow=core.Flow(name="f-4"))

        # create a parent flow run
        fr1 = await create_flow_run(
            flow_run=core.FlowRun(flow_id=f_4.id),
        )
        tr1 = await create_task_run(
            task_run=core.TaskRun(flow_run_id=fr1.id, task_key="a", dynamic_key="0")
        )
        tr2 = await create_task_run(
            task_run=core.TaskRun(flow_run_id=fr1.id, task_key="b", dynamic_key="0")
        )

        # create a subflow corresponding to tr2
        fr2 = await create_flow_run(
            flow_run=core.FlowRun(flow_id=f_4.id, parent_task_run_id=tr2.id),
        )
        tr3 = await create_task_run(
            task_run=core.TaskRun(flow_run_id=fr2.id, task_key="a", dynamic_key="0")
        )

        # ----------------- Commit and yield

        await session.commit()

        yield

    # ----------------- clear data

    async with database_engine.begin() as conn:
        for table in reversed(db_config.Base.metadata.sorted_tables):
            await conn.execute(table.delete())


class TestCountFlowsModels:

    params = [
        [{}, 4],
        [dict(flow_filter=filters.FlowFilter(name=dict(any_=["f-1", "f-2"]))), 2],
        [dict(flow_filter=filters.FlowFilter(name=dict(any_=["f-1", "f-100"]))), 1],
        [dict(flow_filter=filters.FlowFilter(name=dict(any_=["f-1"]))), 1],
        [dict(flow_filter=filters.FlowFilter(tags=dict(all_=["db"]))), 2],
        [dict(flow_filter=filters.FlowFilter(tags=dict(all_=["db", "blue"]))), 1],
        [dict(flow_filter=filters.FlowFilter(tags=dict(all_=["db", "red"]))), 0],
        [dict(flow_run_filter=filters.FlowRunFilter(tags=dict(all_=["db", "red"]))), 3],
        [
            dict(flow_run_filter=filters.FlowRunFilter(tags=dict(all_=["db", "blue"]))),
            2,
        ],
        [dict(flow_run_filter=filters.FlowRunFilter(tags=dict(is_null_=True))), 3],
        [dict(deployment_filter=filters.DeploymentFilter(id=dict(any_=[d_1_1_id]))), 1],
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
    ]

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_python_client_filter(self, kwargs, expected):
        async with OrionClient() as client:
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
            adjusted_kwargs[k] = v

        repsonse = await client.post(
            "/flows/count",
            json=json.loads(
                json.dumps(
                    adjusted_kwargs,
                    default=pydantic.json.pydantic_encoder,
                )
            ),
        )
        assert repsonse.json() == expected

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_api_read(self, client, kwargs, expected):
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
            adjusted_kwargs[k] = v

        repsonse = await client.post(
            "/flows/filter",
            json=json.loads(
                json.dumps(
                    adjusted_kwargs,
                    default=pydantic.json.pydantic_encoder,
                )
            ),
        )
        assert len({r["id"] for r in repsonse.json()}) == expected


class TestCountFlowRunModels:

    params = [
        [{}, 12],
        [dict(flow_filter=filters.FlowFilter(name=dict(any_=["f-1", "f-2"]))), 8],
        [dict(flow_filter=filters.FlowFilter(name=dict(any_=["f-1", "f-100"]))), 5],
        [dict(flow_filter=filters.FlowFilter(name=dict(any_=["f-1"]))), 5],
        [dict(flow_filter=filters.FlowFilter(tags=dict(all_=["db"]))), 8],
        [dict(flow_filter=filters.FlowFilter(tags=dict(all_=["db", "blue"]))), 5],
        [dict(flow_filter=filters.FlowFilter(tags=dict(all_=["db", "red"]))), 0],
        [dict(flow_run_filter=filters.FlowRunFilter(tags=dict(all_=["db", "red"]))), 3],
        [
            dict(flow_run_filter=filters.FlowRunFilter(tags=dict(all_=["db", "blue"]))),
            3,
        ],
        [dict(flow_run_filter=filters.FlowRunFilter(tags=dict(is_null_=True))), 4],
        [dict(deployment_filter=filters.DeploymentFilter(id=dict(any_=[d_1_1_id]))), 2],
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
    ]

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_python_client_filter(self, kwargs, expected):
        async with OrionClient() as client:
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
            adjusted_kwargs[k] = v

        repsonse = await client.post(
            "/flow_runs/count",
            json=json.loads(
                json.dumps(adjusted_kwargs, default=pydantic.json.pydantic_encoder)
            ),
        )
        assert repsonse.json() == expected

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_api_read(self, client, kwargs, expected):
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
            adjusted_kwargs[k] = v

        repsonse = await client.post(
            "/flow_runs/filter",
            json=json.loads(
                json.dumps(
                    adjusted_kwargs,
                    default=pydantic.json.pydantic_encoder,
                )
            ),
        )
        assert len({r["id"] for r in repsonse.json()}) == expected


class TestCountTaskRunsModels:

    params = [
        [{}, 10],
        [dict(flow_filter=filters.FlowFilter(name=dict(any_=["f-1", "f-2"]))), 6],
        [dict(flow_filter=filters.FlowFilter(name=dict(any_=["f-1", "f-100"]))), 3],
        [dict(flow_filter=filters.FlowFilter(name=dict(any_=["f-1"]))), 3],
        [dict(flow_filter=filters.FlowFilter(tags=dict(all_=["db"]))), 6],
        [dict(flow_filter=filters.FlowFilter(tags=dict(all_=["db", "blue"]))), 3],
        [dict(flow_filter=filters.FlowFilter(tags=dict(all_=["db", "red"]))), 0],
        [dict(flow_run_filter=filters.FlowRunFilter(tags=dict(all_=["db", "red"]))), 0],
        [
            dict(flow_run_filter=filters.FlowRunFilter(tags=dict(all_=["db", "blue"]))),
            3,
        ],
        [dict(deployment_filter=filters.DeploymentFilter(id=dict(any_=[d_1_1_id]))), 3],
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
    ]

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_python_client_filter(self, kwargs, expected):
        async with OrionClient() as client:
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
            adjusted_kwargs[k] = v
        repsonse = await client.post(
            "/task_runs/count",
            json=json.loads(
                json.dumps(adjusted_kwargs, default=pydantic.json.pydantic_encoder)
            ),
        )
        assert repsonse.json() == expected

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_api_read(self, client, kwargs, expected):
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
            adjusted_kwargs[k] = v

        repsonse = await client.post(
            "/task_runs/filter",
            json=json.loads(
                json.dumps(
                    adjusted_kwargs,
                    default=pydantic.json.pydantic_encoder,
                )
            ),
        )
        assert len({r["id"] for r in repsonse.json()}) == expected


class TestCountDeploymentModels:

    params = [
        [{}, 3],
        [
            dict(deployment_filter=filters.DeploymentFilter(name=dict(any_=["d-1-1"]))),
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
        [
            dict(
                deployment_filter=filters.DeploymentFilter(
                    is_schedule_active=dict(eq_=True)
                )
            ),
            2,
        ],
        [
            dict(
                deployment_filter=filters.DeploymentFilter(
                    is_schedule_active=dict(eq_=False)
                )
            ),
            1,
        ],
        [dict(flow_filter=filters.FlowFilter(name=dict(any_=["f-1", "f-2"]))), 2],
        [dict(flow_filter=filters.FlowFilter(name=dict(any_=["f-1", "f-100"]))), 2],
        [dict(flow_filter=filters.FlowFilter(name=dict(any_=["f-3"]))), 1],
        [dict(flow_filter=filters.FlowFilter(tags=dict(all_=["db"]))), 2],
        [dict(flow_filter=filters.FlowFilter(tags=dict(all_=["db", "red"]))), 0],
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
    ]

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_python_client_filter(self, kwargs, expected):
        async with OrionClient() as client:
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
            adjusted_kwargs[k] = v

        repsonse = await client.post(
            "/deployments/count",
            json=json.loads(
                json.dumps(
                    adjusted_kwargs,
                    default=pydantic.json.pydantic_encoder,
                )
            ),
        )
        assert repsonse.json() == expected

    @pytest.mark.parametrize("kwargs,expected", params)
    async def test_api_read(self, client, kwargs, expected):
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
            adjusted_kwargs[k] = v

        repsonse = await client.post(
            "/deployments/filter",
            json=json.loads(
                json.dumps(
                    adjusted_kwargs,
                    default=pydantic.json.pydantic_encoder,
                )
            ),
        )
        assert len({r["id"] for r in repsonse.json()}) == expected

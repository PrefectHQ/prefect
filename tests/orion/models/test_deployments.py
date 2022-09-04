import datetime
from uuid import uuid4

import anyio
import pendulum
import pytest
import sqlalchemy as sa

from prefect.orion import models, schemas
from prefect.orion.schemas import filters
from prefect.orion.schemas.states import StateType


class TestCreateDeployment:
    async def test_create_deployment_succeeds(
        self, session, flow, infrastructure_document_id
    ):

        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                manifest_path="file.json",
                flow_id=flow.id,
                parameters={"foo": "bar"},
                tags=["foo", "bar"],
                infrastructure_document_id=infrastructure_document_id,
            ),
        )
        assert deployment.name == "My Deployment"
        assert deployment.flow_id == flow.id
        assert deployment.manifest_path == "file.json"
        assert deployment.parameters == {"foo": "bar"}
        assert deployment.tags == ["foo", "bar"]
        assert deployment.infrastructure_document_id == infrastructure_document_id

    async def test_creating_a_deployment_creates_associated_work_queue(
        self, session, flow
    ):
        wq = await models.work_queues.read_work_queue_by_name(
            session=session, name="wq-1"
        )
        assert wq is None

        await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="d1", work_queue_name="wq-1", flow_id=flow.id, manifest_path=""
            ),
        )
        await session.commit()

        wq = await models.work_queues.read_work_queue_by_name(
            session=session, name="wq-1"
        )
        assert wq is not None

    async def test_creating_a_deployment_with_existing_work_queue_is_ok(
        self, session, flow
    ):

        await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="d1", work_queue_name="wq-1", flow_id=flow.id, manifest_path=""
            ),
        )
        await session.commit()

        await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="d2", work_queue_name="wq-1", flow_id=flow.id, manifest_path=""
            ),
        )
        await session.commit()

    async def test_create_deployment_updates_existing_deployment(
        self,
        session,
        flow,
        infrastructure_document_id,
        infrastructure_document_id_2,
    ):

        openapi_schema = {
            "title": "Parameters",
            "type": "object",
            "properties": {
                "foo": {"title": "foo", "default": "Will", "type": "string"}
            },
        }
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                flow_id=flow.id,
                infrastructure_document_id=infrastructure_document_id,
                parameter_openapi_schema=openapi_schema,
            ),
        )
        original_update_time = deployment.updated

        assert deployment.name == "My Deployment"
        assert deployment.flow_id == flow.id
        assert deployment.parameters == {}
        assert deployment.parameter_openapi_schema == openapi_schema
        assert deployment.tags == []
        assert deployment.infrastructure_document_id == infrastructure_document_id

        await anyio.sleep(1)  # Sleep so update time is easy to differentiate

        schedule = schemas.schedules.IntervalSchedule(
            interval=datetime.timedelta(days=1)
        )

        openapi_schema["properties"]["new"] = {
            "title": "new",
            "default": True,
            "type": "bool",
        }
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                flow_id=flow.id,
                schedule=schedule,
                is_schedule_active=False,
                parameters={"foo": "bar"},
                parameter_openapi_schema=openapi_schema,
                tags=["foo", "bar"],
                infrastructure_document_id=infrastructure_document_id_2,
            ),
        )

        assert deployment.name == "My Deployment"
        assert deployment.flow_id == flow.id
        assert not deployment.is_schedule_active
        assert deployment.schedule == schedule
        assert deployment.parameters == {"foo": "bar"}
        assert deployment.parameter_openapi_schema == openapi_schema
        assert deployment.tags == ["foo", "bar"]
        assert deployment.updated > original_update_time
        assert deployment.infrastructure_document_id == infrastructure_document_id_2

    async def test_create_deployment_with_schedule(
        self, session, flow, flow_function, infrastructure_document_id
    ):
        schedule = schemas.schedules.IntervalSchedule(
            interval=datetime.timedelta(days=1)
        )
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                flow_id=flow.id,
                manifest_path="file.json",
                schedule=schedule,
                infrastructure_document_id=infrastructure_document_id,
            ),
        )
        assert deployment.name == "My Deployment"
        assert deployment.flow_id == flow.id
        assert deployment.manifest_path == "file.json"
        assert deployment.schedule == schedule
        assert deployment.infrastructure_document_id == infrastructure_document_id


class TestReadDeployment:
    async def test_read_deployment(
        self, session, flow, flow_function, infrastructure_document_id
    ):
        # create a deployment to read
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                manifest_path="file.json",
                flow_id=flow.id,
                infrastructure_document_id=infrastructure_document_id,
            ),
        )
        assert deployment.name == "My Deployment"

        read_deployment = await models.deployments.read_deployment(
            session=session, deployment_id=deployment.id
        )
        assert deployment.id == read_deployment.id
        assert deployment.name == read_deployment.name

    async def test_read_deployment_returns_none_if_does_not_exist(self, session):
        result = await models.deployments.read_deployment(
            session=session, deployment_id=str(uuid4())
        )
        assert result is None

    async def test_read_deployment_by_name(
        self, session, flow, flow_function, infrastructure_document_id
    ):
        # create a deployment to read
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                manifest_path="file.json",
                flow_id=flow.id,
                infrastructure_document_id=infrastructure_document_id,
            ),
        )
        assert deployment.name == "My Deployment"

        read_deployment = await models.deployments.read_deployment_by_name(
            session=session,
            name=deployment.name,
            flow_name=flow.name,
        )
        assert deployment.id == read_deployment.id
        assert deployment.name == read_deployment.name

    async def test_read_deployment_by_name_does_not_return_deployments_from_other_flows(
        self, session, flow_function, infrastructure_document_id
    ):
        flow_1, flow_2 = [
            await models.flows.create_flow(
                session=session, flow=schemas.core.Flow(name=f"my-flow-{i}")
            )
            for i in range(2)
        ]

        deployment_1 = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                manifest_path="file.json",
                flow_id=flow_1.id,
                infrastructure_document_id=infrastructure_document_id,
            ),
        )
        deployment_2 = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                manifest_path="file.json",
                flow_id=flow_2.id,
                infrastructure_document_id=infrastructure_document_id,
            ),
        )

        read_deployment = await models.deployments.read_deployment_by_name(
            session=session,
            name=deployment_1.name,
            flow_name=flow_1.name,
        )
        assert read_deployment.id == deployment_1.id

    async def test_read_deployment_by_name_returns_none_if_does_not_exist(
        self, session
    ):
        result = await models.deployments.read_deployment_by_name(
            session=session,
            name=str(uuid4()),
            flow_name=str(uuid4()),
        )
        assert result is None


class TestReadDeployments:
    @pytest.fixture
    async def deployment_id_1(self):
        return uuid4()

    @pytest.fixture
    async def deployment_id_2(self):
        return uuid4()

    @pytest.fixture
    async def deployment_id_3(self):
        return uuid4()

    @pytest.fixture
    async def filter_data(
        self,
        session,
        flow,
        flow_function,
        deployment_id_1,
        deployment_id_2,
        deployment_id_3,
        infrastructure_document_id,
    ):
        await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                id=deployment_id_1,
                name="My Deployment",
                manifest_path="file.json",
                flow_id=flow.id,
                is_schedule_active=True,
                infrastructure_document_id=infrastructure_document_id,
            ),
        )
        await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                id=deployment_id_2,
                name="Another Deployment",
                manifest_path="file.json",
                flow_id=flow.id,
                tags=["tb12"],
                is_schedule_active=True,
                infrastructure_document_id=infrastructure_document_id,
            ),
        )
        await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                id=deployment_id_3,
                name="Yet Another Deployment",
                manifest_path="file.json",
                flow_id=flow.id,
                tags=["tb12", "goat"],
                is_schedule_active=False,
            ),
        )

    async def test_read_deployments(self, filter_data, session):
        read_deployments = await models.deployments.read_deployments(session=session)
        assert len(read_deployments) == 3

    async def test_read_deployments_applies_limit(self, filter_data, session):
        read_deployments = await models.deployments.read_deployments(
            session=session, limit=1
        )
        assert len(read_deployments) == 1

    async def test_read_deployments_applies_offset(
        self, deployment_id_1, filter_data, session
    ):
        read_deployments = await models.deployments.read_deployments(
            session=session, offset=1, limit=1
        )
        # sorts by name by default
        assert {deployment.id for deployment in read_deployments} == {deployment_id_1}

    async def test_read_deployments_returns_empty_list(self, session):
        read_deployments = await models.deployments.read_deployments(session=session)
        assert len(read_deployments) == 0

    async def test_read_deployment_filters_by_id(
        self, filter_data, deployment_id_1, session
    ):
        result = await models.deployments.read_deployments(
            session=session,
            deployment_filter=filters.DeploymentFilter(
                id=filters.DeploymentFilterId(any_=[deployment_id_1]),
            ),
        )
        assert {res.id for res in result} == {deployment_id_1}

    async def test_read_deployment_filters_by_name(
        self, filter_data, deployment_id_2, session
    ):
        result = await models.deployments.read_deployments(
            session=session,
            deployment_filter=filters.DeploymentFilter(
                name=filters.DeploymentFilterName(any_=["Another Deployment"]),
            ),
        )
        assert {res.id for res in result} == {deployment_id_2}

    async def test_read_deployment_filters_by_schedule_active(
        self, filter_data, deployment_id_3, session
    ):
        result = await models.deployments.read_deployments(
            session=session,
            deployment_filter=filters.DeploymentFilter(
                is_schedule_active=filters.DeploymentFilterIsScheduleActive(eq_=False)
            ),
        )
        assert {res.id for res in result} == {deployment_id_3}

    async def test_read_deployment_filters_filters_by_tags(
        self, filter_data, deployment_id_1, deployment_id_3, session
    ):
        result = await models.deployments.read_deployments(
            session=session,
            deployment_filter=filters.DeploymentFilter(
                tags=filters.DeploymentFilterTags(all_=["goat"])
            ),
        )
        assert {res.id for res in result} == {deployment_id_3}
        result = await models.deployments.read_deployments(
            session=session,
            deployment_filter=filters.DeploymentFilter(
                tags=filters.DeploymentFilterTags(is_null_=True)
            ),
        )
        assert {res.id for res in result} == {deployment_id_1}

    async def test_read_deployment_filters_filters_by_flow_criteria(
        self, filter_data, flow, deployment_id_3, session
    ):
        result = await models.deployments.read_deployments(
            session=session,
            deployment_filter=filters.DeploymentFilter(
                tags=filters.DeploymentFilterTags(all_=["goat"])
            ),
            flow_filter=filters.FlowFilter(id=filters.FlowFilterId(any_=[flow.id])),
        )
        assert {res.id for res in result} == {deployment_id_3}
        result = await models.deployments.read_deployments(
            session=session,
            deployment_filter=filters.DeploymentFilter(
                tags=filters.DeploymentFilterTags(all_=["goat"])
            ),
            flow_filter=filters.FlowFilter(id=filters.FlowFilterId(any_=[uuid4()])),
        )
        assert len(result) == 0

    async def test_read_deployment_filters_filters_by_flow_run_criteria(
        self, filter_data, flow, deployment_id_3, session
    ):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id, deployment_id=deployment_id_3
            ),
        )
        result = await models.deployments.read_deployments(
            session=session,
            flow_run_filter=filters.FlowRunFilter(
                id=filters.FlowRunFilterId(any_=[flow_run.id])
            ),
        )
        assert {res.id for res in result} == {deployment_id_3}

        result = await models.deployments.read_deployments(
            session=session,
            flow_run_filter=filters.FlowRunFilter(
                id=filters.FlowRunFilterId(any_=[uuid4()])
            ),
        )
        assert len(result) == 0

    async def test_read_deployment_filters_filters_by_task_run_criteria(
        self, filter_data, flow, deployment_id_3, session
    ):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id, deployment_id=deployment_id_3
            ),
        )
        task_run = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id, task_key="my-task", dynamic_key="0"
            ),
        )
        result = await models.deployments.read_deployments(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(id=dict(any_=[task_run.id])),
        )
        assert {res.id for res in result} == {deployment_id_3}

        result = await models.deployments.read_deployments(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(id=dict(any_=[uuid4()])),
        )
        assert len(result) == 0


class TestDeleteDeployment:
    async def test_delete_deployment(self, session, flow, flow_function):
        # create a deployment to delete

        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                manifest_path="file.json",
                flow_id=flow.id,
            ),
        )
        assert deployment.name == "My Deployment"

        assert await models.deployments.delete_deployment(
            session=session, deployment_id=deployment.id
        )

        # make sure the deployment is deleted
        result = await models.deployments.read_deployment(
            session=session, deployment_id=deployment.id
        )
        assert result is None

    async def test_delete_deployment_returns_false_if_does_not_exist(self, session):
        result = await models.deployments.delete_deployment(
            session=session, deployment_id=str(uuid4())
        )
        assert result is False


class TestScheduledRuns:
    async def test_schedule_runs_inserts_in_db(self, flow, deployment, session, db):
        scheduled_runs = await models.deployments.schedule_runs(
            session, deployment_id=deployment.id
        )
        assert len(scheduled_runs) == 100
        query_result = await session.execute(
            sa.select(db.FlowRun).where(
                db.FlowRun.state.has(db.FlowRunState.type == StateType.SCHEDULED)
            )
        )

        db_scheduled_runs = query_result.scalars().all()
        assert {r.id for r in db_scheduled_runs} == set(scheduled_runs)

        expected_times = {
            pendulum.now("UTC").start_of("day").add(days=i + 1) for i in range(100)
        }

        actual_times = set()
        for run_id in scheduled_runs:
            run = await models.flow_runs.read_flow_run(
                session=session, flow_run_id=run_id
            )
            actual_times.add(run.state.state_details.scheduled_time)
        assert actual_times == expected_times

    async def test_schedule_runs_is_idempotent(self, flow, deployment, session, db):
        scheduled_runs = await models.deployments.schedule_runs(
            session, deployment_id=deployment.id
        )
        assert len(scheduled_runs) == 100

        second_scheduled_runs = await models.deployments.schedule_runs(
            session, deployment_id=deployment.id
        )

        assert len(second_scheduled_runs) == 0

        # only 100 runs were inserted
        query_result = await session.execute(
            sa.select(db.FlowRun).where(
                db.FlowRun.flow_id == flow.id,
                db.FlowRun.state.has(db.FlowRunState.type == StateType.SCHEDULED),
            )
        )

        db_scheduled_runs = query_result.scalars().all()
        assert len(db_scheduled_runs) == 100

    async def test_schedule_n_runs(self, flow, deployment, session):
        scheduled_runs = await models.deployments.schedule_runs(
            session, deployment_id=deployment.id, max_runs=3
        )
        assert len(scheduled_runs) == 3

    async def test_schedule_does_not_error_if_theres_no_schedule(
        self, flow, flow_function, session
    ):
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                manifest_path="file.json",
                flow_id=flow.id,
            ),
        )
        scheduled_runs = await models.deployments.schedule_runs(
            session, deployment_id=deployment.id, max_runs=3
        )
        assert scheduled_runs == []

    async def test_schedule_runs_respects_infrastructure(
        self, flow, flow_function, session, infrastructure_document_id
    ):
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                manifest_path="file.json",
                schedule=schemas.schedules.IntervalSchedule(
                    interval=datetime.timedelta(days=1)
                ),
                flow_id=flow.id,
                infrastructure_document_id=infrastructure_document_id,
            ),
        )
        scheduled_runs = await models.deployments.schedule_runs(
            session, deployment_id=deployment.id, max_runs=1
        )
        assert len(scheduled_runs) == 1
        scheduled_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=scheduled_runs[0]
        )
        assert scheduled_run.infrastructure_document_id == infrastructure_document_id

    @pytest.mark.parametrize("tags", [[], ["foo"]])
    async def test_schedule_runs_applies_tags(self, tags, flow, flow_function, session):
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                manifest_path="file.json",
                schedule=schemas.schedules.IntervalSchedule(
                    interval=datetime.timedelta(days=1)
                ),
                flow_id=flow.id,
                tags=tags,
            ),
        )
        scheduled_runs = await models.deployments.schedule_runs(
            session, deployment_id=deployment.id, max_runs=2
        )
        assert len(scheduled_runs) == 2
        for run_id in scheduled_runs:
            run = await models.flow_runs.read_flow_run(
                session=session, flow_run_id=run_id
            )
            assert run.tags == ["auto-scheduled"] + tags

    async def test_schedule_runs_applies_work_queue(self, flow, flow_function, session):
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                manifest_path="file.json",
                schedule=schemas.schedules.IntervalSchedule(
                    interval=datetime.timedelta(days=1)
                ),
                flow_id=flow.id,
                work_queue_name="wq-test-runs",
            ),
        )
        scheduled_runs = await models.deployments.schedule_runs(
            session, deployment_id=deployment.id, max_runs=2
        )
        assert len(scheduled_runs) == 2
        for run_id in scheduled_runs:
            run = await models.flow_runs.read_flow_run(
                session=session, flow_run_id=run_id
            )
            assert run.work_queue_name == "wq-test-runs"

    @pytest.mark.parametrize("parameters", [{}, {"foo": "bar"}])
    async def test_schedule_runs_applies_parameters(
        self, parameters, flow, flow_function, session
    ):
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                manifest_path="file.json",
                schedule=schemas.schedules.IntervalSchedule(
                    interval=datetime.timedelta(days=1)
                ),
                flow_id=flow.id,
                parameters=parameters,
            ),
        )
        scheduled_runs = await models.deployments.schedule_runs(
            session, deployment_id=deployment.id, max_runs=2
        )
        assert len(scheduled_runs) == 2
        for run_id in scheduled_runs:
            run = await models.flow_runs.read_flow_run(
                session=session, flow_run_id=run_id
            )
            assert run.parameters == parameters

    async def test_schedule_runs_with_end_time(self, flow, deployment, session):
        scheduled_runs = await models.deployments.schedule_runs(
            session,
            deployment_id=deployment.id,
            end_time=pendulum.now("UTC").add(days=17),
        )
        assert len(scheduled_runs) == 17

    async def test_schedule_runs_with_start_time(self, flow, deployment, session):
        scheduled_runs = await models.deployments.schedule_runs(
            session,
            deployment_id=deployment.id,
            start_time=pendulum.now("UTC").add(days=100),
            end_time=pendulum.now("UTC").add(days=150),
        )
        assert len(scheduled_runs) == 50

        expected_times = {
            pendulum.now("UTC").start_of("day").add(days=i + 1) for i in range(100, 150)
        }
        actual_times = set()
        for run_id in scheduled_runs:
            run = await models.flow_runs.read_flow_run(
                session=session, flow_run_id=run_id
            )
            actual_times.add(run.state.state_details.scheduled_time)
        assert actual_times == expected_times

    async def test_schedule_runs_with_times_and_max_number(
        self, flow, deployment, session
    ):
        scheduled_runs = await models.deployments.schedule_runs(
            session,
            deployment_id=deployment.id,
            start_time=pendulum.now("UTC").add(days=100),
            end_time=pendulum.now("UTC").add(days=150),
            max_runs=3,
        )
        assert len(scheduled_runs) == 3

        expected_times = {
            pendulum.now("UTC").start_of("day").add(days=i + 1) for i in range(100, 103)
        }
        actual_times = set()
        for run_id in scheduled_runs:
            run = await models.flow_runs.read_flow_run(
                session=session, flow_run_id=run_id
            )
            actual_times.add(run.state.state_details.scheduled_time)
        assert actual_times == expected_times

    async def test_backfill(self, flow, deployment, session):
        # backfills are just schedules for past dates...
        scheduled_runs = await models.deployments.schedule_runs(
            session,
            deployment_id=deployment.id,
            start_time=pendulum.now("UTC").subtract(days=1000),
            end_time=pendulum.now("UTC").subtract(days=950),
        )
        assert len(scheduled_runs) == 50

        expected_times = {
            pendulum.now("UTC").start_of("day").subtract(days=i)
            for i in range(950, 1000)
        }

        actual_times = set()
        for run_id in scheduled_runs:
            run = await models.flow_runs.read_flow_run(
                session=session, flow_run_id=run_id
            )
            actual_times.add(run.state.state_details.scheduled_time)
        assert actual_times == expected_times

    async def test_run_details_are_applied_to_scheduled_runs(self, deployment, session):
        await models.deployments.schedule_runs(
            session,
            deployment_id=deployment.id,
        )

        all_runs = await models.flow_runs.read_flow_runs(session)
        assert all_runs
        for r in all_runs:
            assert r.state_type == schemas.states.StateType.SCHEDULED
            assert r.expected_start_time is not None
            assert r.expected_start_time == r.next_scheduled_start_time

    async def test_scheduling_multiple_batches_correctly_updates_runs(
        self, session, deployment, flow_function, flow, db
    ):
        # ensures that updating flow run states works correctly and doesnt set
        # any to None inadvertently
        deployment_2 = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My second deployment",
                manifest_path="file.json",
                flow_id=flow.id,
                schedule=schemas.schedules.IntervalSchedule(
                    interval=datetime.timedelta(days=1)
                ),
            ),
        )

        # delete all runs
        await session.execute(sa.delete(db.FlowRun))

        # schedule runs
        await models.deployments.schedule_runs(
            session=session, deployment_id=deployment.id
        )

        result = await session.execute(
            sa.select(sa.func.count(db.FlowRun.id)).where(db.FlowRun.state_id.is_(None))
        )
        # no runs with missing states
        assert result.scalar() == 0

        # schedule more runs from a different deployment
        await models.deployments.schedule_runs(
            session=session, deployment_id=deployment_2.id
        )

        result = await session.execute(
            sa.select(sa.func.count(db.FlowRun.id)).where(db.FlowRun.state_id.is_(None))
        )
        # no runs with missing states
        assert result.scalar() == 0


class TestUpdateDeployment:
    async def test_updating_deployment_creates_associated_work_queue(
        self, session, deployment
    ):
        wq = await models.work_queues.read_work_queue_by_name(
            session=session, name="wq-1"
        )
        assert wq is None

        await models.deployments.update_deployment(
            session=session,
            deployment_id=deployment.id,
            deployment=schemas.actions.DeploymentUpdate(work_queue_name="wq-1"),
        )
        await session.commit()

        wq = await models.work_queues.read_work_queue_by_name(
            session=session, name="wq-1"
        )
        assert wq is not None

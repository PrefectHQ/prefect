from statistics import mode
from uuid import uuid4
import copy
import pendulum
import pytest
import sqlalchemy as sa

from prefect.orion import models, schemas


class TestCreateFlowRun:
    async def test_create_flow_run(self, flow, session):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        assert flow_run.flow_id == flow.id

    async def test_create_flow_run_has_no_default_state(self, flow, session):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.actions.FlowRunCreate(flow_id=flow.id),
        )
        assert flow_run.flow_id == flow.id
        assert flow_run.state is None

    async def test_create_flow_run_with_state(self, flow, session):
        state_id = uuid4()
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.actions.FlowRunCreate(
                flow_id=flow.id,
                state=schemas.states.State(
                    id=state_id, type="RUNNING", name="My Running State"
                ),
            ),
        )
        assert flow_run.flow_id == flow.id
        assert flow_run.state.id == state_id

        query = await session.execute(
            sa.select(models.orm.FlowRunState).filter_by(id=state_id)
        )
        result = query.scalar()
        assert result.id == state_id
        assert result.name == "My Running State"

    async def test_create_flow_run_with_state_and_idempotency_key(self, flow, session):
        scheduled_state_id = uuid4()
        running_state_id = uuid4()

        scheduled_flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.actions.FlowRunCreate(
                flow_id=flow.id,
                idempotency_key="TB12",
                state=schemas.states.State(
                    id=scheduled_state_id, type="SCHEDULED", name="My Scheduled State"
                ),
            ),
        )
        assert scheduled_flow_run.flow_id == flow.id
        assert scheduled_flow_run.state.id == scheduled_state_id

        running_flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.actions.FlowRunCreate(
                flow_id=flow.id,
                idempotency_key="TB12",
                state=schemas.states.State(
                    id=running_state_id, type="RUNNING", name="My Running State"
                ),
            ),
        )
        assert running_flow_run.flow_id == flow.id
        assert running_flow_run.state.id == scheduled_state_id

        query = await session.execute(
            sa.select(models.orm.FlowRunState).filter_by(id=scheduled_state_id)
        )
        result = query.scalar()
        assert result.id == scheduled_state_id
        assert result.name == "My Scheduled State"

    async def test_create_multiple_flow_runs(self, flow, session):
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )

        assert flow_run_1.id != flow_run_2.id

    # the sqlalchemy session will (correctly) recognize that a new object was
    # added to it with the same primary key as an existing object, and emit a
    # warning. Because that is the situation we want to test for, we filter the
    # warning to avoid unecessary noise.
    @pytest.mark.filterwarnings(
        "ignore: New instance .* conflicts with persistent instance"
    )
    async def test_create_flow_run_with_same_id_as_existing_run_errors(
        self, flow, session
    ):
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )

        with pytest.raises(sa.exc.IntegrityError):
            await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(id=flow_run_1.id, flow_id=flow.id),
            )

    async def test_create_flow_run_with_idempotency_key(self, flow, session):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, idempotency_key="test"),
        )
        assert flow_run.idempotency_key == "test"

    async def test_create_flow_run_with_existing_idempotency_key(self, flow, session):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, idempotency_key="test"),
        )
        anotha_flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, idempotency_key="test"),
        )
        assert flow_run.id == anotha_flow_run.id

    async def test_create_flow_run_with_existing_idempotency_key_of_a_different_flow(
        self, flow, session
    ):
        flow2 = models.orm.Flow(name="another flow")
        session.add(flow2)
        await session.flush()

        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, idempotency_key="test"),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow2.id, idempotency_key="test"),
        )

        assert flow_run.id != flow_run_2.id

    async def test_create_flow_run_with_deployment_id(
        self, flow, session, flow_function
    ):

        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="",
                flow_id=flow.id,
                flow_data=schemas.data.DataDocument.encode(
                    "cloudpickle", flow_function
                ),
            ),
        )
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, deployment_id=deployment.id),
        )
        assert flow_run.flow_id == flow.id
        assert flow_run.deployment_id == deployment.id


class TestUpdateFlowRun:
    async def test_update_flow_run_succeeds(self, flow, session):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, flow_version="1.0"),
        )

        flow_run_id = copy.deepcopy(flow_run.id)

        update_result = await models.flow_runs.update_flow_run(
            session=session,
            flow_run_id=flow_run_id,
            flow_run=schemas.actions.FlowRunUpdate(flow_version="The next one"),
        )
        assert update_result

        updated_flow_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run_id
        )
        assert flow_run_id == updated_flow_run.id == flow_run.id
        assert updated_flow_run.flow_version == "The next one"

    async def test_update_flow_run_does_not_update_if_nothing_set(self, flow, session):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, flow_version="1.0"),
        )

        flow_run_id = copy.deepcopy(flow_run.id)

        update_result = await models.flow_runs.update_flow_run(
            session=session,
            flow_run_id=flow_run_id,
            flow_run=schemas.actions.FlowRunUpdate(),
        )
        assert update_result

        updated_flow_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run_id
        )
        assert flow_run_id == updated_flow_run.id == flow_run.id
        assert updated_flow_run.flow_version == "1.0"

    async def test_update_flow_run_returns_false_if_flow_run_does_not_exist(
        self, session
    ):
        assert not (
            await models.flow_runs.update_flow_run(
                session=session,
                flow_run_id=uuid4(),
                flow_run=schemas.actions.FlowRunUpdate(),
            )
        )


class TestReadFlowRun:
    async def test_read_flow_run(self, flow, session):
        # create a flow run to read
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )

        read_flow_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run.id
        )
        assert flow_run == read_flow_run

    async def test_read_flow_run_returns_none_if_does_not_exist(self, session):
        result = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=uuid4()
        )
        assert result is None


class TestReadFlowRuns:
    @pytest.fixture
    async def flow_runs(self, flow, session):
        await session.execute(sa.delete(models.orm.FlowRun))

        flow_2 = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="another-test"),
        )

        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        flow_run_3 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow_2.id),
        )
        await session.commit()
        return [flow_run_1, flow_run_2, flow_run_3]

    async def test_read_flow_runs(self, flow_runs, session):
        read_flow_runs = await models.flow_runs.read_flow_runs(session=session)
        assert len(read_flow_runs) == 3

    async def test_read_flow_runs_applies_limit(self, flow_runs, session):
        read_flow_runs = await models.flow_runs.read_flow_runs(session=session, limit=1)
        assert len(read_flow_runs) == 1

    async def test_read_flow_runs_returns_empty_list(self, session):
        read_flow_runs = await models.flow_runs.read_flow_runs(session=session)
        assert len(read_flow_runs) == 0

    async def test_read_flow_runs_filters_by_ids(self, flow, session):
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        flow_run_3 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(ids=[flow_run_1.id]),
        )
        assert len(result) == 1
        assert result[0].id == flow_run_1.id

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                ids=[flow_run_1.id, flow_run_2.id]
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id, flow_run_2.id}

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(ids=[uuid4()]),
        )
        assert len(result) == 0

    async def test_read_flow_runs_filters_by_tags_all(self, flow, session):
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, tags=["db", "blue"]),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, tags=["db"]),
        )
        flow_run_3 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(tags_all=["db", "blue"]),
        )
        assert len(result) == 1
        assert result[0].id == flow_run_1.id

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(tags_all=["db"]),
        )
        assert {res.id for res in result} == {flow_run_1.id, flow_run_2.id}

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(tags_all=["green"]),
        )
        assert len(result) == 0

    async def test_read_flow_runs_filters_by_states(self, flow, session):
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.Running(name="My Running State"),
            ),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.Completed(name="My Completed State"),
            ),
        )
        flow_run_3 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id, state=schemas.states.Failed(name="RIP")
            ),
        )

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(states=["RUNNING"]),
        )
        assert len(result) == 1
        assert result[0].id == flow_run_1.id

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                states=["RUNNING", "COMPLETED"]
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id, flow_run_2.id}

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(states=["SCHEDULED"]),
        )
        assert len(result) == 0

    async def test_read_flow_runs_filters_by_flow_versions(self, flow, session):
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, flow_version="alpha"),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, flow_version="beta"),
        )
        flow_run_3 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(flow_versions=["alpha"]),
        )
        assert len(result) == 1
        assert result[0].id == flow_run_1.id

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                flow_versions=["alpha", "beta"]
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id, flow_run_2.id}

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(flow_versions=["omega"]),
        )
        assert len(result) == 0

    async def test_read_flow_runs_filters_by_start_time_before(self, flow, session):
        now = pendulum.now()
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.State(
                    type="COMPLETED",
                    name="My Completed State",
                    timestamp=now.subtract(minutes=1),
                ),
            ),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.State(
                    type="COMPLETED",
                    name="My Completed State",
                    timestamp=now.add(minutes=1),
                ),
            ),
        )

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(start_time_before=now),
        )
        assert len(result) == 1
        assert result[0].id == flow_run_1.id

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                start_time_before=now.add(minutes=10)
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id, flow_run_2.id}

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                start_time_before=now.subtract(minutes=10)
            ),
        )
        assert len(result) == 0

    async def test_read_flow_runs_filters_by_start_time_after(self, flow, session):
        now = pendulum.now()
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.State(
                    type="COMPLETED",
                    name="My Completed State",
                    timestamp=now.subtract(minutes=1),
                ),
            ),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.State(
                    type="COMPLETED",
                    name="My Completed State",
                    timestamp=now.add(minutes=1),
                ),
            ),
        )

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(start_time_after=now),
        )
        assert len(result) == 1
        assert result[0].id == flow_run_2.id

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                start_time_after=now.subtract(minutes=10)
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id, flow_run_2.id}

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                start_time_after=now.add(minutes=10)
            ),
        )
        assert len(result) == 0

    async def test_read_flow_runs_filters_by_parent_task_run_ids(
        self, flow, task_run, session
    ):
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id, parent_task_run_id=task_run.id
            ),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
            ),
        )

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                parent_task_run_ids=[task_run.id]
            ),
        )
        assert len(result) == 1
        assert result[0].id == flow_run_1.id

    async def test_read_flow_runs_filters_by_multiple_criteria(self, flow, session):
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, tags=["db", "blue"]),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, tags=["db"]),
        )

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                ids=[flow_run_1.id], tags_all=["db"]
            ),
        )
        assert len(result) == 1
        assert result[0].id == flow_run_1.id

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                ids=[flow_run_2.id], tags_all=["blue"]
            ),
        )
        assert len(result) == 0

    async def test_read_flow_runs_filters_by_flow_criteria(self, flow, session):
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_filter=schemas.filters.FlowFilter(ids=[flow.id]),
        )
        assert len(result) == 2
        assert {res.id for res in result} == {flow_run_1.id, flow_run_2.id}

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_filter=schemas.filters.FlowFilter(ids=[uuid4()]),
        )
        assert len(result) == 0

    async def test_read_flow_runs_filters_by_flow_and_task_run_criteria(
        self, flow, session
    ):
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.actions.TaskRunCreate(
                flow_run_id=flow_run_2.id, task_key="my-key"
            ),
        )

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_filter=schemas.filters.FlowFilter(ids=[flow.id]),
            task_run_filter=schemas.filters.TaskRunFilter(ids=[task_run_1.id]),
        )
        assert len(result) == 1
        assert result[0].id == flow_run_2.id

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_filter=schemas.filters.FlowFilter(ids=[flow.id]),
            task_run_filter=schemas.filters.TaskRunFilter(ids=[uuid4()]),
        )
        assert len(result) == 0

    async def test_read_flow_runs_applies_sort(self, flow, session):
        now = pendulum.now()
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.State(
                    type="SCHEDULED",
                    timestamp=now.subtract(minutes=1),
                ),
            ),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.State(
                    type="SCHEDULED",
                    timestamp=now.add(minutes=1),
                ),
            ),
        )
        await session.commit()
        result = await models.flow_runs.read_flow_runs(
            session=session,
            sort=schemas.sorting.FlowRunSort.EXPECTED_START_TIME_DESC,
            limit=1,
        )
        assert result[0].id == flow_run_2.id


class TestDeleteFlowRun:
    async def test_delete_flow_run(self, flow, session):
        # create a flow run to delete
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )

        assert await models.flow_runs.delete_flow_run(
            session=session, flow_run_id=flow_run.id
        )

        # make sure the flow run is deleted
        result = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run.id
        )
        assert result is None

    async def test_delete_flow_run_returns_false_if_does_not_exist(self, session):
        result = await models.flow_runs.delete_flow_run(
            session=session, flow_run_id=uuid4()
        )
        assert result is False

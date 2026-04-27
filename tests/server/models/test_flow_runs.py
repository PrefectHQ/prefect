import datetime
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models, schemas
from prefect.server.database import orm_models
from prefect.server.exceptions import ObjectNotFoundError
from prefect.server.schemas.core import TaskRunResult
from prefect.types import KeyValueLabels
from prefect.types._datetime import now


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
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        assert flow_run.flow_id == flow.id
        assert flow_run.state is None

    async def test_create_flow_run_with_state(self, flow, session, db):
        state_id = uuid4()
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.State(
                    id=state_id, type="RUNNING", name="My Running State"
                ),
            ),
        )
        assert flow_run.flow_id == flow.id
        assert flow_run.state.id == state_id

        query = await session.execute(sa.select(db.FlowRunState).filter_by(id=state_id))
        result = query.scalar()
        assert result.id == state_id
        assert result.name == "My Running State"

    async def test_create_flow_run_with_state_and_idempotency_key(
        self, flow, session, db
    ):
        scheduled_state_id = uuid4()
        running_state_id = uuid4()

        scheduled_flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
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
            flow_run=schemas.core.FlowRun(
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
            sa.select(db.FlowRunState).filter_by(id=scheduled_state_id)
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
    # warning to avoid unnecessary noise.
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
        another_flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, idempotency_key="test"),
        )
        assert flow_run.id == another_flow_run.id

    async def test_create_flow_run_with_differing_idempotency_key(self, flow, session):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, idempotency_key="test"),
        )
        another_flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, idempotency_key="foo"),
        )
        assert flow_run.id != another_flow_run.id

    async def test_create_flow_run_with_existing_idempotency_key_of_a_different_flow(
        self, flow, session, db
    ):
        flow2 = db.Flow(name="another flow")
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

    async def test_create_flow_run_with_deployment_id(self, flow, session):
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="",
                flow_id=flow.id,
            ),
        )
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, deployment_id=deployment.id),
        )
        assert flow_run.flow_id == flow.id
        assert flow_run.deployment_id == deployment.id

    async def test_create_flow_run_with_created_by(self, flow, session):
        created_by = schemas.core.CreatedBy(
            id=uuid4(), type="A-TYPE", display_value="creator-of-things"
        )
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, created_by=created_by),
        )
        assert flow_run.created_by
        assert flow_run.created_by.id == created_by.id
        assert flow_run.created_by.display_value == created_by.display_value
        assert flow_run.created_by.type == created_by.type


class TestUpdateFlowRun:
    async def test_update_flow_run_succeeds(
        self,
        flow,
        session,
    ):
        job_vars = {"foo": "bar"}
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, flow_version="1.0"),
        )

        flow_run_id = flow_run.id

        update_result = await models.flow_runs.update_flow_run(
            session=session,
            flow_run_id=flow_run_id,
            flow_run=schemas.actions.FlowRunUpdate(
                flow_version="The next one",
                job_variables=job_vars,
            ),
        )
        assert update_result

        updated_flow_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run_id
        )
        assert flow_run_id == updated_flow_run.id == flow_run.id
        assert updated_flow_run.flow_version == "The next one"
        assert updated_flow_run.job_variables == job_vars

    async def test_update_flow_run_does_not_update_if_nothing_set(self, flow, session):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, flow_version="1.0"),
        )

        flow_run_id = flow_run.id

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

    async def test_update_flow_run_labels(
        self, flow: orm_models.Flow, session: AsyncSession
    ):
        """Test that flow run labels can be updated by patching existing labels"""

        # Create a flow run with initial labels
        initial_labels: KeyValueLabels = {"env": "test", "version": "1.0"}
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, labels=initial_labels),
        )

        # Update with new labels
        new_labels: KeyValueLabels = {"version": "2.0", "new_key": "new_value"}
        update_success = await models.flow_runs.update_flow_run_labels(
            session=session, flow_run_id=flow_run.id, labels=new_labels
        )
        assert update_success is True

        # Read the flow run back and verify labels were merged correctly
        updated_flow_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run.id
        )
        assert updated_flow_run
        assert updated_flow_run.labels == {
            "prefect.flow.id": str(flow.id),
            "env": "test",  # Kept from initial labels
            "version": "2.0",  # Updated from new labels
            "new_key": "new_value",  # Added from new labels
        }

    async def test_update_flow_run_labels_raises_if_flow_run_does_not_exist(
        self, session: AsyncSession, caplog: pytest.LogCaptureFixture
    ):
        """Test that updating labels for a non-existent flow run raises"""
        with pytest.raises(ObjectNotFoundError) as exc:
            await models.flow_runs.update_flow_run_labels(
                session=session, flow_run_id=uuid4(), labels={"test": "label"}
            )
        assert "Flow run with id" in str(exc.value)

    async def test_update_flow_run_labels_with_empty_initial_labels(
        self, flow: orm_models.Flow, session: AsyncSession
    ):
        """Test that labels can be added to a flow run with no existing labels"""

        # Create a flow run with no labels
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
            ),
        )

        # Update with new labels
        new_labels: KeyValueLabels = {"env": "test", "version": "1.0"}
        update_success = await models.flow_runs.update_flow_run_labels(
            session=session, flow_run_id=flow_run.id, labels=new_labels
        )
        assert update_success is True

        # Read the flow run back and verify labels were added
        updated_flow_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run.id
        )
        assert updated_flow_run
        assert updated_flow_run.labels == {
            "prefect.flow.id": str(flow.id),
            **new_labels,
        }


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

    async def test_read_flow_run_with_job_variables(self, flow, session):
        job_vars = {"foo": "bar"}
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, job_variables=job_vars),
        )

        read_flow_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run.id
        )
        assert read_flow_run.job_variables == job_vars

    async def test_read_flow_run_returns_none_if_does_not_exist(self, session):
        result = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=uuid4()
        )
        assert result is None


class TestReadFlowRuns:
    @pytest.fixture
    async def flow_runs(self, flow, session, db):
        await session.execute(sa.delete(db.FlowRun))

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

        # any_
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                id=schemas.filters.FlowRunFilterId(any_=[flow_run_1.id])
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id}

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                id=schemas.filters.FlowRunFilterId(any_=[flow_run_1.id, flow_run_2.id])
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id, flow_run_2.id}

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                id=schemas.filters.FlowRunFilterId(any_=[uuid4()])
            ),
        )
        assert len(result) == 0

        # not_any_
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                id=schemas.filters.FlowRunFilterId(
                    not_any_=[flow_run_1.id, flow_run_2.id]
                )
            ),
        )
        assert {res.id for res in result} == {flow_run_3.id}

    async def test_read_flow_runs_filters_by_name(self, flow, session):
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, name="my flow run 1"),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, name="my flow run 2"),
        )

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                name=schemas.filters.FlowRunFilterName(any_=["my flow run 2"])
            ),
        )
        assert {res.id for res in result} == {flow_run_2.id}

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                name=schemas.filters.FlowRunFilterName(any_=["adkljfldkajfkldjs"])
            ),
        )
        assert len(result) == 0

    async def test_read_flow_runs_filters_by_tags(self, flow, session):
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

        # all_
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                tags=schemas.filters.FlowRunFilterTags(all_=["db", "blue"])
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id}

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                tags=schemas.filters.FlowRunFilterTags(all_=["db"])
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id, flow_run_2.id}

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                tags=schemas.filters.FlowRunFilterTags(all_=["green"])
            ),
        )
        assert len(result) == 0

        # is_null_
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                tags=schemas.filters.FlowRunFilterTags(is_null_=True)
            ),
        )
        assert {res.id for res in result} == {flow_run_3.id}
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                tags=schemas.filters.FlowRunFilterTags(is_null_=False)
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id, flow_run_2.id}

    async def test_read_flow_runs_filters_by_states_any(self, flow, session):
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
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id, state=schemas.states.Failed(name="RIP")
            ),
        )

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                state=dict(
                    type=schemas.filters.FlowRunFilterStateType(any_=["RUNNING"])
                )
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id}

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                state=dict(
                    type=schemas.filters.FlowRunFilterStateType(
                        any_=["RUNNING", "COMPLETED"]
                    )
                )
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id, flow_run_2.id}

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                state=dict(
                    type=schemas.filters.FlowRunFilterStateType(any_=["SCHEDULED"])
                )
            ),
        )
        assert len(result) == 0

    async def test_read_flow_runs_filters_by_flow_versions_any(self, flow, session):
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, flow_version="alpha"),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, flow_version="beta"),
        )
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                flow_version=schemas.filters.FlowRunFilterFlowVersion(any_=["alpha"])
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id}

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                flow_version=schemas.filters.FlowRunFilterFlowVersion(
                    any_=["alpha", "beta"]
                )
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id, flow_run_2.id}

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                flow_version=schemas.filters.FlowRunFilterFlowVersion(any_=["omega"])
            ),
        )
        assert len(result) == 0

    async def test_read_flow_runs_filters_by_start_time(self, flow, session):
        now_dt = now()
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                start_time=now_dt - datetime.timedelta(minutes=1),
                state=schemas.states.State(
                    type="COMPLETED",
                    name="My Completed State 1",
                ),
            ),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                start_time=now_dt,
                state=schemas.states.State(
                    type="COMPLETED",
                    name="My Completed State 2",
                ),
            ),
        )
        flow_run_3 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                start_time=now_dt + datetime.timedelta(minutes=1),
                state=schemas.states.State(
                    type="COMPLETED",
                    name="My Completed State 3",
                ),
            ),
        )
        flow_run_4 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                # Use PENDING state (non-terminal) to test start_time is_null_ filter
                # Terminal states now get start_time set automatically
                state=schemas.states.State(
                    type="PENDING",
                    name="My Pending State 4",
                ),
            ),
        )

        # before_
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                start_time=schemas.filters.FlowRunFilterStartTime(
                    before_=now_dt - datetime.timedelta(seconds=1)
                )
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id}

        # after_
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                start_time=schemas.filters.FlowRunFilterStartTime(after_=now_dt)
            ),
        )
        # flow_run_4 has no start_time but expected_start_time is set,
        # and the filter uses coalesce(start_time, expected_start_time)
        assert {res.id for res in result} == {
            flow_run_2.id,
            flow_run_3.id,
            flow_run_4.id,
        }

        # before_ AND after_
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                start_time=schemas.filters.FlowRunFilterStartTime(
                    before_=now_dt + datetime.timedelta(minutes=10),
                    after_=now_dt + datetime.timedelta(seconds=1),
                )
            ),
        )
        assert {res.id for res in result} == {flow_run_3.id}

        # is_null_
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                start_time=schemas.filters.FlowRunFilterStartTime(is_null_=True)
            ),
        )
        assert {res.id for res in result} == {flow_run_4.id}
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                start_time=schemas.filters.FlowRunFilterStartTime(is_null_=False)
            ),
        )
        assert {res.id for res in result} == {
            flow_run_1.id,
            flow_run_2.id,
            flow_run_3.id,
        }

    async def test_read_flow_runs_filters_by_next_scheduled_start_time(
        self, flow, session
    ):
        now_dt = now()
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                next_scheduled_start_time=now_dt - datetime.timedelta(minutes=1),
                state=schemas.states.State(
                    type="COMPLETED",
                    name="My Completed State",
                ),
            ),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                next_scheduled_start_time=now_dt,
                state=schemas.states.State(
                    type="COMPLETED",
                    name="My Completed State",
                ),
            ),
        )
        flow_run_3 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                next_scheduled_start_time=now_dt + datetime.timedelta(minutes=1),
                state=schemas.states.State(
                    type="COMPLETED",
                    name="My Completed State",
                ),
            ),
        )

        # before_
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                next_scheduled_start_time=schemas.filters.FlowRunFilterNextScheduledStartTime(
                    before_=now_dt - datetime.timedelta(seconds=1)
                )
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id}

        # after_
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                next_scheduled_start_time=schemas.filters.FlowRunFilterNextScheduledStartTime(
                    after_=now_dt
                )
            ),
        )
        assert {res.id for res in result} == {flow_run_2.id, flow_run_3.id}

        # before_ AND after_
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                next_scheduled_start_time=schemas.filters.FlowRunFilterNextScheduledStartTime(
                    before_=now_dt + datetime.timedelta(minutes=10),
                    after_=now_dt + datetime.timedelta(seconds=1),
                )
            ),
        )
        assert {res.id for res in result} == {flow_run_3.id}

    async def test_read_flow_runs_filters_by_expected_start_time(self, flow, session):
        now_dt = now()
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                expected_start_time=now_dt - datetime.timedelta(minutes=1),
                state=schemas.states.State(
                    type="COMPLETED",
                    name="My Completed State",
                ),
            ),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                expected_start_time=now_dt,
                state=schemas.states.State(
                    type="COMPLETED",
                    name="My Completed State",
                ),
            ),
        )
        flow_run_3 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                expected_start_time=now_dt + datetime.timedelta(minutes=1),
                state=schemas.states.State(
                    type="COMPLETED",
                    name="My Completed State",
                ),
            ),
        )

        # before_
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                expected_start_time=schemas.filters.FlowRunFilterExpectedStartTime(
                    before_=now_dt - datetime.timedelta(seconds=1)
                )
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id}

        # after_
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                expected_start_time=schemas.filters.FlowRunFilterExpectedStartTime(
                    after_=now_dt
                )
            ),
        )
        assert {res.id for res in result} == {flow_run_2.id, flow_run_3.id}

        # before_ AND after_
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                expected_start_time=schemas.filters.FlowRunFilterExpectedStartTime(
                    before_=now_dt + datetime.timedelta(minutes=10),
                    after_=now_dt + datetime.timedelta(seconds=1),
                )
            ),
        )
        assert len(result) == 1
        assert result[0].id == flow_run_3.id

    async def test_read_flows_filters_by_deployment_id(self, flow, session):
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="",
                flow_id=flow.id,
            ),
        )
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, deployment_id=deployment.id),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        # test any_
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                deployment_id=schemas.filters.FlowRunFilterDeploymentId(
                    any_=[deployment.id]
                )
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id}

        # test is_null_
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                deployment_id=schemas.filters.FlowRunFilterDeploymentId(is_null_=True)
            ),
        )
        assert {res.id for res in result} == {flow_run_2.id}
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                deployment_id=schemas.filters.FlowRunFilterDeploymentId(is_null_=False)
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id}

    async def test_read_flow_runs_filters_by_parent_task_run_ids(self, flow, session):
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
            ),
        )
        task_run = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.actions.TaskRunCreate(
                flow_run_id=flow_run_1.id, task_key="my-key", dynamic_key="0"
            ),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id, parent_task_run_id=task_run.id
            ),
        )

        # test any_
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                parent_task_run_id=schemas.filters.FlowRunFilterParentTaskRunId(
                    any_=[task_run.id]
                )
            ),
        )
        assert {res.id for res in result} == {flow_run_2.id}

        # test is_null_
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                parent_task_run_id=schemas.filters.FlowRunFilterParentTaskRunId(
                    is_null_=True
                )
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id}
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                parent_task_run_id=schemas.filters.FlowRunFilterParentTaskRunId(
                    is_null_=False
                )
            ),
        )
        assert {res.id for res in result} == {flow_run_2.id}

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
                id=schemas.filters.FlowRunFilterId(any_=[flow_run_1.id]),
                tags=schemas.filters.FlowRunFilterTags(all_=["db"]),
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id}

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                id=schemas.filters.FlowRunFilterId(any_=[flow_run_2.id]),
                tags=schemas.filters.FlowRunFilterTags(all_=["blue"]),
            ),
        )
        assert len(result) == 0

        # filter using OR
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                operator="or_",
                id=schemas.filters.FlowRunFilterId(any_=[flow_run_2.id]),
                tags=schemas.filters.FlowRunFilterTags(all_=["blue"]),
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id, flow_run_2.id}

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
            flow_filter=schemas.filters.FlowFilter(
                id=schemas.filters.FlowFilterId(any_=[flow.id])
            ),
        )
        assert len(result) == 2
        assert {res.id for res in result} == {flow_run_1.id, flow_run_2.id}

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_filter=schemas.filters.FlowFilter(
                id=schemas.filters.FlowFilterId(any_=[uuid4()])
            ),
        )
        assert len(result) == 0

    async def test_read_flow_runs_filters_by_deployment_criteria(
        self, flow, deployment, session
    ):
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                deployment_id=deployment.id,
                state=schemas.states.State(
                    type="SCHEDULED",
                ),
            ),
        )
        result = await models.flow_runs.read_flow_runs(
            session=session,
            deployment_filter=schemas.filters.DeploymentFilter(
                id=dict(any_=[deployment.id])
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id}

        result = await models.flow_runs.read_flow_runs(
            session=session,
            deployment_filter=schemas.filters.DeploymentFilter(id=dict(any_=[uuid4()])),
        )
        assert len(result) == 0

    async def test_read_flow_runs_filters_by_flow_and_task_run_criteria(
        self, flow, session
    ):
        await models.flow_runs.create_flow_run(
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
                flow_run_id=flow_run_2.id, task_key="my-key", dynamic_key="0"
            ),
        )

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_filter=schemas.filters.FlowFilter(
                id=schemas.filters.FlowFilterId(any_=[flow.id])
            ),
            task_run_filter=schemas.filters.TaskRunFilter(
                id=schemas.filters.TaskRunFilterId(any_=[task_run_1.id])
            ),
        )
        assert {res.id for res in result} == {flow_run_2.id}

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_filter=schemas.filters.FlowFilter(
                id=schemas.filters.FlowFilterId(any_=[flow.id])
            ),
            task_run_filter=schemas.filters.TaskRunFilter(
                id=schemas.filters.TaskRunFilterId(any_=[uuid4()])
            ),
        )
        assert len(result) == 0

    async def test_read_flow_runs_filters_by_work_pool_name(self, flow, session):
        work_pool = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(name="work-pool"),
        )
        work_queue = await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="work-pool-queue"),
        )
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, work_queue_id=work_queue.id),
        )

        result = await models.flow_runs.read_flow_runs(
            session=session,
            work_pool_filter=schemas.filters.WorkPoolFilter(
                name=schemas.filters.WorkPoolFilterName(any_=[work_pool.name])
            ),
        )
        assert {res.id for res in result} == {flow_run_2.id}

    async def test_read_flow_runs_filters_by_work_queue_id(self, session, flow):
        work_pool = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(name="work-pool"),
        )
        work_queue = await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="work-pool-queue"),
        )
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, work_queue_id=work_queue.id),
        )

        result = await models.flow_runs.read_flow_runs(
            session=session,
            work_queue_filter=schemas.filters.WorkQueueFilter(
                id=schemas.filters.WorkQueueFilterId(any_=[work_queue.id])
            ),
        )
        assert {res.id for res in result} == {flow_run_2.id}

    async def test_read_flow_runs_applies_sort(self, flow, session):
        now_dt = now()
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.State(
                    type="SCHEDULED",
                    timestamp=now_dt - datetime.timedelta(minutes=1),
                ),
            ),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.State(
                    type="SCHEDULED",
                    timestamp=now_dt + datetime.timedelta(minutes=1),
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

    @pytest.mark.filterwarnings(
        # SQLAlchemy will create an unawaited coroutine on attribute access failure
        "ignore:coroutine '.*' was never awaited"
    )
    async def test_read_flow_runs_with_only_one_column(self, flow_runs, db, session):
        # clear the session to erase cached versions of these flow runs and
        # force all data to be reloaded
        session.expunge_all()

        result = await models.flow_runs.read_flow_runs(
            session=session, columns=[db.FlowRun.id]
        )

        assert {r.id for r in result} == {fr.id for fr in flow_runs}

        # name and state_type were not loaded and raise an error
        # because the async session is closed
        for r in result:
            with pytest.raises(sa.exc.MissingGreenlet):
                r.name
            with pytest.raises(sa.exc.MissingGreenlet):
                r.state_type

    @pytest.mark.filterwarnings(
        # SQLAlchemy will create an unawaited coroutine on attribute access failure
        "ignore:coroutine '.*' was never awaited"
    )
    async def test_read_flow_runs_with_only_two_columns(self, flow_runs, db, session):
        # clear the session to erase cached versions of these flow runs and
        # force all data to be reloaded
        session.expunge_all()

        result = await models.flow_runs.read_flow_runs(
            session=session, columns=[db.FlowRun.id, db.FlowRun.name]
        )
        assert {r.id for r in result} == {fr.id for fr in flow_runs}
        assert {r.name for r in result} == {fr.name for fr in flow_runs}

        # state_type was not loaded and raises an error
        # because the async session is closed
        for r in result:
            with pytest.raises(sa.exc.MissingGreenlet):
                r.state_type

    async def test_read_flow_runs_filters_by_created_by(self, flow, session):
        creator_id_1 = uuid4()
        creator_id_2 = uuid4()
        created_by_1 = schemas.core.CreatedBy(
            id=creator_id_1, type="DEPLOYMENT", display_value="scheduled-deploy"
        )
        created_by_2 = schemas.core.CreatedBy(
            id=creator_id_2, type="AUTOMATION", display_value="my-automation"
        )
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, created_by=created_by_1),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, created_by=created_by_2),
        )
        flow_run_3 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),  # no created_by
        )

        # test type_ filter
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                created_by=schemas.filters.FlowRunFilterCreatedBy(type_=["DEPLOYMENT"])
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id}

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                created_by=schemas.filters.FlowRunFilterCreatedBy(
                    type_=["DEPLOYMENT", "AUTOMATION"]
                )
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id, flow_run_2.id}

        # test id_ filter
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                created_by=schemas.filters.FlowRunFilterCreatedBy(id_=[creator_id_1])
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id}

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                created_by=schemas.filters.FlowRunFilterCreatedBy(
                    id_=[creator_id_1, creator_id_2]
                )
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id, flow_run_2.id}

        # test is_null_ filter
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                created_by=schemas.filters.FlowRunFilterCreatedBy(is_null_=True)
            ),
        )
        assert {res.id for res in result} == {flow_run_3.id}

        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                created_by=schemas.filters.FlowRunFilterCreatedBy(is_null_=False)
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id, flow_run_2.id}


class TestReadFlowRunTaskRunDependencies:
    async def test_read_task_run_dependencies(self, flow_run, session):
        task_run_1 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id, task_key="key-1", dynamic_key="0"
            ),
        )

        task_run_2 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="key-2",
                dynamic_key="0",
                task_inputs=dict(x={TaskRunResult(id=task_run_1.id)}),
            ),
        )

        task_run_3 = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="key-3",
                dynamic_key="0",
                task_inputs=dict(x={TaskRunResult(id=task_run_2.id)}),
            ),
        )

        dependencies = await models.flow_runs.read_task_run_dependencies(
            session=session, flow_run_id=flow_run.id
        )

        # We do this because read_task_run_dependencies doesn't guarantee any ordering
        d1 = next(filter(lambda d: d.id == task_run_1.id, dependencies))
        d2 = next(filter(lambda d: d.id == task_run_2.id, dependencies))
        d3 = next(filter(lambda d: d.id == task_run_3.id, dependencies))

        assert len(dependencies) == 3

        fields = [
            "id",
            "name",
            "state",
            "expected_start_time",
            "start_time",
            "end_time",
            "total_run_time",
            "estimated_run_time",
        ]

        for field in fields:
            assert getattr(d1, field) == getattr(task_run_1, field)
            assert getattr(d2, field) == getattr(task_run_2, field)
            assert getattr(d3, field) == getattr(task_run_3, field)

        assert len(d1.upstream_dependencies) == 0
        assert len(d2.upstream_dependencies) == len(d3.upstream_dependencies) == 1
        assert d2.upstream_dependencies[0].id == d1.id
        assert d3.upstream_dependencies[0].id == d2.id

    async def test_read_task_run_dependencies_throws_error_if_does_not_exist(
        self, session
    ):
        with pytest.raises(ObjectNotFoundError):
            await models.flow_runs.read_task_run_dependencies(
                session=session, flow_run_id=uuid4()
            )


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

    async def test_delete_flow_run_with_data(self, flow, session, db):
        state_id = uuid4()
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                state=schemas.states.State(
                    id=state_id,
                    type="COMPLETED",
                    name="My Running State",
                    data={"hello": "world"},
                ),
            ),
        )
        assert flow_run.flow_id == flow.id
        assert flow_run.state.id == state_id

        # make sure the flow run exists
        assert await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run.id
        )

        assert await models.flow_runs.delete_flow_run(
            session=session, flow_run_id=flow_run.id
        )

        # make sure the flow run is deleted
        assert (
            await models.flow_runs.read_flow_run(
                session=session, flow_run_id=flow_run.id
            )
            is None
        )

    @pytest.mark.parametrize(
        "state_type,expected_slots",
        [
            ("PENDING", 0),
            ("RUNNING", 0),
            ("CANCELLING", 0),
            *[
                (type, 1)
                for type in schemas.states.StateType
                if type not in ("PENDING", "RUNNING", "CANCELLING")
            ],
        ],
    )
    async def test_delete_flow_run_with_deployment_concurrency_limit(
        self,
        session,
        flow,
        deployment_with_concurrency_limit,
        state_type,
        expected_slots,
    ):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                deployment_id=deployment_with_concurrency_limit.id,
                state=schemas.states.State(
                    type=state_type,
                ),
            ),
        )

        # Take one active slot
        await models.concurrency_limits_v2.bulk_increment_active_slots(
            session=session,
            concurrency_limit_ids=[
                deployment_with_concurrency_limit.concurrency_limit_id
            ],
            slots=1,
        )

        await session.commit()

        concurrency_limit = await models.concurrency_limits_v2.read_concurrency_limit(
            session=session,
            concurrency_limit_id=deployment_with_concurrency_limit.concurrency_limit_id,
        )
        assert concurrency_limit.active_slots == 0

        assert await models.flow_runs.delete_flow_run(
            session=session, flow_run_id=flow_run.id
        )

        await session.refresh(concurrency_limit)
        assert concurrency_limit.active_slots == expected_slots


class TestCountFlowRunsJoinFastPath:
    async def test_count_deployment_filter_correct(self, flow, session):
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="test-deployment-count",
                flow_id=flow.id,
            ),
        )
        await session.flush()

        # Two runs linked to the deployment, one unlinked.
        for _ in range(2):
            await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id, deployment_id=deployment.id
                ),
            )
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        await session.flush()

        count = await models.flow_runs.count_flow_runs(
            session=session,
            deployment_filter=schemas.filters.DeploymentFilter(
                id=schemas.filters.DeploymentFilterId(any_=[deployment.id])
            ),
        )
        assert count == 2

    async def test_count_work_pool_filter_correct(self, flow, session):
        work_pool = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(name="count-wp"),
        )
        work_queue = await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="count-wq"),
        )
        await session.flush()

        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, work_queue_id=work_queue.id),
        )
        # unlinked run — must not be counted
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        await session.flush()

        count = await models.flow_runs.count_flow_runs(
            session=session,
            work_pool_filter=schemas.filters.WorkPoolFilter(
                name=schemas.filters.WorkPoolFilterName(any_=[work_pool.name])
            ),
        )
        assert count == 1

    async def test_count_work_queue_filter_correct(self, flow, session):
        work_pool = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(name="count-wq-wp"),
        )
        work_queue = await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="count-wq-queue"),
        )
        await session.flush()

        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, work_queue_id=work_queue.id),
        )
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        await session.flush()

        count = await models.flow_runs.count_flow_runs(
            session=session,
            work_queue_filter=schemas.filters.WorkQueueFilter(
                id=schemas.filters.WorkQueueFilterId(any_=[work_queue.id])
            ),
        )
        assert count == 1

    async def test_count_flow_filter_correct(self, flow, session):
        flow2 = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="other-flow-for-count"),
        )
        await session.flush()

        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow2.id),
        )
        await session.flush()

        count = await models.flow_runs.count_flow_runs(
            session=session,
            flow_filter=schemas.filters.FlowFilter(
                id=schemas.filters.FlowFilterId(any_=[flow.id])
            ),
        )
        assert count == 1

    async def test_count_fast_path_with_flow_run_filter(self, flow, session):
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="fast-path-frfilter-dep",
                flow_id=flow.id,
            ),
        )
        await session.flush()

        fr1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, deployment_id=deployment.id),
        )
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, deployment_id=deployment.id),
        )
        await session.flush()

        count = await models.flow_runs.count_flow_runs(
            session=session,
            deployment_filter=schemas.filters.DeploymentFilter(
                id=schemas.filters.DeploymentFilterId(any_=[deployment.id])
            ),
            flow_run_filter=schemas.filters.FlowRunFilter(
                id=schemas.filters.FlowRunFilterId(any_=[fr1.id])
            ),
        )
        assert count == 1

    async def test_count_task_run_filter_alone_distinct_flow_runs(self, flow, session):
        """
        When only task_run_filter is active the else-branch routes through
        _apply_flow_run_filters. The result must equal the number of distinct
        flow runs that have a matching task run — NOT the number of task runs.

        Fails on pre-fix: if task_run_filter were silently dropped (criterion 2)
        the count would include flow runs without any task run. If the EXISTS
        approach were replaced by a plain join without DISTINCT the count could
        be inflated (criterion 9).
        """
        # 3 flow runs, each with 2 task runs.
        all_task_run_ids = []
        for i in range(3):
            fr = await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(flow_id=flow.id),
            )
            for j in range(2):
                tr = await models.task_runs.create_task_run(
                    session=session,
                    task_run=schemas.actions.TaskRunCreate(
                        flow_run_id=fr.id,
                        task_key=f"task-distinct-{i}-{j}",
                        dynamic_key=str(j),
                    ),
                )
                all_task_run_ids.append(tr.id)

        # 2 flow runs without any task run — must not be included.
        for _ in range(2):
            await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(flow_id=flow.id),
            )
        await session.flush()

        # Filter matches all 6 task runs across 3 flow runs.
        count = await models.flow_runs.count_flow_runs(
            session=session,
            task_run_filter=schemas.filters.TaskRunFilter(
                id=schemas.filters.TaskRunFilterId(any_=all_task_run_ids)
            ),
        )
        # 3 distinct flow runs, not 6 (2 task runs × 3 flow runs).
        assert count == 3

    async def test_count_deployment_and_task_run_filter_p1(self, flow, session):
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="p1-deployment-taskrun",
                flow_id=flow.id,
            ),
        )
        await session.flush()

        # Run WITH the deployment AND a matching task run.
        fr_match = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, deployment_id=deployment.id),
        )
        tr_match = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.actions.TaskRunCreate(
                flow_run_id=fr_match.id, task_key="p1-task", dynamic_key="0"
            ),
        )

        # Run WITH the deployment but WITHOUT any task run — must NOT be counted.
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, deployment_id=deployment.id),
        )

        # Run WITHOUT the deployment but WITH a matching task run — must NOT be counted.
        fr_no_dep = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.actions.TaskRunCreate(
                flow_run_id=fr_no_dep.id, task_key="p1-task-nodep", dynamic_key="0"
            ),
        )
        await session.flush()

        count = await models.flow_runs.count_flow_runs(
            session=session,
            deployment_filter=schemas.filters.DeploymentFilter(
                id=schemas.filters.DeploymentFilterId(any_=[deployment.id])
            ),
            task_run_filter=schemas.filters.TaskRunFilter(
                id=schemas.filters.TaskRunFilterId(any_=[tr_match.id])
            ),
        )
        # Only fr_match satisfies both filters.
        assert count == 1

    async def test_count_work_pool_and_task_run_filter_p1(self, flow, session):
        work_pool = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(name="p1-wp"),
        )
        work_queue = await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="p1-wq"),
        )
        await session.flush()

        # Run with work_pool AND matching task run.
        fr_match = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, work_queue_id=work_queue.id),
        )
        tr_match = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.actions.TaskRunCreate(
                flow_run_id=fr_match.id, task_key="p1-wp-task", dynamic_key="0"
            ),
        )

        # Run with work_pool but NO matching task run — must NOT be counted.
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, work_queue_id=work_queue.id),
        )

        # Run WITHOUT work_pool but WITH matching task run — must NOT be counted.
        fr_no_wp = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.actions.TaskRunCreate(
                flow_run_id=fr_no_wp.id,
                task_key="p1-wp-task-no-wp",
                dynamic_key="0",
            ),
        )
        await session.flush()

        count = await models.flow_runs.count_flow_runs(
            session=session,
            work_pool_filter=schemas.filters.WorkPoolFilter(
                name=schemas.filters.WorkPoolFilterName(any_=[work_pool.name])
            ),
            task_run_filter=schemas.filters.TaskRunFilter(
                id=schemas.filters.TaskRunFilterId(any_=[tr_match.id])
            ),
        )
        assert count == 1

    async def test_count_work_queue_and_task_run_filter_p1(self, flow, session):
        work_pool = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(name="p1-wq-wp"),
        )
        work_queue = await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="p1-wq-queue"),
        )
        await session.flush()

        fr_match = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, work_queue_id=work_queue.id),
        )
        tr_match = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.actions.TaskRunCreate(
                flow_run_id=fr_match.id, task_key="p1-wq-task", dynamic_key="0"
            ),
        )

        # work_queue but no task run.
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, work_queue_id=work_queue.id),
        )

        # task run but no work_queue.
        fr_no_wq = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.actions.TaskRunCreate(
                flow_run_id=fr_no_wq.id,
                task_key="p1-wq-task-no-wq",
                dynamic_key="0",
            ),
        )
        await session.flush()

        count = await models.flow_runs.count_flow_runs(
            session=session,
            work_queue_filter=schemas.filters.WorkQueueFilter(
                id=schemas.filters.WorkQueueFilterId(any_=[work_queue.id])
            ),
            task_run_filter=schemas.filters.TaskRunFilter(
                id=schemas.filters.TaskRunFilterId(any_=[tr_match.id])
            ),
        )
        assert count == 1

    async def test_count_equals_read_length_deployment_filter(self, flow, session):
        """
        count_flow_runs(deployment_filter=F) must equal len(read_flow_runs(deployment_filter=F)).

        Fails on pre-fix if the two paths (count's JOIN branch vs. read's EXISTS
        branch) disagree on which rows they match — a regression indicator.
        """
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="pagination-consistency-dep",
                flow_id=flow.id,
            ),
        )
        await session.flush()

        for _ in range(3):
            await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id, deployment_id=deployment.id
                ),
            )
        # Unlinked — must be excluded from both.
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        await session.flush()

        dep_filter = schemas.filters.DeploymentFilter(
            id=schemas.filters.DeploymentFilterId(any_=[deployment.id])
        )

        count = await models.flow_runs.count_flow_runs(
            session=session,
            deployment_filter=dep_filter,
        )
        runs = await models.flow_runs.read_flow_runs(
            session=session,
            deployment_filter=dep_filter,
        )
        assert count == len(runs) == 3

    async def test_count_equals_read_length_work_pool_filter(self, flow, session):
        """
        count_flow_runs(work_pool_filter=F) must equal len(read_flow_runs(work_pool_filter=F)).
        """
        work_pool = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(name="pag-wp"),
        )
        work_queue = await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="pag-wq"),
        )
        await session.flush()

        for _ in range(4):
            await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id, work_queue_id=work_queue.id
                ),
            )
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        await session.flush()

        wp_filter = schemas.filters.WorkPoolFilter(
            name=schemas.filters.WorkPoolFilterName(any_=[work_pool.name])
        )

        count = await models.flow_runs.count_flow_runs(
            session=session,
            work_pool_filter=wp_filter,
        )
        runs = await models.flow_runs.read_flow_runs(
            session=session,
            work_pool_filter=wp_filter,
        )
        assert count == len(runs) == 4

    async def test_count_equals_read_length_deployment_and_work_pool_combined(
        self, flow, session
    ):
        """
        count_flow_runs(deployment_filter=F, work_pool_filter=G) must equal
        len(read_flow_runs(deployment_filter=F, work_pool_filter=G)).

        Fails on pre-fix if count's JOIN fast-path and read's EXISTS path disagree
        on which rows satisfy the combined filter.
        """
        work_pool = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(name="a1-parity-wp"),
        )
        work_queue = await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="a1-parity-wq"),
        )
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="a1-parity-dep",
                flow_id=flow.id,
            ),
        )
        await session.flush()

        for _ in range(2):
            await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id,
                    deployment_id=deployment.id,
                    work_queue_id=work_queue.id,
                ),
            )
        # Only deployment — must be excluded from both count and read.
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, deployment_id=deployment.id),
        )
        await session.flush()

        dep_filter = schemas.filters.DeploymentFilter(
            id=schemas.filters.DeploymentFilterId(any_=[deployment.id])
        )
        wp_filter = schemas.filters.WorkPoolFilter(
            name=schemas.filters.WorkPoolFilterName(any_=[work_pool.name])
        )

        count = await models.flow_runs.count_flow_runs(
            session=session,
            deployment_filter=dep_filter,
            work_pool_filter=wp_filter,
        )
        runs = await models.flow_runs.read_flow_runs(
            session=session,
            deployment_filter=dep_filter,
            work_pool_filter=wp_filter,
        )
        assert count == len(runs) == 2

    async def test_count_no_filter_returns_all(self, flow, session):
        baseline = await models.flow_runs.count_flow_runs(session=session)

        for _ in range(5):
            await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(flow_id=flow.id),
            )
        await session.flush()

        count = await models.flow_runs.count_flow_runs(session=session)
        assert count == baseline + 5

    async def test_count_nonexistent_deployment_returns_zero(self, session):
        count = await models.flow_runs.count_flow_runs(
            session=session,
            deployment_filter=schemas.filters.DeploymentFilter(
                id=schemas.filters.DeploymentFilterId(any_=[uuid4()])
            ),
        )
        assert count == 0

    async def test_count_flow_filter_and_task_run_filter_combined(self, flow, session):
        """
        When flow_filter and task_run_filter are both provided the guard
        condition routes to the else-branch (because task_run_filter is set).
        The result must honour BOTH filters via _apply_flow_run_filters.

        Fails on pre-fix if: (a) the else-branch drops either filter, or
        (b) the combined EXISTS logic in _apply_flow_run_filters has a bug.
        """
        flow2 = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="flow-filter-task-run-combo"),
        )
        await session.flush()

        # Matches both: flow=flow AND has matching task run.
        fr_match = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        tr = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.actions.TaskRunCreate(
                flow_run_id=fr_match.id,
                task_key="combo-task",
                dynamic_key="0",
            ),
        )

        # Matches flow filter but no matching task run.
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )

        # Matches task run filter but wrong flow.
        fr_wrong_flow = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow2.id),
        )
        await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.actions.TaskRunCreate(
                flow_run_id=fr_wrong_flow.id,
                task_key="combo-task-wrong-flow",
                dynamic_key="0",
            ),
        )
        await session.flush()

        count = await models.flow_runs.count_flow_runs(
            session=session,
            flow_filter=schemas.filters.FlowFilter(
                id=schemas.filters.FlowFilterId(any_=[flow.id])
            ),
            task_run_filter=schemas.filters.TaskRunFilter(
                id=schemas.filters.TaskRunFilterId(any_=[tr.id])
            ),
        )
        assert count == 1

    async def test_count_equals_read_length_work_queue_filter(self, flow, session):
        """
        count_flow_runs(work_queue_filter=F) must equal
        len(read_flow_runs(work_queue_filter=F)).

        Fails on pre-fix if count_flow_runs's JOIN fast-path and
        read_flow_runs's EXISTS path disagree on which rows match —
        which would cause pagination (count) and listing (read) to
        report different totals for the same filter.
        """
        work_pool = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(name="pag-wq-wp"),
        )
        work_queue = await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="pag-wq-queue"),
        )
        await session.flush()

        for _ in range(3):
            await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id, work_queue_id=work_queue.id
                ),
            )
        # Unlinked run — must be excluded from both count and read.
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        await session.flush()

        wq_filter = schemas.filters.WorkQueueFilter(
            id=schemas.filters.WorkQueueFilterId(any_=[work_queue.id])
        )

        count = await models.flow_runs.count_flow_runs(
            session=session,
            work_queue_filter=wq_filter,
        )
        runs = await models.flow_runs.read_flow_runs(
            session=session,
            work_queue_filter=wq_filter,
        )
        assert count == len(runs)
        assert count == 3

    async def test_count_equals_read_length_flow_filter(self, flow, session):
        """
        count_flow_runs(flow_filter=F) must equal
        len(read_flow_runs(flow_filter=F)).

        Fails on pre-fix if the JOIN fast-path in count_flow_runs and
        the EXISTS path in read_flow_runs disagree on which rows match.
        """
        flow2 = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="pag-flow-filter-other"),
        )
        await session.flush()

        for _ in range(2):
            await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(flow_id=flow.id),
            )
        # Run on a different flow — must be excluded from both.
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow2.id),
        )
        await session.flush()

        fl_filter = schemas.filters.FlowFilter(
            id=schemas.filters.FlowFilterId(any_=[flow.id])
        )

        count = await models.flow_runs.count_flow_runs(
            session=session,
            flow_filter=fl_filter,
        )
        runs = await models.flow_runs.read_flow_runs(
            session=session,
            flow_filter=fl_filter,
        )
        assert count == len(runs)
        assert count == 2

    async def test_count_equals_read_work_queue_and_work_pool_combined(
        self, flow, session
    ):
        """
        count_flow_runs(wq_filter, wp_filter) must equal
        len(read_flow_runs(wq_filter, wp_filter)) when actual matching rows exist.

        The SQL-structure test uses non-existent IDs (trivially count=0) so it
        cannot detect a wrong FK in the JOIN chain.  This test provides real rows
        so any semantic divergence between count's JOIN path and read's EXISTS
        path is caught.

        Fails on pre-fix: the fast path did not exist.  On the current code, a
        wrong JOIN condition (e.g., WorkPool joined on deployment_id) would
        return 0 here but 3 from read_flow_runs.
        """
        work_pool = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(name="parity-wqwp-wp"),
        )
        work_queue = await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="parity-wqwp-wq"),
        )
        await session.flush()

        for _ in range(3):
            await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id, work_queue_id=work_queue.id
                ),
            )
        # Run with no work_queue — must be excluded from both count and read.
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        await session.flush()

        wq_filter = schemas.filters.WorkQueueFilter(
            id=schemas.filters.WorkQueueFilterId(any_=[work_queue.id])
        )
        wp_filter = schemas.filters.WorkPoolFilter(
            name=schemas.filters.WorkPoolFilterName(any_=[work_pool.name])
        )

        count = await models.flow_runs.count_flow_runs(
            session=session,
            work_queue_filter=wq_filter,
            work_pool_filter=wp_filter,
        )
        runs = await models.flow_runs.read_flow_runs(
            session=session,
            work_queue_filter=wq_filter,
            work_pool_filter=wp_filter,
        )
        assert count == len(runs) == 3

    async def test_count_equals_read_flow_and_deployment_combined(self, flow, session):
        """
        count_flow_runs(flow_filter=F, deployment_filter=D) must equal
        len(read_flow_runs(flow_filter=F, deployment_filter=D)).

        Fails on pre-fix if count's JOIN fast-path and read's EXISTS path
        disagree on which rows satisfy the intersection of two independent
        filter dimensions.
        """
        flow2 = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="parity-fl-dep-flow2"),
        )
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="parity-fl-dep-dep",
                flow_id=flow.id,
            ),
        )
        await session.flush()

        # Run satisfying both filters.
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, deployment_id=deployment.id),
        )
        # Satisfies only flow_filter (no deployment) — must be excluded.
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        # Satisfies only deployment_filter (wrong flow) — must be excluded.
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow2.id, deployment_id=deployment.id
            ),
        )
        await session.flush()

        fl_filter = schemas.filters.FlowFilter(
            id=schemas.filters.FlowFilterId(any_=[flow.id])
        )
        dep_filter = schemas.filters.DeploymentFilter(
            id=schemas.filters.DeploymentFilterId(any_=[deployment.id])
        )

        count = await models.flow_runs.count_flow_runs(
            session=session,
            flow_filter=fl_filter,
            deployment_filter=dep_filter,
        )
        runs = await models.flow_runs.read_flow_runs(
            session=session,
            flow_filter=fl_filter,
            deployment_filter=dep_filter,
        )
        assert count == len(runs) == 1

    async def test_count_all_four_fast_path_filters_intersection(self, flow, session):
        """
        count_flow_runs with flow_filter + deployment_filter +
        work_queue_filter + work_pool_filter (no task_run_filter) must
        return only the flow runs that satisfy ALL four constraints.

        Fails on pre-fix if the fast-path JOINs for all four filters
        were not combined — e.g. if only some JOINs were applied, runs
        satisfying 3 of 4 constraints would be over-counted.
        """
        work_pool = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(name="all4-wp"),
        )
        work_queue = await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=schemas.actions.WorkQueueCreate(name="all4-wq"),
        )
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="all4-dep",
                flow_id=flow.id,
            ),
        )
        await session.flush()

        # Satisfies all four: correct flow + deployment + work_queue (+ work_pool).
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                deployment_id=deployment.id,
                work_queue_id=work_queue.id,
            ),
        )

        # Only deployment + work_queue (wrong flow — different Flow object).
        flow_other = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="all4-other-flow"),
        )
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow_other.id,
                deployment_id=deployment.id,
                work_queue_id=work_queue.id,
            ),
        )

        # Only flow + work_queue (no deployment).
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                work_queue_id=work_queue.id,
            ),
        )

        # Only flow + deployment (no work_queue -> not on work_pool).
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                deployment_id=deployment.id,
            ),
        )
        await session.flush()

        all4_flow_filter = schemas.filters.FlowFilter(
            id=schemas.filters.FlowFilterId(any_=[flow.id])
        )
        all4_dep_filter = schemas.filters.DeploymentFilter(
            id=schemas.filters.DeploymentFilterId(any_=[deployment.id])
        )
        all4_wq_filter = schemas.filters.WorkQueueFilter(
            id=schemas.filters.WorkQueueFilterId(any_=[work_queue.id])
        )
        all4_wp_filter = schemas.filters.WorkPoolFilter(
            name=schemas.filters.WorkPoolFilterName(any_=[work_pool.name])
        )

        count = await models.flow_runs.count_flow_runs(
            session=session,
            flow_filter=all4_flow_filter,
            deployment_filter=all4_dep_filter,
            work_queue_filter=all4_wq_filter,
            work_pool_filter=all4_wp_filter,
        )
        runs = await models.flow_runs.read_flow_runs(
            session=session,
            flow_filter=all4_flow_filter,
            deployment_filter=all4_dep_filter,
            work_queue_filter=all4_wq_filter,
            work_pool_filter=all4_wp_filter,
        )
        assert count == len(runs) == 1

    async def test_count_empty_deployment_filter_behavior(self, flow, session):
        """
        DeploymentFilter() with no sub-fields set is truthy in Python, so
        it triggers the JOIN fast-path. The JOIN is INNER JOIN on
        deployment_id, and as_sql_filter() returns sa.true() (no WHERE
        restriction beyond the join). Therefore the count equals the number
        of flow runs that have a non-null deployment_id with a matching
        Deployment row — flow runs without a deployment are excluded.

        Fails on pre-fix if the fast-path is absent: the else-branch calls
        _apply_flow_run_filters which handles an empty DeploymentFilter via
        a correlated EXISTS with sa.true(). If that path diverged from the
        JOIN result (e.g. included null-deployment_id runs) the count would
        be wrong.

        On the current code this pins the guarantee: an empty
        DeploymentFilter() counts exactly the runs that have a matching
        deployment row, not all runs.
        """
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="empty-filter-dep",
                flow_id=flow.id,
            ),
        )
        await session.flush()

        # Run linked to a deployment — must be counted.
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, deployment_id=deployment.id),
        )
        # Run with no deployment — must NOT be counted.
        await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        await session.flush()

        count = await models.flow_runs.count_flow_runs(
            session=session,
            deployment_filter=schemas.filters.DeploymentFilter(),
        )
        assert count == 1

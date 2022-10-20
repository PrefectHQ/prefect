from uuid import uuid4

import pendulum
import pytest
import sqlalchemy as sa

from prefect.orion import models, schemas
from prefect.orion.exceptions import ObjectNotFoundError
from prefect.orion.schemas.core import TaskRunResult


class TestCreateFlowRun:
    async def test_create_flow_run(self, flow, session):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id),
        )
        assert flow_run.flow_id == flow.id

    async def test_create_flow_run_with_infrastructure(
        self, flow, session, infrastructure_document_id
    ):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                infrastructure_document_id=infrastructure_document_id,
            ),
        )
        assert flow_run.infrastructure_document_id == infrastructure_document_id

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
                manifest_path="file.json",
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
            ),
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
        flow_run_1 = await models.flow_runs.create_flow_run(
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
        flow_run_3 = await models.flow_runs.create_flow_run(
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
        flow_run_3 = await models.flow_runs.create_flow_run(
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
        now = pendulum.now()
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                start_time=now.subtract(minutes=1),
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
                start_time=now,
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
                start_time=now.add(minutes=1),
                state=schemas.states.State(
                    type="COMPLETED",
                    name="My Completed State",
                ),
            ),
        )
        flow_run_4 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
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
                start_time=schemas.filters.FlowRunFilterStartTime(
                    before_=now.subtract(seconds=1)
                )
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id}

        # after_
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                start_time=schemas.filters.FlowRunFilterStartTime(after_=now)
            ),
        )
        assert {res.id for res in result} == {flow_run_2.id, flow_run_3.id}

        # before_ AND after_
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                start_time=schemas.filters.FlowRunFilterStartTime(
                    before_=now.add(minutes=10), after_=now.add(seconds=1)
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
        now = pendulum.now()
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                next_scheduled_start_time=now.subtract(minutes=1),
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
                next_scheduled_start_time=now,
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
                next_scheduled_start_time=now.add(minutes=1),
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
                    before_=now.subtract(seconds=1)
                )
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id}

        # after_
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                next_scheduled_start_time=schemas.filters.FlowRunFilterNextScheduledStartTime(
                    after_=now
                )
            ),
        )
        assert {res.id for res in result} == {flow_run_2.id, flow_run_3.id}

        # before_ AND after_
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                next_scheduled_start_time=schemas.filters.FlowRunFilterNextScheduledStartTime(
                    before_=now.add(minutes=10), after_=now.add(seconds=1)
                )
            ),
        )
        assert {res.id for res in result} == {flow_run_3.id}

    async def test_read_flow_runs_filters_by_expected_start_time(self, flow, session):
        now = pendulum.now()
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                expected_start_time=now.subtract(minutes=1),
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
                expected_start_time=now,
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
                expected_start_time=now.add(minutes=1),
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
                    before_=now.subtract(seconds=1)
                )
            ),
        )
        assert {res.id for res in result} == {flow_run_1.id}

        # after_
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                expected_start_time=schemas.filters.FlowRunFilterExpectedStartTime(
                    after_=now
                )
            ),
        )
        assert {res.id for res in result} == {flow_run_2.id, flow_run_3.id}

        # before_ AND after_
        result = await models.flow_runs.read_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                expected_start_time=schemas.filters.FlowRunFilterExpectedStartTime(
                    before_=now.add(minutes=10), after_=now.add(seconds=1)
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
                manifest_path="file.json",
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
        d1 = next(filter(lambda d: d["id"] == task_run_1.id, dependencies))
        d2 = next(filter(lambda d: d["id"] == task_run_2.id, dependencies))
        d3 = next(filter(lambda d: d["id"] == task_run_3.id, dependencies))

        assert len(dependencies) == 3
        assert d1["id"] == task_run_1.id
        assert d2["id"] == task_run_2.id
        assert d3["id"] == task_run_3.id

        assert len(d1["upstream_dependencies"]) == 0
        assert len(d2["upstream_dependencies"]) == len(d3["upstream_dependencies"]) == 1
        assert d2["upstream_dependencies"][0].id == d1["id"]
        assert d3["upstream_dependencies"][0].id == d2["id"]

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

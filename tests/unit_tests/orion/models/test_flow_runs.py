import sqlalchemy as sa
import pytest
from uuid import uuid4

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
        with pytest.raises(sa.exc.IntegrityError):
            await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(flow_id=flow.id, idempotency_key="test"),
            )

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

    async def test_create_flow_run_with_deployment_id(self, flow, session):

        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(name="", flow_id=flow.id),
        )
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(flow_id=flow.id, deployment_id=deployment.id),
        )
        assert flow_run.flow_id == flow.id
        assert flow_run.deployment_id == deployment.id


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
        return [flow_run_1, flow_run_2, flow_run_3]

    async def test_read_flow_runs(self, flow_runs, session):
        read_flow_runs = await models.flow_runs.read_flow_runs(session=session)
        assert len(read_flow_runs) == 3

    async def test_read_flow_runs_with_flow_id(self, flow, flow_runs, session):
        read_flow_runs = await models.flow_runs.read_flow_runs(
            session=session, flow_id=flow.id
        )
        assert len(read_flow_runs) == 2
        assert all([r.flow_id == flow.id for r in read_flow_runs])

    async def test_read_flow_runs_applies_limit(self, flow_runs, session):
        read_flow_runs = await models.flow_runs.read_flow_runs(session=session, limit=1)
        assert len(read_flow_runs) == 1

    async def test_read_flow_runs_returns_empty_list(self, session):
        read_flow_runs = await models.flow_runs.read_flow_runs(session=session)
        assert len(read_flow_runs) == 0


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

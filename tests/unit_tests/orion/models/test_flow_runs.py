import sqlalchemy as sa
import pytest
from uuid import uuid4

import pytest
import sqlalchemy as sa

from prefect.orion import models, schemas


class TestCreateFlowRun:
    async def test_create_flow_run(self, flow, database_session):
        flow_run = await models.flow_runs.create_flow_run(
            session=database_session,
            flow_run=schemas.actions.FlowRunCreate(flow_id=flow.id),
        )
        assert flow_run.flow_id == flow.id

    async def test_create_multiple_flow_runs(self, flow, database_session):
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=database_session,
            flow_run=schemas.actions.FlowRunCreate(flow_id=flow.id),
        )

        flow_run_2 = await models.flow_runs.create_flow_run(
            session=database_session,
            flow_run=schemas.actions.FlowRunCreate(flow_id=flow.id),
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
        self, flow, database_session
    ):
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=database_session,
            flow_run=schemas.actions.FlowRunCreate(flow_id=flow.id),
        )

        with pytest.raises(sa.exc.IntegrityError):
            await models.flow_runs.create_flow_run(
                session=database_session,
                flow_run=schemas.core.FlowRun(id=flow_run_1.id, flow_id=flow.id),
            )

    async def test_create_flow_run_with_idempotency_key(self, flow, database_session):
        flow_run = await models.flow_runs.create_flow_run(
            session=database_session,
            flow_run=schemas.actions.FlowRunCreate(
                flow_id=flow.id, idempotency_key="test"
            ),
        )
        assert flow_run.idempotency_key == "test"

    async def test_create_flow_run_with_existing_idempotency_key(
        self, flow, database_session
    ):
        flow_run = await models.flow_runs.create_flow_run(
            session=database_session,
            flow_run=schemas.actions.FlowRunCreate(
                flow_id=flow.id, idempotency_key="test"
            ),
        )
        with pytest.raises(sa.exc.IntegrityError):
            await models.flow_runs.create_flow_run(
                session=database_session,
                flow_run=schemas.actions.FlowRunCreate(
                    flow_id=flow.id, idempotency_key="test"
                ),
            )

    async def test_create_flow_run_with_existing_idempotency_key_of_a_different_flow(
        self, flow, database_session
    ):
        flow2 = models.orm.Flow(name="another flow")
        database_session.add(flow2)
        await database_session.flush()

        flow_run = await models.flow_runs.create_flow_run(
            session=database_session,
            flow_run=schemas.actions.FlowRunCreate(
                flow_id=flow.id, idempotency_key="test"
            ),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=database_session,
            flow_run=schemas.actions.FlowRunCreate(
                flow_id=flow2.id, idempotency_key="test"
            ),
        )

        assert flow_run.id != flow_run_2.id

    async def test_create_flow_run_succeeds(self, flow, database_session):
        flow_run = await models.flow_runs.create_flow_run(
            session=database_session, flow_run=dict(flow_id=flow.id, flow_version="0.1")
        )
        assert flow_run.flow_id == flow.id
        assert flow_run.flow_version == "0.1"


class TestReadFlowRun:
    async def test_read_flow_run(self, flow, database_session):
        # create a flow run to read
        flow_run = await models.flow_runs.create_flow_run(
            session=database_session,
            flow_run=dict(flow_id=flow.id),
        )

        read_flow_run = await models.flow_runs.read_flow_run(
            session=database_session, flow_run_id=flow_run.id
        )
        assert flow_run == read_flow_run

    async def test_read_flow_run_returns_none_if_does_not_exist(self, database_session):
        result = await models.flow_runs.read_flow_run(
            session=database_session, flow_run_id=uuid4()
        )
        assert result is None


class TestReadFlowRuns:
    @pytest.fixture
    async def flow_runs(self, flow, database_session):
        await database_session.execute(sa.delete(models.orm.FlowRun))

        flow_2 = await models.flows.create_flow(
            session=database_session,
            flow=schemas.actions.FlowCreate(name="another-test"),
        )

        flow_run_1 = await models.flow_runs.create_flow_run(
            session=database_session, flow_run=dict(flow_id=flow.id)
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=database_session,
            flow_run=schemas.actions.FlowRunCreate(flow_id=flow.id),
        )
        flow_run_3 = await models.flow_runs.create_flow_run(
            session=database_session,
            flow_run=schemas.actions.FlowRunCreate(flow_id=flow_2.id),
        )
        return [flow_run_1, flow_run_2, flow_run_3]

    async def test_read_flow_runs(self, flow_runs, database_session):
        read_flow_runs = await models.flow_runs.read_flow_runs(session=database_session)
        assert len(read_flow_runs) == 3

    async def test_read_flow_runs_with_flow_id(self, flow, flow_runs, database_session):
        read_flow_runs = await models.flow_runs.read_flow_runs(
            session=database_session, flow_id=flow.id
        )
        assert len(read_flow_runs) == 2
        assert all([r.flow_id == flow.id for r in read_flow_runs])

    async def test_read_flow_runs_applies_limit(self, flow_runs, database_session):
        read_flow_runs = await models.flow_runs.read_flow_runs(
            session=database_session, limit=1
        )
        assert len(read_flow_runs) == 1

    async def test_read_flow_runs_returns_empty_list(self, database_session):
        read_flow_runs = await models.flow_runs.read_flow_runs(session=database_session)
        assert len(read_flow_runs) == 0


class TestDeleteFlowRun:
    async def test_delete_flow_run(self, flow, database_session):
        # create a flow run to delete
        flow_run = await models.flow_runs.create_flow_run(
            session=database_session,
            flow_run=dict(flow_id=flow.id),
        )

        assert await models.flow_runs.delete_flow_run(
            session=database_session, flow_run_id=flow_run.id
        )

        # make sure the flow run is deleted
        result = await models.flow_runs.read_flow_run(
            session=database_session, flow_run_id=flow_run.id
        )
        assert result is None

    async def test_delete_flow_run_returns_false_if_does_not_exist(
        self, database_session
    ):
        result = await models.flow_runs.delete_flow_run(
            session=database_session, flow_run_id=uuid4()
        )
        assert result is False

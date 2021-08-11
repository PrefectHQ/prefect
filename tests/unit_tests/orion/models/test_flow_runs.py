from uuid import uuid4

import pytest
import sqlalchemy as sa

from prefect.orion import models, schemas


class TestCreateFlowRun:
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
            session=database_session, flow_run=dict(flow_id=flow.id)
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
        flow_run_0 = await models.flow_runs.create_flow_run(
            session=database_session, flow_run=dict(flow_id=flow.id)
        )
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=database_session, flow_run=dict(flow_id=flow.id)
        )
        return [flow_run_0, flow_run_1]

    async def test_read_flow_runs(self, flow_runs, database_session):
        read_flow_runs = await models.flow_runs.read_flow_runs(session=database_session)
        assert len(read_flow_runs) == len(flow_runs)

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
            session=database_session, flow_run=dict(flow_id=flow.id)
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
        assert not result

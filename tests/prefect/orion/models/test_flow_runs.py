import uuid
import pytest
from uuid import uuid4
from prefect.orion import models
from prefect.orion.models.flow_runs import read_flow_run


class TestCreateFlowRun:
    async def test_create_flow_run_succeeds(self, database_session):
        fake_flow_id = uuid4()
        flow_run = await models.flow_runs.create_flow_run(
            session=database_session, flow_id=fake_flow_id, flow_version="0.1"
        )
        assert flow_run.flow_id == fake_flow_id
        assert flow_run.flow_version == "0.1"


class TestReadFlowRun:
    async def test_read_flow_run(self, database_session):
        # create a flow run to read
        flow_run = await models.flow_runs.create_flow_run(
            session=database_session, flow_id=uuid4(), flow_version="0.1"
        )

        read_flow_run = await models.flow_runs.read_flow_run(
            session=database_session, id=flow_run.id
        )
        assert flow_run == read_flow_run

    async def test_read_flow_run_returns_none_if_does_not_exist(self, database_session):
        assert (
            await models.flow_runs.read_flow_run(session=database_session, id=uuid4())
        ) is None


class TestReadFlowRuns:
    @pytest.fixture
    async def flow_runs(self, database_session):
        flow_run_0 = await models.flow_runs.create_flow_run(
            session=database_session, flow_id=uuid4(), flow_version="0.1"
        )
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=database_session, flow_id=uuid4(), flow_version="0.2"
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
    async def test_delete_flow_run(self, database_session):
        # create a flow run to delete
        flow_run = await models.flow_runs.create_flow_run(
            session=database_session, flow_id=uuid4(), flow_version="0.1"
        )

        assert await models.flow_runs.delete_flow_run(
            session=database_session, id=flow_run.id
        )

        # make sure the flow run is deleted
        assert (
            await models.flow_runs.read_flow_run(
                session=database_session, id=flow_run.id
            )
        ) is None

    async def test_delete_flow_run_returns_false_if_does_not_exist(
        self, database_session
    ):
        assert not (
            await models.flow_runs.delete_flow_run(session=database_session, id=uuid4())
        )

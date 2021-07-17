import pytest
from uuid import uuid4
from prefect.orion import models


class TestCreateFlow:
    async def test_create_flow_succeeds(self, database_session):
        flow = await models.flows.create_flow(session=database_session, name="my-flow")
        assert flow.name == "my-flow"
        assert flow.id

    async def test_create_flow_returns_records_if_already_exists(
        self, database_session
    ):
        # create a flow
        flow = await models.flows.create_flow(session=database_session, name="my-flow")
        assert flow.name == "my-flow"
        assert flow.id

        # try to create the same flow, it should return the existing
        same_flow = await models.flows.create_flow(
            session=database_session, name="my-flow"
        )
        assert same_flow.name == flow.name
        assert same_flow.id == flow.id


class TestReadFlow:
    async def test_read_flow(self, database_session):
        # create a flow to read
        flow = await models.flows.create_flow(session=database_session, name="my-flow")
        assert flow.name == "my-flow"

        read_flow = await models.flows.read_flow(session=database_session, id=flow.id)
        assert flow.id == read_flow.id
        assert flow.name == read_flow.name

    async def test_read_flow_returns_none_if_does_not_exist(self, database_session):
        assert (
            await models.flows.read_flow(session=database_session, id=uuid4())
        ) is None


class TestReadFlows:
    @pytest.fixture
    async def flows(self, database_session):
        flow_1 = await models.flows.create_flow(
            session=database_session, name="my-flow-1"
        )
        flow_2 = await models.flows.create_flow(
            session=database_session, name="my-flow-2"
        )
        return [flow_1, flow_2]

    async def test_read_flows(self, flows, database_session):
        read_flows = await models.flows.read_flows(session=database_session)
        assert len(read_flows) == len(flows)

    async def test_read_flows_applies_limit(self, flows, database_session):
        read_flows = await models.flows.read_flows(session=database_session, limit=1)
        assert len(read_flows) == 1

    async def test_read_flows_returns_empty_list(self, database_session):
        read_flows = await models.flows.read_flows(session=database_session)
        assert len(read_flows) == 0

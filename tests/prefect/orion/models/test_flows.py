from uuid import uuid4

import pytest
import sqlalchemy as sa

from prefect.orion import models, schemas


class TestCreateFlow:
    async def test_create_flow_succeeds(self, database_session):
        flow = await models.flows.create_flow(
            session=database_session, flow=schemas.actions.FlowCreate(name="my-flow")
        )
        assert flow.name == "my-flow"
        assert flow.id

    async def test_create_flow_raises_if_already_exists(self, database_session):
        # create a flow
        flow = await models.flows.create_flow(
            session=database_session, flow=schemas.actions.FlowCreate(name="my-flow")
        )
        assert flow.name == "my-flow"
        assert flow.id

        # try to create the same flow

        with pytest.raises(sa.exc.IntegrityError):
            await models.flows.create_flow(
                session=database_session,
                flow=schemas.actions.FlowCreate(name="my-flow"),
            )


class TestReadFlow:
    async def test_read_flow(self, database_session):
        # create a flow to read
        flow = await models.flows.create_flow(
            session=database_session, flow=schemas.actions.FlowCreate(name="my-flow")
        )
        assert flow.name == "my-flow"

        read_flow = await models.flows.read_flow(session=database_session, id=flow.id)
        assert flow.id == read_flow.id
        assert flow.name == read_flow.name

    async def test_read_flow_returns_none_if_does_not_exist(self, database_session):
        result = await models.flows.read_flow(session=database_session, id=str(uuid4()))
        assert result is None


class TestReadFlowByName:
    async def test_read_flow(self, database_session):
        # create a flow to read
        flow = await models.flows.create_flow(
            session=database_session, flow=schemas.actions.FlowCreate(name="my-flow")
        )
        assert flow.name == "my-flow"

        read_flow = await models.flows.read_flow_by_name(
            session=database_session, name=flow.name
        )
        assert flow.id == read_flow.id
        assert flow.name == read_flow.name

    async def test_read_flow_returns_none_if_does_not_exist(self, database_session):
        result = await models.flows.read_flow_by_name(
            session=database_session, name=str(uuid4())
        )
        assert result is None


class TestReadFlows:
    @pytest.fixture
    async def flows(self, database_session):
        flow_1 = await models.flows.create_flow(
            session=database_session, flow=schemas.actions.FlowCreate(name="my-flow-1")
        )
        flow_2 = await models.flows.create_flow(
            session=database_session, flow=schemas.actions.FlowCreate(name="my-flow-2")
        )
        return [flow_1, flow_2]

    async def test_read_flows(self, flows, database_session):
        read_flows = await models.flows.read_flows(session=database_session)
        assert len(read_flows) == len(flows)

    async def test_read_flows_applies_limit(self, flows, database_session):
        read_flows = await models.flows.read_flows(session=database_session, limit=1)
        assert len(read_flows) == 1

    async def test_read_flows_applies_offset(self, flows, database_session):
        read_flows = await models.flows.read_flows(session=database_session, offset=1)
        # note this test only works right now because flows are ordered by
        # name by default, when the actual ordering logic is implemented
        # this test case will need to be modified
        assert len(read_flows) == 1
        assert read_flows[0].name == "my-flow-2"

    async def test_read_flows_returns_empty_list(self, database_session):
        read_flows = await models.flows.read_flows(session=database_session)
        assert len(read_flows) == 0


class TestDeleteFlow:
    async def test_delete_flow(self, database_session):
        # create a flow to delete
        flow = await models.flows.create_flow(
            session=database_session, flow=schemas.actions.FlowCreate(name="my-flow")
        )
        assert flow.name == "my-flow"

        assert await models.flows.delete_flow(session=database_session, id=flow.id)

        # make sure the flow is deleted
        assert (
            await models.flows.read_flow(session=database_session, id=flow.id)
        ) is None

    async def test_delete_flow_returns_false_if_does_not_exist(self, database_session):
        result = await models.flows.delete_flow(
            session=database_session, id=str(uuid4())
        )
        assert result is False

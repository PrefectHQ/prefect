from uuid import uuid4

import pytest

from prefect.server import models, schemas


class TestCreateFlow:
    async def test_create_flow_succeeds(self, session):
        flow = await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="my-flow")
        )
        assert flow.name == "my-flow"
        assert flow.id

    async def test_create_flow_does_not_upsert(self, session):
        # create a flow
        flow_1 = await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="my-flow", tags=["green"])
        )

        # try to create the same flow with tags
        flow_2 = await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="my-flow", tags=["blue"])
        )
        assert flow_1.tags == flow_2.tags
        assert flow_1.name == flow_2.name
        assert flow_1.id == flow_2.id


class TestUpdateFlow:
    async def test_update_flow_succeeds(self, session):
        flow = await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="my-flow")
        )

        flow_id = flow.id

        update_result = await models.flows.update_flow(
            session=session,
            flow_id=flow_id,
            flow=schemas.actions.FlowUpdate(tags=["TB12"]),
        )
        assert update_result

        updated_flow = await models.flows.read_flow(session=session, flow_id=flow_id)
        assert updated_flow.tags == ["TB12"]
        assert flow_id == flow.id == updated_flow.id

    async def test_update_flow_does_not_update_if_nothing_set(self, session):
        flow = await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="my-flow", tags=["TB12"])
        )

        flow_id = flow.id

        update_result = await models.flows.update_flow(
            session=session,
            flow_id=flow_id,
            flow=schemas.actions.FlowUpdate(),
        )
        assert update_result

        updated_flow = await models.flows.read_flow(session=session, flow_id=flow_id)
        assert updated_flow.tags == ["TB12"]
        assert flow_id == flow.id == updated_flow.id

    async def test_update_flow_returns_false_if_flow_does_not_exist(self, session):
        assert not (
            await models.flows.update_flow(
                session=session,
                flow_id=uuid4(),
                flow=schemas.actions.FlowUpdate(),
            )
        )


class TestReadFlow:
    async def test_read_flow(self, session):
        # create a flow to read
        flow = await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="my-flow")
        )
        assert flow.name == "my-flow"

        read_flow = await models.flows.read_flow(session=session, flow_id=flow.id)
        assert flow.id == read_flow.id
        assert flow.name == read_flow.name

    async def test_read_flow_returns_none_if_does_not_exist(self, session):
        result = await models.flows.read_flow(session=session, flow_id=str(uuid4()))
        assert result is None


class TestReadFlowByName:
    async def test_read_flow(self, session):
        # create a flow to read
        flow = await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="my-flow")
        )
        assert flow.name == "my-flow"

        read_flow = await models.flows.read_flow_by_name(
            session=session, name=flow.name
        )
        assert flow.id == read_flow.id
        assert flow.name == read_flow.name

    async def test_read_flow_returns_none_if_does_not_exist(self, session):
        result = await models.flows.read_flow_by_name(
            session=session, name=str(uuid4())
        )
        assert result is None


class TestReadFlows:
    @pytest.fixture
    async def flows(self, session):
        flow_1 = await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="my-flow-1")
        )
        flow_2 = await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="my-flow-2")
        )
        await session.commit()
        return [flow_1, flow_2]

    async def test_read_flows(self, flows, session):
        read_flows = await models.flows.read_flows(session=session)
        assert len(read_flows) == len(flows)

    async def test_read_flows_applies_limit(self, flows, session):
        read_flows = await models.flows.read_flows(session=session, limit=1)
        assert len(read_flows) == 1

    async def test_read_flows_applies_offset(self, flows, session):
        read_flows = await models.flows.read_flows(session=session, offset=1)
        # note this test only works right now because flows are ordered by
        # name by default, when the actual ordering logic is implemented
        # this test case will need to be modified
        assert len(read_flows) == 1
        assert read_flows[0].name == "my-flow-2"

    async def test_read_flows_returns_empty_list(self, session):
        read_flows = await models.flows.read_flows(session=session)
        assert len(read_flows) == 0

    async def test_read_flows_filters_by_tags(self, session):
        flow_1 = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="my-flow-1", tags=["db", "blue"]),
        )
        flow_2 = await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="my-flow-2", tags=["db"])
        )
        flow_3 = await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="my-flow-3")
        )

        # exact tag match
        result = await models.flows.read_flows(
            session=session,
            flow_filter=schemas.filters.FlowFilter(
                tags=schemas.filters.FlowFilterTags(all_=["db", "blue"])
            ),
        )
        assert {res.id for res in result} == {flow_1.id}

        # subset of tags match
        result = await models.flows.read_flows(
            session=session,
            flow_filter=schemas.filters.FlowFilter(
                tags=schemas.filters.FlowFilterTags(all_=["db"])
            ),
        )
        assert {res.id for res in result} == {flow_1.id, flow_2.id}

        # is_null_
        result = await models.flows.read_flows(
            session=session,
            flow_filter=schemas.filters.FlowFilter(
                tags=schemas.filters.FlowFilterTags(is_null_=True)
            ),
        )
        assert {res.id for res in result} == {flow_3.id}
        result = await models.flows.read_flows(
            session=session,
            flow_filter=schemas.filters.FlowFilter(
                tags=schemas.filters.FlowFilterTags(is_null_=False)
            ),
        )
        assert {res.id for res in result} == {flow_1.id, flow_2.id}

    async def test_flows_filters_by_name_any(self, session):
        flow_1 = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="my-flow-1", tags=["db", "blue"]),
        )
        flow_2 = await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="my-flow-2", tags=["db"])
        )
        flow_3 = await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="my-flow-3")
        )

        # filter based on flow names
        result = await models.flows.read_flows(
            session=session,
            flow_filter=schemas.filters.FlowFilter(
                name=schemas.filters.FlowFilterName(any_=["my-flow-1"])
            ),
        )
        assert {res.id for res in result} == {flow_1.id}

        result = await models.flows.read_flows(
            session=session,
            flow_filter=schemas.filters.FlowFilter(
                name=schemas.filters.FlowFilterName(any_=["my-flow-2", "my-flow-3"])
            ),
        )
        assert {res.id for res in result} == {flow_2.id, flow_3.id}

    async def test_read_flows_filters_by_ids_any(self, session):
        flow_1 = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name="my-flow-1", tags=["db", "blue"]),
        )
        flow_2 = await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="my-flow-2", tags=["db"])
        )
        await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="my-flow-3")
        )

        # filter based on flow ids
        result = await models.flows.read_flows(
            session=session,
            flow_filter=schemas.filters.FlowFilter(
                id=schemas.filters.FlowFilterId(any_=[flow_1.id])
            ),
        )
        assert {res.id for res in result} == {flow_1.id}

        result = await models.flows.read_flows(
            session=session,
            flow_filter=schemas.filters.FlowFilter(
                id=schemas.filters.FlowFilterId(any_=[flow_1.id, flow_2.id])
            ),
        )
        assert {res.id for res in result} == {flow_1.id, flow_2.id}

    async def test_read_flows_filters_by_deployment_criteria(
        self, flow, deployment, session
    ):
        result = await models.flows.read_flows(
            session=session,
            deployment_filter=schemas.filters.DeploymentFilter(
                id=dict(any_=[deployment.id])
            ),
        )
        assert {res.id for res in result} == {flow.id}
        result = await models.flows.read_flows(
            session=session,
            flow_filter=schemas.filters.FlowFilter(id=dict(any_=[flow.id])),
            deployment_filter=schemas.filters.DeploymentFilter(id=dict(any_=[uuid4()])),
        )
        assert len(result) == 0

    async def test_read_flows_applies_sort(self, flows, session):
        read_flows = await models.flows.read_flows(
            session=session, sort=schemas.sorting.FlowSort.NAME_ASC
        )
        assert read_flows[0].name == "my-flow-1"

        read_flows_name_desc = await models.flows.read_flows(
            session=session, sort=schemas.sorting.FlowSort.NAME_DESC
        )
        assert read_flows_name_desc[0].name == "my-flow-2"


class TestDeleteFlow:
    async def test_delete_flow(self, session):
        # create a flow to delete
        flow = await models.flows.create_flow(
            session=session, flow=schemas.core.Flow(name="my-flow")
        )
        assert flow.name == "my-flow"

        assert await models.flows.delete_flow(session=session, flow_id=flow.id)

        # make sure the flow is deleted
        assert (await models.flows.read_flow(session=session, flow_id=flow.id)) is None

    async def test_delete_flow_returns_false_if_does_not_exist(self, session):
        result = await models.flows.delete_flow(session=session, flow_id=str(uuid4()))
        assert result is False

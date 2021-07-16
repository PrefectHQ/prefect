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

import pytest
from uuid import uuid4
import pendulum
from prefect.orion import models, schemas


class TestCreateFlowRunState:
    async def test_create_flow_run_state_succeeds(self, flow_run, database_session):
        fake_flow_run_state = schemas.actions.StateCreate(type="RUNNING")
        flow_run_state = await models.flow_run_states.create_flow_run_state(
            session=database_session,
            flow_run_state=fake_flow_run_state,
            flow_run_id=flow_run.id,
        )
        assert flow_run_state.name == fake_flow_run_state.name
        assert flow_run_state.type == fake_flow_run_state.type
        assert flow_run_state.flow_run_id == flow_run.id
        assert flow_run_state.state_details["flow_run_id"] == flow_run.id

    async def test_create_flow_run_state_succeeds(self, flow_run, database_session):
        fake_flow_run_state = schemas.actions.StateCreate(
            type="SCHEDULED",
        )
        flow_run_state = await models.flow_run_states.create_flow_run_state(
            session=database_session,
            flow_run_state=fake_flow_run_state,
            flow_run_id=flow_run.id,
        )

        another_fake_flow_run_state = schemas.actions.StateCreate(type="RUNNING")
        another_flow_run_state = await models.flow_run_states.create_flow_run_state(
            session=database_session,
            flow_run_state=fake_flow_run_state,
            flow_run_id=flow_run.id,
        )
        assert (
            another_flow_run_state.run_details["previous_state_id"] == flow_run_state.id
        )


class TestReadFlowRunState:
    async def test_read_flow_run_state(self, database_session):
        # create a flow run to read
        fake_flow_run_state = schemas.actions.StateCreate(type="RUNNING")
        flow_run_state = await models.flow_run_states.create_flow_run_state(
            session=database_session,
            flow_run_state=fake_flow_run_state,
            flow_run_id=uuid4(),
        )
        read_flow_run_state = await models.flow_run_states.read_flow_run_state(
            session=database_session, id=flow_run_state.id
        )
        assert flow_run_state == read_flow_run_state

    async def test_read_flow_run_state_returns_none_if_does_not_exist(
        self, database_session
    ):
        assert (
            await models.flow_run_states.read_flow_run_state(
                session=database_session, id=uuid4()
            )
        ) is None


class TestReadFlowRunStates:
    async def test_flow_run_states(self, database_session, flow_run, flow_run_states):
        flow_run_states_by_flow_run_id = (
            await models.flow_run_states.read_flow_run_states(
                session=database_session, flow_run_id=flow_run.id
            )
        )
        assert len(flow_run_states_by_flow_run_id) == len(flow_run_states)

    async def test_flow_run_states_filters_by_flow_run_id(self, database_session):
        # query for states using a random flow run id
        flow_run_states_by_flow_run_id = (
            await models.flow_run_states.read_flow_run_states(
                session=database_session, flow_run_id=uuid4()
            )
        )
        assert len(flow_run_states_by_flow_run_id) == 0


class TestDeleteFlowRunState:
    async def test_delete_flow_run_state(self, database_session):
        # create a flow run to read
        fake_flow_run_state = schemas.actions.StateCreate(type="RUNNING")
        flow_run_state = await models.flow_run_states.create_flow_run_state(
            session=database_session,
            flow_run_state=fake_flow_run_state,
            flow_run_id=uuid4(),
        )

        assert await models.flow_run_states.delete_flow_run_state(
            session=database_session, id=flow_run_state.id
        )

        # make sure the flow run state is deleted
        assert (
            await models.flow_run_states.read_flow_run_state(
                session=database_session, id=flow_run_state.id
            )
        ) is None

    async def test_delete_flow_run_state_returns_false_if_does_not_exist(
        self, database_session
    ):
        assert not (
            await models.flow_run_states.delete_flow_run_state(
                session=database_session, id=uuid4()
            )
        )

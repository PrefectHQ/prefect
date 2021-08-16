import pytest
from uuid import uuid4
import pendulum
from prefect.orion import models, schemas
from prefect.orion.schemas.states import StateType


class TestCreateFlowRunState:
    async def test_create_flow_run_state_succeeds(self, flow_run, session):
        flow_run_state = await models.flow_run_states.create_flow_run_state(
            session=session,
            flow_run_id=flow_run.id,
            state=schemas.actions.StateCreate(type="RUNNING"),
        )
        assert flow_run_state.name == "Running"
        assert flow_run_state.type == StateType.RUNNING
        assert flow_run_state.flow_run_id == flow_run.id
        assert flow_run_state.state_details.flow_run_id == flow_run.id

    async def test_run_details_are_updated_with_previous_state_id(
        self, flow_run, session
    ):
        trs = await models.flow_run_states.create_flow_run_state(
            session=session,
            flow_run_id=flow_run.id,
            state=schemas.actions.StateCreate(type="SCHEDULED"),
        )

        trs2 = await models.flow_run_states.create_flow_run_state(
            session=session,
            flow_run_id=flow_run.id,
            state=schemas.actions.StateCreate(type="RUNNING"),
        )
        assert trs2.run_details.previous_state_id == trs.id

    async def test_run_details_are_updated_entering_running(self, flow_run, session):
        trs = await models.flow_run_states.create_flow_run_state(
            session=session,
            flow_run_id=flow_run.id,
            state=schemas.actions.StateCreate(type="SCHEDULED"),
        )

        assert trs.run_details.start_time is None
        assert trs.run_details.run_count == 0

        trs2 = await models.flow_run_states.create_flow_run_state(
            session=session,
            flow_run_id=flow_run.id,
            state=schemas.actions.StateCreate(type="RUNNING"),
        )
        assert trs2.run_details.start_time == trs2.timestamp
        assert trs2.run_details.run_count == 1
        assert trs2.run_details.last_run_time == trs2.timestamp
        assert trs2.run_details.total_run_time_seconds == 0

        trs3 = await models.flow_run_states.create_flow_run_state(
            session=session,
            flow_run_id=flow_run.id,
            state=schemas.actions.StateCreate(type="RUNNING"),
        )
        assert trs3.run_details.start_time == trs2.timestamp
        assert trs3.run_details.run_count == 2
        assert trs3.run_details.last_run_time == trs3.timestamp
        assert (
            trs3.run_details.total_run_time_seconds
            == (trs3.timestamp - trs2.timestamp).total_seconds()
        )


class TestReadFlowRunState:
    async def test_read_flow_run_state(self, flow_run, session):
        # create a flow run to read
        flow_run_state = await models.flow_run_states.create_flow_run_state(
            session=session,
            flow_run_id=flow_run.id,
            state=schemas.actions.StateCreate(type="RUNNING"),
        )

        read_flow_run_state = await models.flow_run_states.read_flow_run_state(
            session=session, flow_run_state_id=flow_run_state.id
        )
        assert flow_run_state == read_flow_run_state

    async def test_read_flow_run_state_returns_none_if_does_not_exist(self, session):
        result = await models.flow_run_states.read_flow_run_state(
            session=session, flow_run_state_id=uuid4()
        )

        assert result is None


class TestReadFlowRunStates:
    async def test_flow_run_states(self, session, flow_run, flow_run_states):
        flow_run_states_by_flow_run_id = (
            await models.flow_run_states.read_flow_run_states(
                session=session, flow_run_id=flow_run.id
            )
        )
        assert len(flow_run_states_by_flow_run_id) == len(flow_run_states)

    async def test_flow_run_states_filters_by_flow_run_id(self, session):
        # query for states using a random flow run id
        flow_run_states_by_flow_run_id = (
            await models.flow_run_states.read_flow_run_states(
                session=session, flow_run_id=uuid4()
            )
        )
        assert len(flow_run_states_by_flow_run_id) == 0


class TestDeleteFlowRunState:
    async def test_delete_flow_run_state(self, flow_run, session):
        # create a flow run to read
        flow_run_state = await models.flow_run_states.create_flow_run_state(
            session=session,
            flow_run_id=flow_run.id,
            state=schemas.actions.StateCreate(type="RUNNING"),
        )

        assert await models.flow_run_states.delete_flow_run_state(
            session=session, flow_run_state_id=flow_run_state.id
        )

        # make sure the flow run state is deleted
        result = await models.flow_run_states.read_flow_run_state(
            session=session, flow_run_state_id=flow_run_state.id
        )
        assert result is None

    async def test_delete_flow_run_state_returns_false_if_does_not_exist(self, session):
        result = await models.flow_run_states.delete_flow_run_state(
            session=session, flow_run_state_id=uuid4()
        )
        assert not result

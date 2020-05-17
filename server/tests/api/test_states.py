# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import asyncio
import datetime
import json
import time
import uuid

import pendulum
import pytest
from asynctest import CoroutineMock
from box import Box

import prefect
from prefect.engine.result import Result, SafeResult
from prefect.engine.result_handlers import JSONResultHandler
from prefect.engine.state import (
    Failed,
    Finished,
    Looped,
    Mapped,
    Pending,
    Retrying,
    Running,
    Scheduled,
    State,
    Submitted,
    Success,
    TimedOut,
    TriggerFailed,
    _MetaState,
)
from prefect_server import api, config, utilities
from prefect_server.api import runs, states
from prefect_server.database import models


class TestTaskRunStates:
    @pytest.mark.parametrize(
        "state_cls", [s for s in State.children() if s not in _MetaState.children()]
    )
    async def test_set_task_run_state(
        self, running_flow_run_id, task_run_id, state_cls
    ):
        await states.set_task_run_state(task_run_id=task_run_id, state=state_cls())

        query = await models.TaskRun.where(id=task_run_id).first(
            {"version", "state", "serialized_state"}
        )

        assert query.version == 1
        assert query.state == state_cls.__name__
        assert query.serialized_state["type"] == state_cls.__name__

    @pytest.mark.parametrize(
        "state_cls",
        [
            s
            for s in State.children()
            if s not in _MetaState.children() and not s().is_running()
        ],
    )
    async def test_set_non_running_task_run_state_works_when_flow_run_is_not_running(
        self, flow_run_id, task_run_id, state_cls
    ):
        await states.set_flow_run_state(flow_run_id, state=Success())
        await states.set_task_run_state(task_run_id=task_run_id, state=state_cls())

        query = await models.TaskRun.where(id=task_run_id).first(
            {"version", "state", "serialized_state"}
        )

        assert query.version == 1
        assert query.state == state_cls.__name__
        assert query.serialized_state["type"] == state_cls.__name__

    async def test_set_running_task_run_state_fails_when_flow_run_is_not_running(
        self, flow_run_id, task_run_id
    ):
        await states.set_flow_run_state(flow_run_id, state=Success())
        with pytest.raises(ValueError, match="State update failed"):
            await states.set_task_run_state(task_run_id=task_run_id, state=Running())

    async def test_set_running_task_run_state_works_when_flow_run_is_not_running_if_force(
        self, flow_run_id, task_run_id,
    ):
        await states.set_flow_run_state(flow_run_id, state=Success())
        await states.set_task_run_state(
            task_run_id=task_run_id, state=Running(), force=True
        )

        query = await models.TaskRun.where(id=task_run_id).first(
            {"version", "state", "serialized_state"}
        )

        assert query.version == 1
        assert query.state == "Running"
        assert query.serialized_state["type"] == "Running"

    async def test_set_task_run_state_does_not_increment_run_count_when_looping(
        self, task_run_id, running_flow_run_id
    ):
        # simulate some looping
        await states.set_task_run_state(task_run_id=task_run_id, state=Running())
        await states.set_task_run_state(task_run_id=task_run_id, state=Looped())
        result = await states.set_task_run_state(
            task_run_id=task_run_id, state=Running()
        )

        task_run = await models.TaskRun.where(id=task_run_id).first({"run_count"})
        assert task_run.run_count == 1

    @pytest.mark.parametrize("state", [Running(), Success()])
    async def test_set_task_run_state_fails_with_wrong_task_run_id(
        self, state, running_flow_run_id
    ):
        with pytest.raises(ValueError, match="Invalid task run ID"):
            await states.set_task_run_state(task_run_id=str(uuid.uuid4()), state=state)

    async def test_trigger_failed_state_does_not_set_end_time(self, task_run_id):
        await states.set_task_run_state(task_run_id=task_run_id, state=TriggerFailed())
        task_run_info = await models.TaskRun.where(id=task_run_id).first(
            {"id", "start_time", "end_time"}
        )
        assert not task_run_info.start_time
        assert not task_run_info.end_time

    @pytest.mark.parametrize(
        "state_cls", [s for s in State.children() if s not in _MetaState.children()]
    )
    async def test_setting_a_task_run_state_pulls_cached_inputs_if_possible(
        self, running_flow_run_id, task_run_id, state_cls
    ):
        # set up a Failed state with cached inputs
        res1 = SafeResult(1, result_handler=JSONResultHandler())
        res2 = SafeResult({"z": 2}, result_handler=JSONResultHandler())
        complex_result = {"x": res1, "y": res2}
        cached_state = Failed(cached_inputs=complex_result)
        await models.TaskRun.where(id=task_run_id).update(
            set=dict(serialized_state=cached_state.serialize())
        )

        # try to schedule the task run to scheduled
        await states.set_task_run_state(task_run_id=task_run_id, state=state_cls())

        task_run = await models.TaskRun.where(id=task_run_id).first(
            {"serialized_state"}
        )

        # ensure the state change took place
        assert task_run.serialized_state["type"] == state_cls.__name__
        assert task_run.serialized_state["cached_inputs"]["x"]["value"] == 1
        assert task_run.serialized_state["cached_inputs"]["y"]["value"] == {"z": 2}

    @pytest.mark.parametrize(
        "state",
        [
            s(cached_inputs=None)
            for s in State.children()
            if s not in _MetaState.children()
        ],
        ids=[s.__name__ for s in State.children() if s not in _MetaState.children()],
    )
    async def test_task_runs_with_null_cached_inputs_do_not_overwrite_cache(
        self, running_flow_run_id, state, task_run_id
    ):
        # set up a Failed state with null cached inputs
        await states.set_task_run_state(task_run_id=task_run_id, state=state)
        # set up a Retrying state with non-null cached inputs
        res1 = SafeResult(1, result_handler=JSONResultHandler())
        res2 = SafeResult({"z": 2}, result_handler=JSONResultHandler())
        complex_result = {"x": res1, "y": res2}
        cached_state = Retrying(cached_inputs=complex_result)
        await states.set_task_run_state(task_run_id=task_run_id, state=cached_state)
        run = await models.TaskRun.where(id=task_run_id).first({"serialized_state"})

        assert run.serialized_state["cached_inputs"]["x"]["value"] == 1
        assert run.serialized_state["cached_inputs"]["y"]["value"] == {"z": 2}

    @pytest.mark.parametrize(
        "state_cls", [s for s in State.children() if s not in _MetaState.children()]
    )
    async def test_task_runs_cached_inputs_give_preference_to_new_cached_inputs(
        self, running_flow_run_id, state_cls, task_run_id
    ):
        # set up a Failed state with null cached inputs
        res1 = SafeResult(1, result_handler=JSONResultHandler())
        res2 = SafeResult({"a": 2}, result_handler=JSONResultHandler())
        complex_result = {"b": res1, "c": res2}
        cached_state = state_cls(cached_inputs=complex_result)
        await states.set_task_run_state(task_run_id=task_run_id, state=cached_state)
        # set up a Retrying state with non-null cached inputs
        res1 = SafeResult(1, result_handler=JSONResultHandler())
        res2 = SafeResult({"z": 2}, result_handler=JSONResultHandler())
        complex_result = {"x": res1, "y": res2}
        cached_state = Retrying(cached_inputs=complex_result)
        await states.set_task_run_state(task_run_id=task_run_id, state=cached_state)
        run = Box(
            await models.TaskRun.where(id=task_run_id).first({"serialized_state"})
        )

        # verify that we have cached inputs, and that preference has been given to the new
        # cached inputs
        assert run.serialized_state.cached_inputs
        assert run.serialized_state.cached_inputs.x.value == 1
        assert run.serialized_state.cached_inputs.y.value == {"z": 2}


class TestFlowRunStates:
    @pytest.mark.parametrize(
        "state_cls", [s for s in State.children() if s not in _MetaState.children()]
    )
    async def test_set_flow_run_state(self, flow_run_id, state_cls):
        result = await states.set_flow_run_state(
            flow_run_id=flow_run_id, state=state_cls()
        )

        query = await models.FlowRun.where(id=flow_run_id).first(
            {"version", "state", "serialized_state"}
        )

        assert query.version == 2
        assert query.state == state_cls.__name__
        assert query.serialized_state["type"] == state_cls.__name__

    @pytest.mark.parametrize("state", [Running(), Success()])
    async def test_set_flow_run_state_fails_with_wrong_flow_run_id(self, state):
        with pytest.raises(ValueError, match="Invalid flow run ID"):
            await states.set_flow_run_state(flow_run_id=str(uuid.uuid4()), state=state)

    async def test_trigger_failed_state_does_not_set_end_time(self, flow_run_id):
        # there is no logic in Prefect that would create this sequence of
        # events, but a user could manually do this
        await states.set_flow_run_state(flow_run_id=flow_run_id, state=TriggerFailed())
        flow_run_info = await models.FlowRun.where(id=flow_run_id).first(
            {"id", "start_time", "end_time"}
        )
        assert not flow_run_info.start_time
        assert not flow_run_info.end_time

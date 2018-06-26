import copy
from contextlib import contextmanager

import pytest

import prefect
from prefect import Task, Flow
from prefect.engine.state import State
from typing import Union, Dict, Any, Iterable


@contextmanager
def set_config(keys, value):
    try:
        old_config = copy.copy(prefect.config.__dict__)

        config = prefect.config
        if isinstance(keys, str):
            keys = [keys]
        for key in keys[:-1]:
            config = getattr(config, key)
        setattr(config, keys[-1], value)
        yield
    finally:
        prefect.config.__dict__.clear()
        prefect.config.__dict__.update(old_config)


def run_flow_runner_test(
    flow: Flow,
    expected_state: str,
    state: State=None,
    task_states: Dict[Task, State]=None,
    start_tasks: Iterable[Task]=None,
    expected_task_states: Dict[Task, Union[State, str]]=None,
    executor=None,
    parameters: dict=None,
    context: dict=None,
) -> State:
    """
    Runs a flow and tests that it matches the expected state. If an
    expected_task_states dict is provided, it will be matched as well.

    Args:
        flow (prefect.Flow): the Flow to test

        expected_state (str): the expected State as a string (no data)

        state (State): the starting state for the flow.

        expected_task_states (dict): a dict of expected
            {task_id: State} (or {task_id: str}) pairs. Passing a
            dict with Task keys is also ok.

        executor (prefect.Executor)

        context (dict): an optional context for the run

        parameters (dict): the parameters for the run

        override_task_inputs (dict): input overrides for tasks. This dict should have
            the form {task.name: {kwarg: value}}.

    Returns:
        The FlowRun state
    """
    if expected_task_states is None:
        expected_task_states = {}

    flow_runner = prefect.engine.flow_runner.FlowRunner(flow=flow, executor=executor)

    flow_state = flow_runner.run(
        state=state,
        context=context,
        parameters=parameters,
        task_states=task_states,
        start_tasks=start_tasks,
        return_tasks=expected_task_states.keys())

    if expected_state is not None:
        try:
            assert flow_state.state == expected_state
        except AssertionError:
            pytest.fail(
                "Flow state ({}) did not match expected state ({})".format(
                    flow_state, expected_state
                )
            )

    for task, expected_task_state in expected_task_states.items():
        try:
            if isinstance(expected_task_state, str):
                assert flow_state.data[task].state == expected_task_state
            else:
                assert flow_state.data[task] == expected_task_state
        except AssertionError:
            pytest.fail(
                "Actual task state ({a_state}) or data ({a_data}) did not match "
                "expected task state ({e_state}) or data ({e_data}) "
                'for task "{task}"'.format(
                    a_state=flow_state.data[task].state,
                    a_data=flow_state.data[task].data,
                    e_state=State(expected_task_state).state,
                    e_data=State(expected_task_state).data,
                    task=task,
                )
            )
        except:
            pytest.fail("Task {} not found in flow state".format(task))


    return flow_state

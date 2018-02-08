import itertools

import pytest

import prefect
from prefect.engine.state import TaskRunState


class DummyTask(prefect.Task):

    _id_iter = itertools.count()

    def __init__(self, name=None, *args, **kwargs):
        if name is None:
            name = str(next(self._id_iter))
        super().__init__(*args, name=name, **kwargs)

    def run(self):
        pass


def run_task_runner_test(
        task,
        expected_state,
        state=None,
        upstream_states=None,
        inputs=None,
        executor=None,
        context=None):
    """
    Runs a task and tests that it matches the expected state.

    Args:
        task (prefect.Task): the Task to test

        expected_state (prefect.TaskRunState or str): the expected TaskRunState

        state (prefect.TaskRunState or str): the starting state for the task.

        upstream_states (dict): a dictionary of {task_name: TaskRunState} pairs
            representing the task's upstream states

        inputs (dict): a dictionary of inputs to the task

        executor (prefect.Executor)

        context (dict): an optional context for the run

    Returns:
        The TaskRun state
    """
    task_runner = prefect.engine.task_runner.TaskRunner(
        task=task, executor=executor)
    task_state = task_runner.run(
        state=state,
        upstream_states=upstream_states,
        inputs=inputs,
        context=context)

    assert task_state == expected_state
    if isinstance(expected_state, TaskRunState):
        assert task_state.result == expected_state.result

    return task_state


def run_flow_runner_test(
        flow,
        expected_state=None,
        state=None,
        task_states=None,
        start_tasks=None,
        expected_task_states=None,
        executor=None,
        override_task_inputs=None,
        parameters=None,
        context=None):
    """
    Runs a flow and tests that it matches the expected state. If an
    expected_task_states dict is provided, it will be matched as well.

    Args:
        flow (prefect.Flow): the Flow to test

        expected_state (prefect.FlowRunState or str): the expected FlowRunState

        state (prefect.FlowRunState or str): the starting state for the task.

        expected_task_states (dict): a dict of expected
            {task_name: TaskRunState} (or {task_name: str}) pairs. Passing a
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

    flow_runner = prefect.engine.flow_runner.FlowRunner(
        flow=flow, executor=executor)
    flow_state = flow_runner.run(
        state=state,
        context=context,
        parameters=parameters,
        override_task_inputs=override_task_inputs,
        task_states=task_states,
        start_tasks=start_tasks,
        return_all_task_states=True)

    if expected_state is not None:
        try:
            assert flow_state == expected_state
        except AssertionError:
            pytest.fail(
                'Flow state ({}) did not match expected state ({})'.format(
                    flow_state, expected_state))

    for task_name, expected_task_state in expected_task_states.items():
        if isinstance(task_name, prefect.Task):
            task_name = task_name.name
        try:
            assert flow_state.result[task_name] == expected_task_state
        except KeyError:
            pytest.fail('Task {} not found in flow result'.format(task_name))
        except AssertionError:
            pytest.fail(
                'Actual task state ({}) did not match expected task state ({}) '
                'for task: {}'.format(
                    flow_state.result[task_name], expected_task_state,
                    task_name))
        if isinstance(expected_task_state, TaskRunState):
            assert flow_state.result[
                task_name].result == expected_task_state.result

    return flow_state

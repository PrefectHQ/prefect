import prefect
from prefect.state import TaskRunState


def run_task_runner_test(
        task,
        expected_state,
        state=None,
        upstream_states=None,
        inputs=None,
        executor_context=None,
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

        executor_context (contextmanager): an optional execution context manager

        context (dict): an optional context for the run

    Returns:
        The TaskRun state
    """
    task_runner = prefect.engine.task_runner.TaskRunner(
        task=task, executor_context=executor_context)
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
        expected_state,
        state=None,
        expected_task_states=None,
        executor_context=None,
        inputs=None,
        context=None):
    """
    Runs a flow and tests that it matches the expected state. If an
    expected_task_states dict is provided, it will be matched as well.

    Args:
        flow (prefect.Flow): the Flow to test

        expected_state (prefect.FlowRunState or str): the expected FlowRunState

        state (prefect.FlowRunState or str): the starting state for the task.

        expected_task_states (dict): a dict of expected
            {task_name: TaskRunState} (or {task_name: str}) pairs

        executor_context (contextmanager): an optional execution context manager

        context (dict): an optional context for the run

        inputs (dict): input overrides for tasks. This dict should have
            the form {task.name: {kwarg: value}}.

    Returns:
        The FlowRun state
    """
    if expected_task_states is None:
        expected_task_states = {}

    flow_runner = prefect.engine.flow_runner.FlowRunner(
        flow=flow, executor_context=executor_context)
    flow_state = flow_runner.run(
        state=state,
        context=context,
        inputs=inputs,
        return_all_task_states=True)
    assert flow_state == expected_state

    for task_name, expected_task_state in expected_task_states.items():
        assert flow_state.result[task_name] == expected_task_state
        if isinstance(expected_task_state, TaskRunState):
            assert flow_state.result[
                task_name].result == expected_task_state.result

    return flow_state

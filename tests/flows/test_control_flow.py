import pytest
import prefect
from prefect.tasks import control_flow, Parameter
from prefect.utilities.tests import run_flow_runner_test, DummyTask
from prefect.state import FlowRunState, TaskRunState


def test_ifelse():
    """
    Test a flow with the form:
        condition (True)
        - True-1 => True-2
        - False-1 => False-2

    """
    with prefect.Flow('test') as flow:
        condition = True

        # create branches of two dummy tasks each for True and False
        true_task = DummyTask('true_1')
        false_task = DummyTask('false_1')
        true_task.set(run_before=DummyTask('true_2'))
        false_task.set(run_before=DummyTask('false_2'))

        # create ifelse
        control_flow.ifelse(
            condition=condition, true_task=true_task, false_task=false_task)

    run_flow_runner_test(
        flow=flow,
        expected_task_states=dict(
            true_1=TaskRunState.SUCCESS,
            true_2=TaskRunState.SUCCESS,
            false_1=TaskRunState.SKIP_DOWNSTREAM,
            false_2=TaskRunState.SKIP_DOWNSTREAM))


def test_switch():

    with prefect.Flow('test') as flow:

        condition = Parameter('x')

        branches = {
            5: DummyTask('5'),
            6: DummyTask('6'),
            'xyz': DummyTask('xyz'),
        }

        # create switch
        control_flow.switch(condition=condition, patterns=branches)

    run_flow_runner_test(
        flow=flow,
        parameters=dict(x=5),
        expected_task_states={
            '5': TaskRunState.SUCCESS,
            '6': TaskRunState.SKIP_DOWNSTREAM,
            'xyz': TaskRunState.SKIP_DOWNSTREAM,
        })

    run_flow_runner_test(
        flow=flow,
        parameters=dict(x=6),
        expected_task_states={
            '5': TaskRunState.SKIP_DOWNSTREAM,
            '6': TaskRunState.SUCCESS,
            'xyz': TaskRunState.SKIP_DOWNSTREAM,
        })

    run_flow_runner_test(
        flow=flow,
        parameters=dict(x='xyz'),
        expected_task_states={
            '5': TaskRunState.SKIP_DOWNSTREAM,
            '6': TaskRunState.SKIP_DOWNSTREAM,
            'xyz': TaskRunState.SUCCESS,
        })

    run_flow_runner_test(
        flow=flow,
        parameters=dict(x=True),
        expected_task_states={
            '5': TaskRunState.SKIP_DOWNSTREAM,
            '6': TaskRunState.SKIP_DOWNSTREAM,
            'xyz': TaskRunState.SKIP_DOWNSTREAM,
        })

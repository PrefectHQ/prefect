import pytest
import prefect
from prefect.utilities.test import run_flow_runner_test
from prefect.state import FlowRunState, TaskRunState


def test_approval():
    with prefect.Flow('approval') as f:
        pre_approval = prefect.tasks.FunctionTask(
            fn=lambda: 1, name='pre_approval')
        wait_for_approval = prefect.tasks.control_flow.approval.WaitForApproval(
            name='wait_for_approval')
        post_approval = prefect.tasks.FunctionTask(
            fn=lambda: 2, name='post_approval')

        pre_approval.then(wait_for_approval).then(
            post_approval)

    # states after the approval request should still be pending
    state = run_flow_runner_test(
        flow=f,
        expected_state=FlowRunState.PENDING,
        expected_task_states=dict(
            pre_approval=FlowRunState.SUCCESS,
            wait_for_approval=FlowRunState.PENDING,
            post_approval=FlowRunState.PENDING,
        ))

    # rerunning should not change anything
    run_flow_runner_test(
        flow=f,
        # initialize with previous results
        task_states=state.result,
        expected_state=FlowRunState.PENDING,
        expected_task_states=dict(
            pre_approval=FlowRunState.SUCCESS,
            wait_for_approval=FlowRunState.PENDING,
            post_approval=FlowRunState.PENDING,
        ))

    # running with the approval task as the start_task should run the process
    run_flow_runner_test(
        flow=f,
        # initialize with previous result
        task_states=state.result,
        # specify wait_for_approval as a start_task
        start_tasks=['wait_for_approval'],
        expected_state=FlowRunState.SUCCESS,
        expected_task_states=dict(
            pre_approval=FlowRunState.SUCCESS,
            wait_for_approval=FlowRunState.SUCCESS,
            post_approval=FlowRunState.SUCCESS,
        ))

# def test_approval_branch():
#     with prefect.Flow('approval') as f:

#         task1 = prefect.tasks.FunctionTask(fn=lambda: 1, name='do_something')
#         request_approval = prefect.tasks.control_flow.approval.RequestApproval(
#             name='request_approval', next_task_name='wait_for_approval')
#         wait_for_approval = prefect.tasks.control_flow.approval.ReceiveApproval(
#             name='wait_for_approval')

#         if_approved = prefect.tasks.FunctionTask(
#             fn=lambda: 2, name='do_something_if_approved')
#         if_not_approved = prefect.tasks.FunctionTask(
#             fn=lambda: 3, name='do_something_if_not_approved')

#         prefect.ifelse(
#             wait_for_approval,
#             true_task=if_approved,
#             false_task=if_not_approved)

#     run_flow_runner_test(flow=f, expected_state=FlowRunState.SUCCESS)

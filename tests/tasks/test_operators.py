import pytest

import prefect
from prefect.flow import Flow
from prefect.tasks.core import operators as ops
from prefect.utilities.tests import run_flow_runner_test
from prefect.state import FlowRunState, TaskRunState


def check_operator_flow(flow, task_name, result):
    run_flow_runner_test(
        flow=flow,
        expected_state=FlowRunState.SUCCESS,
        expected_task_states={
            task_name: TaskRunState(TaskRunState.SUCCESS, result=result)
        })


def test_and():
    with Flow('test') as flow:
        ops.And().set(x=True, y=True)
    check_operator_flow(flow, 'And', True)

    with Flow('test') as flow:
        ops.And().set(x=True, y=False)
    check_operator_flow(flow, 'And', False)


def test_or():

    with Flow('test') as flow:
        ops.Or().set(x=True, y=True)
    check_operator_flow(flow, 'Or', True)

    with Flow('test') as flow:
        ops.Or().set(x=True, y=False)
    check_operator_flow(flow, 'Or', True)


def test_eq():

    with Flow('test') as flow:
        ops.Eq().set(x=1, y=1)
    check_operator_flow(flow, 'Eq', True)

    with Flow('test') as flow:
        ops.Eq().set(x=1, y=2)
    check_operator_flow(flow, 'Eq', False)


def test_neq():

    with Flow('test') as flow:
        ops.Neq().set(x=1, y=1)
    check_operator_flow(flow, 'Neq', False)

    with Flow('test') as flow:
        ops.Neq().set(x=1, y=2)
    check_operator_flow(flow, 'Neq', True)


def test_gt():

    with Flow('test') as flow:
        ops.GT().set(x=2, y=1)
    check_operator_flow(flow, 'GT', True)

    with Flow('test') as flow:
        ops.GT().set(x=1, y=2)
    check_operator_flow(flow, 'GT', False)

    with Flow('test') as flow:
        ops.GT().set(x=1, y=1)
    check_operator_flow(flow, 'GT', False)


def test_gte():

    with Flow('test') as flow:
        ops.GTE().set(x=2, y=1)
    check_operator_flow(flow, 'GTE', True)

    with Flow('test') as flow:
        ops.GTE().set(x=1, y=2)
    check_operator_flow(flow, 'GTE', False)
    with Flow('test') as flow:
        ops.GTE().set(x=1, y=1)
    check_operator_flow(flow, 'GTE', True)


def test_lt():

    with Flow('test') as flow:
        ops.LT().set(x=2, y=1)
    check_operator_flow(flow, 'LT', False)

    with Flow('test') as flow:
        ops.LT().set(x=1, y=2)
    check_operator_flow(flow, 'LT', True)

    with Flow('test') as flow:
        ops.LT().set(x=1, y=1)
    check_operator_flow(flow, 'LT', False)


def test_lte():

    with Flow('test') as flow:
        ops.LTE().set(x=2, y=1)
    check_operator_flow(flow, 'LTE', False)

    with Flow('test') as flow:
        ops.LTE().set(x=1, y=2)
    check_operator_flow(flow, 'LTE', True)
    with Flow('test') as flow:

        ops.LTE().set(x=1, y=1)
    check_operator_flow(flow, 'LTE', True)

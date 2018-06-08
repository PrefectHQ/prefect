import pytest

import prefect
from prefect.flow import Flow
from prefect.tasks.core import operators as ops
from prefect.utilities.tests import run_flow_runner_test
from prefect.engine.state import FlowRunState, TaskRunState


def check_operator_flow(flow, task_name, result):
    run_flow_runner_test(
        flow=flow,
        expected_state=FlowRunState.SUCCESS,
        expected_task_states={
            task_name: TaskRunState(TaskRunState.SUCCESS, result=result)
        },
    )


def test_and():
    with Flow("test") as flow:
        ops.And(True, True)
    check_operator_flow(flow, "And", True)

    with Flow("test") as flow:
        ops.And(True, False)
    check_operator_flow(flow, "And", False)


def test_or():

    with Flow("test") as flow:
        ops.Or(True, True)
    check_operator_flow(flow, "Or", True)

    with Flow("test") as flow:
        ops.Or(True, False)
    check_operator_flow(flow, "Or", True)


def test_eq():

    with Flow("test") as flow:
        ops.Eq(1, 1)
    check_operator_flow(flow, "Eq", True)

    with Flow("test") as flow:
        ops.Eq(1, 2)
    check_operator_flow(flow, "Eq", False)


def test_neq():

    with Flow("test") as flow:
        ops.Neq(1, 1)
    check_operator_flow(flow, "Neq", False)

    with Flow("test") as flow:
        ops.Neq(1, 2)
    check_operator_flow(flow, "Neq", True)


def test_gt():

    with Flow("test") as flow:
        ops.GT(2, 1)
    check_operator_flow(flow, "GT", True)

    with Flow("test") as flow:
        ops.GT(1, 2)
    check_operator_flow(flow, "GT", False)

    with Flow("test") as flow:
        ops.GT(1, 1)
    check_operator_flow(flow, "GT", False)


def test_gte():

    with Flow("test") as flow:
        ops.GTE(2, 1)
    check_operator_flow(flow, "GTE", True)

    with Flow("test") as flow:
        ops.GTE(1, 2)
    check_operator_flow(flow, "GTE", False)
    with Flow("test") as flow:
        ops.GTE(1, 1)
    check_operator_flow(flow, "GTE", True)


def test_lt():

    with Flow("test") as flow:
        ops.LT(2, 1)
    check_operator_flow(flow, "LT", False)

    with Flow("test") as flow:
        ops.LT(1, 2)
    check_operator_flow(flow, "LT", True)

    with Flow("test") as flow:
        ops.LT(1, 1)
    check_operator_flow(flow, "LT", False)


def test_lte():

    with Flow("test") as flow:
        ops.LTE(2, 1)
    check_operator_flow(flow, "LTE", False)

    with Flow("test") as flow:
        ops.LTE(1, 2)
    check_operator_flow(flow, "LTE", True)
    with Flow("test") as flow:

        ops.LTE(1, 1)
    check_operator_flow(flow, "LTE", True)

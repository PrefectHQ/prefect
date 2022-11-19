import builtins

import pytest

from prefect import flow, task
from prefect.context import get_run_context
from prefect.logging.loggers import print_as_log


def test_log_prints_task_setting_is_context_managed():
    @task(log_prints=True)
    def get_builtin_print():
        return builtins.print

    @flow
    def wrapper():
        return builtins.print, get_builtin_print()

    caller_builtin_print, user_builtin_print = wrapper()

    assert caller_builtin_print is builtins.print
    assert user_builtin_print is print_as_log


def test_log_prints_flow_setting_is_context_managed():
    @flow(log_prints=True)
    def get_builtin_print():
        return builtins.print

    @flow
    def wrapper():
        return builtins.print, get_builtin_print()

    caller_builtin_print, user_builtin_print = wrapper()

    assert caller_builtin_print is builtins.print
    assert user_builtin_print is print_as_log


def test_task_inherits_log_prints_setting(caplog):
    @task
    def test_log_task():
        task_run_name = get_run_context().task_run.name
        print(f"test print from {task_run_name}")
        return task_run_name

    @flow(log_prints=True)
    def log_prints_flow():
        return test_log_task()

    with caplog.at_level("INFO"):
        task_run_name = log_prints_flow()

    assert f"test print from {task_run_name}" in caplog.text


@pytest.mark.xfail(reason="known bug")
def test_subflow_inherits_log_prints_setting(caplog):
    @flow
    def test_subflow():
        subflow_run_name = get_run_context().flow_run.name
        print(f"test message from {subflow_run_name}")
        return subflow_run_name

    @flow(log_prints=True)
    def test_flow():
        return test_subflow()

    with caplog.at_level("INFO"):
        subflow_run_name = test_flow()

    assert f"test message from {subflow_run_name}" in caplog.text

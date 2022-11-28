import builtins

import pytest

from prefect import flow, task
from prefect.context import get_run_context
from prefect.logging.loggers import print_as_log
from prefect.settings import PREFECT_LOGGING_LOG_PRINTS, temporary_settings

# Check the scope of the monkeypatching ------------------------------------------------


def test_log_prints_patch_is_scoped_to_task():
    @task(log_prints=True)
    def get_builtin_print():
        return builtins.print

    @flow
    def wrapper():
        return builtins.print, get_builtin_print()

    caller_builtin_print, user_builtin_print = wrapper()

    assert caller_builtin_print is builtins.print
    assert user_builtin_print is print_as_log


def test_log_prints_patch_is_scoped_to_subflow():
    @flow(log_prints=True)
    def get_builtin_print():
        return builtins.print

    @flow
    def wrapper():
        return builtins.print, get_builtin_print()

    caller_builtin_print, user_builtin_print = wrapper()

    assert caller_builtin_print is builtins.print
    assert user_builtin_print is print_as_log


# Check behavior when loaded from a global setting -------------------------------------


@pytest.mark.parametrize("setting_value", [True, False])
def test_root_flow_log_prints_defaults_to_setting_value(caplog, setting_value):
    @flow
    def test_flow():
        print("hello world!")

    with temporary_settings({PREFECT_LOGGING_LOG_PRINTS: setting_value}):
        test_flow()

    assert ("hello world!" in caplog.text) is setting_value


@pytest.mark.parametrize("setting_value", [True, False])
def test_task_log_prints_defaults_to_setting_value(caplog, setting_value):
    @task
    def test_task():
        print("hello world!")

    @flow
    def parent_flow():
        test_task()

    with temporary_settings({PREFECT_LOGGING_LOG_PRINTS: setting_value}):
        parent_flow()

    assert ("hello world!" in caplog.text) is setting_value


@pytest.mark.parametrize("setting_value", [True, False])
def test_subflow_log_prints_defaults_to_setting_value(caplog, setting_value):
    @flow
    def test_flow():
        print("hello world!")

    @flow
    def parent_flow():
        test_flow()

    with temporary_settings({PREFECT_LOGGING_LOG_PRINTS: setting_value}):
        parent_flow()

    assert ("hello world!" in caplog.text) is setting_value


# Check behavior when loaded from the parent setting -----------------------------------


@pytest.mark.parametrize("setting_value", [True, False])
@pytest.mark.parametrize("parent_value", [True, False])
def test_task_log_prints_inherits_parent_value(caplog, setting_value, parent_value):
    @task
    def test_task():
        print("hello world!")

    @flow(log_prints=parent_value)
    def parent_flow():
        test_task()

    # Note: The setting should have no affect here
    with temporary_settings({PREFECT_LOGGING_LOG_PRINTS: setting_value}):
        parent_flow()

    assert ("hello world!" in caplog.text) is parent_value


@pytest.mark.parametrize("setting_value", [True, False])
@pytest.mark.parametrize("parent_value", [True, False])
def test_subflow_log_prints_inherits_parent_value(caplog, setting_value, parent_value):
    @flow
    def test_subflow():
        print("hello world!")

    @flow(log_prints=parent_value)
    def parent_flow():
        return test_subflow()

    # Note: The setting should have no affect here
    with temporary_settings({PREFECT_LOGGING_LOG_PRINTS: setting_value}):
        parent_flow()

    assert ("hello world!" in caplog.text) is parent_value


@pytest.mark.parametrize("parent_value", [True, False, None])
def test_nested_subflow_log_prints_inherits_parent_value(caplog, parent_value):
    @flow
    def three():
        print("hello world!")

    @flow(log_prints=parent_value)
    def two():
        return three()

    @flow(log_prints=True)
    def one():
        return two()

    one()

    if parent_value is not False:
        assert "hello world!" in caplog.text
    else:
        assert "hello world!" not in caplog.text


# Check behavior when overriding parent settings ---------------------------------------


@pytest.mark.parametrize("parent_value", [False, None])
def test_task_can_opt_in_to_log_prints(caplog, parent_value):
    @task(log_prints=True)
    def test_task():
        task_run_name = get_run_context().task_run.name
        print(f"test print from {task_run_name}")
        return task_run_name

    @flow(log_prints=parent_value)
    def parent_flow():
        return test_task()

    printing_task_name = parent_flow()

    assert f"test print from {printing_task_name}" in caplog.text


@pytest.mark.parametrize("parent_value", [False, None])
def test_subflow_can_opt_in_to_log_prints(caplog, parent_value):
    @flow(log_prints=True)
    def test_flow():
        print("hello world!")

    @flow(log_prints=parent_value)
    def parent_flow():
        return test_flow()

    parent_flow()

    assert "hello world!" in caplog.text


def test_task_can_opt_out_of_log_prints(caplog, capsys):
    @task(log_prints=False)
    def test_task():
        task_run_name = get_run_context().task_run.name
        print(f"test print from {task_run_name}")
        return task_run_name

    @flow(log_prints=True)
    def parent_flow():
        return test_task()

    printing_task_name = parent_flow()

    assert f"test print from {printing_task_name}" not in caplog.text
    assert f"test print from {printing_task_name}" in capsys.readouterr().out


def test_subflow_can_opt_out_of_log_prints(caplog, capsys):
    @flow(log_prints=False)
    def test_flow():
        print("hello world!")

    @flow(log_prints=True)
    def parent_flow():
        return test_flow()

    parent_flow()

    assert "hello world!" not in caplog.text
    assert "hello world!" in capsys.readouterr().out


# Check .with_options can update the value ---------------------------------------------


@pytest.mark.parametrize("value", [True, False, None])
def test_task_log_prints_updated_by_with_options(value):
    @task
    def test_task():
        task_run_name = get_run_context().task_run.name
        print(f"test print from {task_run_name}")
        return task_run_name

    new_task = test_task.with_options(log_prints=value)
    assert new_task.log_prints is value


@pytest.mark.parametrize("value", [True, False, None])
def test_flow_log_prints_updated_by_with_options(value):
    @flow
    def test_flow():
        print("hello world!")

    new_flow = test_flow.with_options(log_prints=value)
    assert new_flow.log_prints is value

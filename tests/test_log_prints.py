import builtins

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


def test_log_prints_subflow_setting_is_context_managed():
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

    printing_task_name = log_prints_flow()

    assert f"test print from {printing_task_name}" in caplog.text


def test_subflow_inherits_log_prints_setting(caplog):
    @flow
    def test_subflow():
        subflow_run_name = get_run_context().flow_run.name
        print(f"test message from {subflow_run_name}")
        return subflow_run_name

    @flow(log_prints=True)
    def test_flow():
        return test_subflow()

    printing_subflow_name = test_flow()

    assert f"test message from {printing_subflow_name}" in caplog.text


def test_task_can_opt_in_when_parent_not_set(caplog):
    @task(log_prints=True)
    def test_log_task():
        task_run_name = get_run_context().task_run.name
        print(f"test print from {task_run_name}")
        return task_run_name

    @flow
    def simple_flow():
        return test_log_task()

    printing_task_name = simple_flow()

    assert f"test print from {printing_task_name}" in caplog.text


def test_subflow_can_opt_in_when_parent_not_set(caplog):
    @flow(log_prints=True)
    def test_log_flow():
        flow_run_name = get_run_context().flow_run.name
        print(f"test print from {flow_run_name}")
        return flow_run_name

    @flow
    def simple_flow():
        return test_log_flow()

    printing_flow_name = simple_flow()

    assert f"test print from {printing_flow_name}" in caplog.text


def test_task_log_prints_with_options(caplog):
    @task
    def test_log_task():
        task_run_name = get_run_context().task_run.name
        print(f"test print from {task_run_name}")
        return task_run_name

    @flow
    def log_prints_flow():
        return test_log_task.with_options(log_prints=True)()

    printing_task_name = log_prints_flow()

    assert f"test print from {printing_task_name}" in caplog.text


def test_flow_log_prints_with_options(caplog):
    @flow
    def test_log_flow():
        flow_run_name = get_run_context().flow_run.name
        print(f"test print from {flow_run_name}")
        return flow_run_name

    @flow
    def log_prints_flow():
        return test_log_flow.with_options(log_prints=True)()

    printing_subflow_name = log_prints_flow()

    assert f"test print from {printing_subflow_name}" in caplog.text


def test_task_inherits_log_prints_setting_with_options(caplog):
    @task
    def test_log_task():
        task_run_name = get_run_context().task_run.name
        print(f"test print from {task_run_name}")
        return task_run_name

    @flow
    def simple_flow():
        return test_log_task()

    modified_flow = simple_flow.with_options(log_prints=True)

    printing_task_name = modified_flow()

    assert f"test print from {printing_task_name}" in caplog.text


def test_task_can_opt_out_of_inherited_on_setting(caplog, capsys):
    @task(log_prints=False)
    def test_log_task():
        task_run_name = get_run_context().task_run.name
        print(f"test print from {task_run_name}")
        return task_run_name

    @flow(log_prints=True)
    def simple_flow():
        return test_log_task()

    printing_task_name = simple_flow()

    assert f"test print from {printing_task_name}" not in caplog.text
    assert f"test print from {printing_task_name}" in capsys.readouterr().out


def test_subflow_can_opt_out_of_inherited_on_setting(caplog, capsys):
    @flow(log_prints=False)
    def test_log_flow():
        flow_run_name = get_run_context().flow_run.name
        print(f"test print from {flow_run_name}")
        return flow_run_name

    @flow(log_prints=True)
    def simple_flow():
        return test_log_flow()

    printing_flow_name = simple_flow()

    assert f"test print from {printing_flow_name}" not in caplog.text
    assert f"test print from {printing_flow_name}" in capsys.readouterr().out


def test_task_can_opt_out_of_inherited_off_setting(caplog, capsys):
    @task(log_prints=True)
    def test_log_task():
        task_run_name = get_run_context().task_run.name
        print(f"test print from {task_run_name}")
        return task_run_name

    @flow(log_prints=False)
    def simple_flow():
        return test_log_task()

    printing_task_name = simple_flow()

    assert f"test print from {printing_task_name}" in caplog.text
    assert f"test print from {printing_task_name}" not in capsys.readouterr().out


def test_subflow_can_opt_out_of_inherited_off_setting(caplog, capsys):
    @flow(log_prints=True)
    def test_log_flow():
        flow_run_name = get_run_context().flow_run.name
        print(f"test print from {flow_run_name}")
        return flow_run_name

    @flow(log_prints=False)
    def simple_flow():
        return test_log_flow()

    printing_flow_name = simple_flow()

    assert f"test print from {printing_flow_name}" in caplog.text
    assert f"test print from {printing_flow_name}" not in capsys.readouterr().out


def test_task_with_options_can_opt_out_of_inherited_on_setting(caplog, capsys):
    @task
    def test_log_task():
        task_run_name = get_run_context().task_run.name
        print(f"test print from {task_run_name}")
        return task_run_name

    @flow(log_prints=True)
    def simple_flow():
        return test_log_task.with_options(log_prints=False)()

    printing_task_name = simple_flow()

    assert f"test print from {printing_task_name}" not in caplog.text
    assert f"test print from {printing_task_name}" in capsys.readouterr().out


def test_subflow_with_options_can_opt_out_of_inherited_on_setting(caplog, capsys):
    @flow
    def test_log_flow():
        flow_run_name = get_run_context().flow_run.name
        print(f"test print from {flow_run_name}")
        return flow_run_name

    @flow(log_prints=True)
    def simple_flow():
        return test_log_flow.with_options(log_prints=False)()

    printing_flow_name = simple_flow()

    assert f"test print from {printing_flow_name}" not in caplog.text
    assert f"test print from {printing_flow_name}" in capsys.readouterr().out


def test_task_with_options_can_opt_out_of_inherited_off_setting(caplog, capsys):
    @task
    def test_log_task():
        task_run_name = get_run_context().task_run.name
        print(f"test print from {task_run_name}")
        return task_run_name

    @flow(log_prints=False)
    def simple_flow():
        return test_log_task.with_options(log_prints=True)()

    printing_task_name = simple_flow()

    assert f"test print from {printing_task_name}" in caplog.text
    assert f"test print from {printing_task_name}" not in capsys.readouterr().out


def test_subflow_with_options_can_opt_out_of_inherited_off_setting(caplog, capsys):
    @flow
    def test_log_flow():
        flow_run_name = get_run_context().flow_run.name
        print(f"test print from {flow_run_name}")
        return flow_run_name

    @flow(log_prints=False)
    def simple_flow():
        return test_log_flow.with_options(log_prints=True)()

    printing_flow_name = simple_flow()

    assert f"test print from {printing_flow_name}" in caplog.text
    assert f"test print from {printing_flow_name}" not in capsys.readouterr().out


def test_subsubflow_inherits_log_prints_setting(caplog):
    @flow
    def test_log_flow():
        flow_run_name = get_run_context().flow_run.name
        print(f"test print from {flow_run_name}")
        return flow_run_name

    @flow
    def wrapper():
        return test_log_flow()

    @flow(log_prints=True)
    def parent():
        return wrapper()

    printing_flow_name = parent()

    assert f"test print from {printing_flow_name}" in caplog.text


def test_subsubflow_inherits_log_prints_setting_with_options(caplog):
    @flow
    def test_log_flow():
        flow_run_name = get_run_context().flow_run.name
        print(f"test print from {flow_run_name}")
        return flow_run_name

    @flow
    def wrapper():
        return test_log_flow()

    @flow
    def parent():
        return wrapper()

    printing_flow_name = parent.with_options(log_prints=True)()

    assert f"test print from {printing_flow_name}" in caplog.text


def test_subsubflow_can_opt_out_of_inherited_on_setting(caplog, capsys):
    @flow(log_prints=False)
    def test_log_flow():
        flow_run_name = get_run_context().flow_run.name
        print(f"test print from {flow_run_name}")
        return flow_run_name

    @flow
    def wrapper():
        return test_log_flow()

    @flow(log_prints=True)
    def parent():
        return wrapper()

    printing_flow_name = parent()

    assert f"test print from {printing_flow_name}" not in caplog.text
    assert f"test print from {printing_flow_name}" in capsys.readouterr().out


def test_subsubflow_can_opt_out_of_inherited_off_setting(caplog, capsys):
    @flow(log_prints=True)
    def test_log_flow():
        flow_run_name = get_run_context().flow_run.name
        print(f"test print from {flow_run_name}")
        return flow_run_name

    @flow
    def wrapper():
        return test_log_flow()

    @flow(log_prints=False)
    def parent():
        return wrapper()

    printing_flow_name = parent()

    assert f"test print from {printing_flow_name}" in caplog.text
    assert f"test print from {printing_flow_name}" not in capsys.readouterr().out


def test_subsubflow_can_opt_in_when_root_parent_not_set(caplog, capsys):
    @flow(log_prints=True)
    def test_log_flow():
        flow_run_name = get_run_context().flow_run.name
        print(f"test print from {flow_run_name}")
        return flow_run_name

    @flow
    def wrapper():
        return test_log_flow()

    @flow
    def parent():
        return wrapper()

    printing_flow_name = parent()

    assert f"test print from {printing_flow_name}" in caplog.text
    assert f"test print from {printing_flow_name}" not in capsys.readouterr().out

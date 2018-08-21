import os
import pytest

from prefect import Flow
from prefect.tasks.core.shell import ShellTask


def test_shell_initializes_and_runs_basic_cmd():
    task = ShellTask(command="echo -n 'hello world'")
    f = Flow(tasks=[task])
    out = f.run(return_tasks=[task])
    assert out.is_successful()
    assert out.result[task].result == b'hello world'


def test_shell_inherits_env():
    task = ShellTask(command="echo -n $MYTESTVAR")
    f = Flow(tasks=[task])
    os.environ['MYTESTVAR'] = '42'
    out = f.run(return_tasks=[task])
    assert out.is_successful()
    assert out.result[task].result == b'42'


def test_shell_returns_errors_as_well():
    task = ShellTask(command="ls surely_a_dir_that_doesnt_exist; exit 0")
    f = Flow(tasks=[task])
    out = f.run(return_tasks=[task])
    assert out.is_successful()
    assert out.result[task].result == b'ls: surely_a_dir_that_doesnt_exist: No such file or directory\n'

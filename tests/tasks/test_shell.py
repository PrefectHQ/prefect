import os
import pytest

from prefect import Flow
from prefect.tasks.core.shell import ShellTask


def test_shell_initializes_and_runs_basic_cmd():
    task = ShellTask(command="echo -n 'hello world'")
    f = Flow(tasks=[task])
    out = f.run(return_tasks=[task])
    assert out.is_successful()
    assert out.result[task].result == b"hello world"


def test_shell_inherits_env():
    task = ShellTask(command="echo -n $MYTESTVAR")
    f = Flow(tasks=[task])
    os.environ["MYTESTVAR"] = "42"
    out = f.run(return_tasks=[task])
    assert out.is_successful()
    assert out.result[task].result == b"42"


def test_shell_task_accepts_env():
    task = ShellTask(command="echo -n $MYTESTVAR", env=dict(MYTESTVAR="test"))
    f = Flow(tasks=[task])
    out = f.run(return_tasks=[task])
    assert out.is_successful()
    assert out.result[task].result == b"test"


def test_shell_returns_errors_as_well():
    task = ShellTask(command="ls surely_a_dir_that_doesnt_exist; exit 0")
    f = Flow(tasks=[task])
    out = f.run(return_tasks=[task])
    assert out.is_successful()
    assert (
        out.result[task].result
        == b"ls: surely_a_dir_that_doesnt_exist: No such file or directory\n"
    )


def test_shell_initializes_and_runs_multiline_cmd():
    cmd = """
    for line in $(printenv)
    do
        echo "${line#*=}"
    done
    """
    task = ShellTask(command=cmd, env={key: "test" for key in "abcdefgh"})
    f = Flow(tasks=[task])
    out = f.run(return_tasks=[task])
    assert out.is_successful()
    lines = out.result[task].result.decode().split("\n")
    test_lines = [l for l in lines if l == "test"]
    assert len(test_lines) == 8

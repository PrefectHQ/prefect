import os
import shutil
import sys
import tempfile

import pytest

from prefect import Flow
from prefect.engine import signals
from prefect.tasks.shell import ShellTask
from prefect.utilities.debug import raise_on_exception


pytest.mark.skipif(sys.platform == "win32")


def test_shell_initializes_and_runs_basic_cmd():
    with Flow(name="test") as f:
        task = ShellTask()(command="echo -n 'hello world'")
    out = f.run()
    assert out.is_successful()
    assert out.result[task].result == b"hello world"


def test_shell_initializes_with_basic_cmd():
    with Flow(name="test") as f:
        task = ShellTask(command="echo -n 'hello world'")()
    out = f.run()
    assert out.is_successful()
    assert out.result[task].result == b"hello world"


def test_shell_raises_if_no_command_provided():
    with Flow(name="test") as f:
        task = ShellTask()()

    with pytest.raises(TypeError):
        with raise_on_exception():
            out = f.run()


@pytest.mark.skipif(not bool(shutil.which("zsh")), reason="zsh not installed.")
def test_shell_runs_other_shells():
    with Flow(name="test") as f:
        task = ShellTask(shell="zsh")(command="echo -n $ZSH_NAME")
    out = f.run()
    assert out.is_successful()
    assert out.result[task].result == b"zsh"


def test_shell_inherits_env():
    with Flow(name="test") as f:
        task = ShellTask()(command="echo -n $MYTESTVAR")
    os.environ["MYTESTVAR"] = "42"
    out = f.run()
    assert out.is_successful()
    assert out.result[task].result == b"42"


def test_shell_task_accepts_env():
    with Flow(name="test") as f:
        task = ShellTask()(command="echo -n $MYTESTVAR", env=dict(MYTESTVAR="test"))
    out = f.run()
    assert out.is_successful()
    assert out.result[task].result == b"test"


def test_shell_task_env_can_be_set_at_init():
    with Flow(name="test") as f:
        task = ShellTask(env=dict(MYTESTVAR="test"))(command="echo -n $MYTESTVAR")
    out = f.run()
    assert out.is_successful()
    assert out.result[task].result == b"test"


def test_shell_returns_stderr_as_well():
    with Flow(name="test") as f:
        task = ShellTask()(command="ls surely_a_dir_that_doesnt_exist || exit 0")
    out = f.run()
    assert out.is_successful()
    assert "No such file or directory" in out.result[task].result.decode()


def test_shell_initializes_and_runs_multiline_cmd():
    cmd = """
    for line in $(printenv)
    do
        echo "${line#*=}"
    done
    """
    with Flow(name="test") as f:
        task = ShellTask()(command=cmd, env={key: "test" for key in "abcdefgh"})
    out = f.run()
    assert out.is_successful()
    lines = out.result[task].result.decode().split("\n")
    test_lines = [l for l in lines if l == "test"]
    assert len(test_lines) == 8


def test_shell_task_raises_fail_if_cmd_fails():
    with Flow(name="test") as f:
        task = ShellTask()(command="ls surely_a_dir_that_doesnt_exist")
    out = f.run()
    assert out.is_failed()
    assert "Command failed with exit code" in str(out.result[task].message)


def test_shell_task_handles_multiline_commands():
    with tempfile.TemporaryDirectory() as tempdir:
        cmd = """
        cd {}
        for file in $(ls)
        do
            cat $file
        done
        """.format(
            tempdir
        )
        with open(tempdir + "/testfile.txt", "w") as f:
            f.write("this is a test")

        with Flow(name="test") as f:
            task = ShellTask()(command=cmd)

        out = f.run()

    assert out.is_successful()
    assert out.result[task].result == b"this is a test"


def test_shell_adds_newline_to_helper_script():
    helper = "cd ~"
    task = ShellTask(helper_script=helper)
    with Flow("test") as f:
        res = task(command="ls")

    out = f.run()
    assert out.is_successful()


def test_shell_sources_helper_script_correctly():
    helper = """
    say_hi() {
        echo $1
    }
    """
    task = ShellTask(helper_script=helper)

    with Flow(name="test") as f:
        res = task(command="say_hi chris")

    out = f.run()
    assert out.is_successful()
    assert out.result[res].result == b"chris\n"

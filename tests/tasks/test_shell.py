import os
import shutil
import sys
import tempfile

import pytest

from prefect import Flow
from prefect.tasks.shell import ShellTask
from prefect.utilities.debug import raise_on_exception

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="ShellTask currently not supported on Windows"
)


def test_shell_initializes_and_runs_basic_cmd():
    with Flow(name="test") as f:
        task = ShellTask()(command="echo -n 'hello world'")
    out = f.run()
    assert out.is_successful()
    assert out.result[task].result == "hello world"


def test_shell_initializes_with_basic_cmd():
    with Flow(name="test") as f:
        task = ShellTask(command="echo -n 'hello world'")()
    out = f.run()
    assert out.is_successful()
    assert out.result[task].result == "hello world"


def test_shell_initializes_and_multiline_output_returns_last_line():
    with Flow(name="test") as f:
        task = ShellTask()(command="echo -n 'hello world\n42'")
    out = f.run()
    assert out.is_successful()
    assert out.result[task].result == "42"


def test_shell_returns_none_if_empty_output():
    with Flow(name="test") as f:
        task = ShellTask()(command="ls > /dev/null")
    out = f.run()
    assert out.is_successful()
    assert out.result[task].result is None


def test_shell_initializes_and_multiline_output_optionally_returns_all_lines():
    with Flow(name="test") as f:
        task = ShellTask(return_all=True)(command="echo -n 'hello world\n42'")
    out = f.run()
    assert out.is_successful()
    assert out.result[task].result == ["hello world", "42"]


def test_shell_raises_if_no_command_provided():
    with Flow(name="test") as f:
        ShellTask()()
    with pytest.raises(TypeError):
        with raise_on_exception():
            assert f.run()


@pytest.mark.skipif(not bool(shutil.which("zsh")), reason="zsh not installed.")
def test_shell_runs_other_shells():
    with Flow(name="test") as f:
        task = ShellTask(shell="zsh")(command="echo -n $ZSH_NAME")
    out = f.run()
    assert out.is_successful()
    assert out.result[task].result == "zsh"


def test_shell_inherits_env():
    with Flow(name="test") as f:
        task = ShellTask()(command="echo -n $MYTESTVAR")
    os.environ["MYTESTVAR"] = "42"
    out = f.run()
    assert out.is_successful()
    assert out.result[task].result == "42"


def test_shell_task_accepts_env():
    with Flow(name="test") as f:
        task = ShellTask()(command="echo -n $MYTESTVAR", env=dict(MYTESTVAR="test"))
    out = f.run()
    assert out.is_successful()
    assert out.result[task].result == "test"


def test_shell_task_env_can_be_set_at_init():
    with Flow(name="test") as f:
        task = ShellTask(env=dict(MYTESTVAR="test"))(command="echo -n $MYTESTVAR")
    out = f.run()
    assert out.is_successful()
    assert out.result[task].result == "test"


def test_shell_logs_error_on_non_zero_exit(caplog):
    with Flow(name="test") as f:
        task = ShellTask()(command="ls surely_a_dir_that_doesnt_exist")
    out = f.run()
    assert out.is_failed()

    error_log = [c for c in caplog.records if c.levelname == "ERROR"]
    assert len(error_log) == 1
    assert error_log[0].name == "prefect.ShellTask"
    assert "surely_a_dir_that_doesnt_exist" in error_log[0].message
    assert "No such file or directory" in error_log[0].message


def test_shell_initializes_and_runs_multiline_cmd():
    cmd = """
    TEST=$(cat <<-END
This is line one
This is line two
This is line three
boom!
END
)
for i in $TEST
do
    echo $i
done"""
    with Flow(name="test") as f:
        task = ShellTask()(command=cmd, env={key: "test" for key in "abcdefgh"})
    out = f.run()
    assert out.is_successful()
    assert out.result[task].result == "boom!"


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
    assert out.result[task].result == "this is a test"


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
    assert out.result[res].result == "chris"

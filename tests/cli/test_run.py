import textwrap
import sys

import pytest
from click.testing import CliRunner

from prefect.cli.run import run

SUCCESSFUL_LOCAL_STDOUT = """
Retrieving local flow... Done
Running flow locally...
Flow run succeeded!
""".lstrip()

FAILURE_LOCAL_STDOUT = """
Retrieving local flow... Done
Running flow locally...
Flow run failed!
""".lstrip()


@pytest.fixture()
def hello_world_flow_file(tmpdir):
    flow_file = tmpdir.join("flow.py")
    flow_file.write_text(
        """
        from prefect.hello_world import hello_flow
        """.strip(),
        encoding="UTF-8",
    )
    return str(flow_file)


@pytest.fixture()
def context_flow_file(tmpdir):
    flow_file = tmpdir.join("flow.py")
    flow_file.write_text(
        textwrap.dedent(
            """
            from prefect import Flow, task
            
            @task(log_stdout=True)
            def print_context_x():
                from prefect import context
                print(context.get("x"))
            
            with Flow("context-test-flow") as flow:
                print_context_x()
            """
        ),
        encoding="UTF-8",
    )
    return str(flow_file)


@pytest.fixture()
def runtime_failing_flow(tmpdir):
    flow_file = tmpdir.join("flow.py")
    flow_file.write_text(
        textwrap.dedent(
            """
            from prefect import Flow, task
            
            @task(log_stdout=True)
            def fail_task():
                raise ValueError("Some error")
            
            with Flow("fail-test-flow") as flow:
                fail_task()
            """
        ),
        encoding="UTF-8",
    )
    return str(flow_file)


@pytest.fixture()
def at_load_failing_flow(tmpdir):
    flow_file = tmpdir.join("flow.py")
    flow_file.write_text(
        textwrap.dedent(
            """
            from prefect import Flow
            
            with Flow("fail-test-flow") as flow:
                reference_an_unknown_var
            """
        ),
        encoding="UTF-8",
    )
    return str(flow_file)


def test_run_help():
    result = CliRunner().invoke(run, ["--help"])
    assert not result.exit_code
    assert "Run a flow" in result.output
    assert "Examples:" in result.output


@pytest.mark.parametrize("kind", ["path", "module"])
def test_run_local(tmpdir, kind, caplog, hello_world_flow_file):
    location = hello_world_flow_file if kind == "path" else "prefect.hello_world"

    result = CliRunner().invoke(run, [f"--{kind}", location])
    assert not result.exit_code
    assert result.output == SUCCESSFUL_LOCAL_STDOUT
    # FlowRunner logs are displayed
    assert "Hello World" in caplog.text


@pytest.mark.parametrize("log_level", ["ERROR", "DEBUG"])
def test_run_local_log_level(tmpdir, caplog, log_level):
    result = CliRunner().invoke(
        run, ["--module", "prefect.hello_world", "--log-level", log_level]
    )
    assert not result.exit_code
    assert result.output == SUCCESSFUL_LOCAL_STDOUT
    # Hello World is _not_ an error level log and should not be displayed then
    if log_level == "ERROR":
        assert "Hello World" not in caplog.text
        assert "INFO" not in caplog.text
    else:
        assert "Hello World" in caplog.text
        assert "INFO" in caplog.text
        assert "DEBUG" in caplog.text


def test_run_local_respects_quiet(caplog):
    result = CliRunner().invoke(run, ["--module", "prefect.hello_world", "--quiet"])
    assert not result.exit_code
    assert result.output == ""
    # Flow run logs are still happening for local runs
    assert "Hello World" in caplog.text


def test_run_local_respects_no_logs(caplog):
    result = CliRunner().invoke(run, ["--module", "prefect.hello_world", "--no-logs"])
    assert not result.exit_code
    # Run output still occurs
    assert result.output == SUCCESSFUL_LOCAL_STDOUT
    # Flow run logs are silenced
    assert caplog.text == ""


def test_run_local_passes_parameters(caplog, hello_world_flow_file):
    result = CliRunner().invoke(
        run, ["--module", "prefect.hello_world", "--param", 'name="foo"']
    )
    assert not result.exit_code
    # A configured section will apppear now that a parameter is set
    for line in SUCCESSFUL_LOCAL_STDOUT:
        assert line in result.output
    assert "Configured local flow run\n└── Parameters: {'name': 'foo'}" in result.output
    # Parameter was used by the flow
    assert "Hello Foo" in caplog.text


def test_run_local_passes_context(caplog, context_flow_file):
    result = CliRunner().invoke(
        run, ["--path", context_flow_file, "--context", 'x="custom-context-val"']
    )
    assert not result.exit_code
    # A configured section will apppear now that the context is set
    for line in SUCCESSFUL_LOCAL_STDOUT:
        assert line in result.output
    assert (
        "Configured local flow run\n└── Context: {'x': 'custom-context-val'}"
        in result.output
    )
    # Parameter was used by the flow
    assert "custom-context-val" in caplog.text


def test_run_passes_context(caplog, context_flow_file):
    result = CliRunner().invoke(
        run, ["--path", context_flow_file, "--context", 'x="custom-context-val"']
    )
    assert not result.exit_code
    # A configured section will apppear now that the context is set
    for line in SUCCESSFUL_LOCAL_STDOUT:
        assert line in result.output
    assert (
        "Configured local flow run\n└── Context: {'x': 'custom-context-val'}"
        in result.output
    )
    # Parameter was used by the flow
    assert "custom-context-val" in caplog.text


def test_run_local_handles_flow_run_failure(caplog, runtime_failing_flow):
    result = CliRunner().invoke(run, ["--path", runtime_failing_flow])
    assert not result.exit_code
    assert result.output == FAILURE_LOCAL_STDOUT
    # Flow runner logged exception
    assert "ValueError: Some error" in caplog.text


def test_run_local_handles_flow_load_failure_with_script_issue(at_load_failing_flow):
    result = CliRunner().invoke(run, ["--path", at_load_failing_flow])
    assert result.exit_code
    assert f"Retrieving local flow... Error" in result.output
    assert "Traceback" in result.output


@pytest.mark.skipif(
    sys.platform == "win32", reason="Full traceback displayed on Windows"
)
def test_run_local_handles_flow_load_failure_with_missing_file(tmpdir):
    missing_file = str(tmpdir.join("file"))
    result = CliRunner().invoke(run, ["--path", missing_file])
    assert result.exit_code
    assert f"Retrieving local flow... Error" in result.output
    # Instead of a traceback there is a short error
    assert "Traceback" not in result.output
    assert f"File does not exist: {missing_file!r}" in result.output


def test_run_local_handles_flow_load_failure_with_missing_module(tmpdir):
    missing_file = str(tmpdir.join("file"))
    result = CliRunner().invoke(run, ["--module", "my_very_unique_module_name"])
    assert result.exit_code
    assert f"Retrieving local flow... Error" in result.output
    # Instead of a traceback there is a short error
    assert "Traceback" not in result.output
    assert f"No module named 'my_very_unique_module_name'" in result.output


def test_run_local_handles_flow_load_failure_with_missing_module_attr(tmpdir):
    missing_file = str(tmpdir.join("file"))
    result = CliRunner().invoke(run, ["--module", "prefect.foobar"])
    assert result.exit_code
    assert f"Retrieving local flow... Error" in result.output
    # Instead of a traceback there is a short error
    assert "Traceback" not in result.output
    assert f"Module 'prefect' has no attribute 'foobar'" in result.output

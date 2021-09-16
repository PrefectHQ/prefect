import textwrap
import sys
import os
import json
import pytest
import pendulum
from click.testing import CliRunner
from unittest.mock import MagicMock

from prefect import Flow
from prefect.engine.state import Scheduled, Success, Failed, Submitted
from prefect.run_configs import UniversalRun
from prefect.storage import Local as LocalStorage
from prefect.backend import FlowRunView, FlowView
from prefect.utilities.executors import run_with_thread_timeout
from prefect.exceptions import TaskTimeoutSignal

from prefect.cli.run import load_json_key_values, run


FAILURE_LOCAL_STDOUT = """
Retrieving local flow... Done
Running flow locally...
Flow run failed!
""".lstrip()

TEST_FLOW_VIEW = FlowView(
    flow_id="flow-id",
    name="flow-name",
    settings={"key": "value"},
    run_config=UniversalRun(env={"ENV": "VAL"}),
    flow=Flow("flow"),
    serialized_flow=Flow("flow").serialize(),
    archived=False,
    project_name="project",
    flow_group_labels=["label"],
    core_version="0.0.0",
    storage=LocalStorage(stored_as_script=True, path="fake-path.py"),
)

SUCCESS_FLOW_RUN_VIEW = FlowRunView(
    flow_run_id="flow-run-id",
    name="flow-run-name",
    flow_id="flow-id",
    state=Success(message="state-1"),
    states=[],
    parameters={"param": "value"},
    context={"foo": "bar"},
    labels=["label"],
    updated_at=pendulum.now(),
    run_config=UniversalRun(),
)
# On `get_latest` return the same flow run view
SUCCESS_FLOW_RUN_VIEW.get_latest = MagicMock(return_value=SUCCESS_FLOW_RUN_VIEW)


FAILED_FLOW_RUN_VIEW = FlowRunView(
    flow_run_id="flow-run-id",
    name="flow-run-name",
    flow_id="flow-id",
    state=Failed(message="state-1"),
    states=[],
    parameters={"param": "value"},
    context={"foo": "bar"},
    labels=["label"],
    updated_at=pendulum.now(),
    run_config=UniversalRun(),
)
# On `get_latest` return the same flow run view
FAILED_FLOW_RUN_VIEW.get_latest = MagicMock(return_value=FAILED_FLOW_RUN_VIEW)


SUBMITTED_FLOW_RUN_VIEW = FlowRunView(
    flow_run_id="flow-run-id",
    name="flow-run-name",
    flow_id="flow-id",
    state=Submitted(message="state-1"),
    states=[],
    parameters={"param": "value"},
    context={"foo": "bar"},
    labels=["label"],
    updated_at=pendulum.now(),
    run_config=UniversalRun(),
)
# On `get_latest` return the same flow run view
SUBMITTED_FLOW_RUN_VIEW.get_latest = MagicMock(return_value=SUBMITTED_FLOW_RUN_VIEW)


TEST_FLOW_RUN_VIEW = FlowRunView(
    flow_run_id="flow-run-id",
    name="flow-run-name",
    flow_id="flow-id",
    state=Scheduled(message="state-1"),
    states=[],
    parameters={"param": "value"},
    context={"foo": "bar"},
    labels=["label"],
    updated_at=pendulum.now(),
    run_config=UniversalRun(),
)
# On `get_latest` return the success flow run view
TEST_FLOW_RUN_VIEW.get_latest = MagicMock(return_value=SUCCESS_FLOW_RUN_VIEW)


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
def multiflow_file(tmpdir):
    flow_file = tmpdir.join("flow.py")
    flow_file.write_text(
        textwrap.dedent(
            """
            from prefect import Flow
            
            flow_a = Flow("a")
            flow_b = Flow("b")
            """
        ),
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


@pytest.fixture()
def cloud_mocks(monkeypatch):
    class CloudMocks:
        FlowView = MagicMock()
        FlowRunView = MagicMock()
        Client = MagicMock()
        watch_flow_run = MagicMock()
        execute_flow_run_in_subprocess = MagicMock()
        sleep = MagicMock()

    mocks = CloudMocks()
    monkeypatch.setattr("prefect.cli.run.FlowView", mocks.FlowView)
    monkeypatch.setattr("prefect.cli.run.FlowRunView", mocks.FlowRunView)
    monkeypatch.setattr("prefect.cli.run.Client", mocks.Client)
    monkeypatch.setattr("prefect.cli.run.watch_flow_run", mocks.watch_flow_run)
    monkeypatch.setattr(
        "prefect.cli.run.execute_flow_run_in_subprocess",
        mocks.execute_flow_run_in_subprocess,
    )

    # Mock sleep for faster testing
    monkeypatch.setattr("prefect.cli.run.time.sleep", mocks.sleep)

    return mocks


@pytest.mark.parametrize(
    "input,output",
    [
        ("2", 2),
        ("2.0", 2.0),
        ('"2.0"', "2.0"),
        ("foo", "foo"),  # auto-quoted
        ('"foo"', "foo"),
        ("0foo", "0foo"),  # auto-quote when starting with a number
        ('{"key": "value"}', {"key": "value"}),
    ],
)
def test_load_json_key_values(input, output):
    assert load_json_key_values([f"test={input}"], "")["test"] == output


def test_run_help():
    result = CliRunner().invoke(run, ["--help"])
    assert not result.exit_code
    assert "Run a flow" in result.output
    assert "Examples:" in result.output


@pytest.mark.parametrize(
    "options",
    (
        ["--name", "hello", "--id", "fake-id"],
        ["--project", "hello", "--path", "fake-id"],
        ["--project", "hello", "--id", "fake-id"],
        ["--module", "hello", "--id", "fake-id"],
    ),
)
def test_run_lookup_help_too_many_options(options):
    result = CliRunner().invoke(run, options)
    assert result.exit_code
    assert "Received too many options to look up the flow" in result.output
    assert (
        "Look up a flow to run with one of the following option combinations"
        in result.output
    )


def test_run_lookup_help_no_options():
    result = CliRunner().invoke(run, "--param foo=1")
    assert result.exit_code
    assert "Received no options to look up the flow" in result.output
    assert (
        "Look up a flow to run with one of the following option combinations"
        in result.output
    )


def test_run_wraps_parameter_file_parsing_exception(tmpdir):
    params_file = tmpdir.join("params.json")
    params_file.write_text("not-valid-json", encoding="UTF-8")
    result = CliRunner().invoke(
        run, ["--module", "prefect.hello_world", "--param-file", str(params_file)]
    )
    assert result.exit_code
    assert "Failed to parse JSON" in result.output


def test_run_wraps_parameter_file_not_found_exception(tmpdir):
    params_file = tmpdir.join("params.json")
    result = CliRunner().invoke(
        run, ["--module", "prefect.hello_world", "--param-file", str(params_file)]
    )
    assert result.exit_code
    assert "Parameter file does not exist" in result.output


@pytest.mark.parametrize("kind", ["param", "context"])
def test_run_wraps_parameter_and_context_json_parsing_exception(tmpdir, kind):
    result = CliRunner().invoke(
        run, ["--module", "prefect.hello_world", f"--{kind}", 'x="foo"1']
    )
    assert result.exit_code
    assert (
        f"Failed to parse JSON for {kind.replace('param', 'parameter')} 'x'"
        in result.output
    )


def test_run_automatically_quotes_simple_strings():
    result = CliRunner().invoke(
        run, ["--module", "prefect.hello_world", "--param", "name=foo"]
    )
    assert not result.exit_code
    assert "Parameters: {'name': 'foo'}" in result.output


@pytest.mark.parametrize("kind", ["path", "module"])
def test_run_local(tmpdir, kind, caplog, hello_world_flow_file):
    location = hello_world_flow_file if kind == "path" else "prefect.hello_world"

    result = CliRunner().invoke(run, [f"--{kind}", location])
    assert not result.exit_code
    assert "Running flow locally..." in result.output
    assert "Flow run succeeded" in result.output
    # FlowRunner logs are displayed
    assert "Hello World" in caplog.text


@pytest.mark.parametrize("kind", ["path", "module"])
def test_run_local_allows_selection_from_multiple_flows(
    monkeypatch, multiflow_file, kind
):
    monkeypatch.syspath_prepend(os.path.dirname(os.path.abspath(multiflow_file)))

    location = multiflow_file if kind == "path" else "flow"

    result = CliRunner().invoke(run, [f"--{kind}", location, "--name", "b"])
    assert not result.exit_code
    assert "Running flow locally..." in result.output
    assert "Flow run succeeded" in result.output


@pytest.mark.parametrize("kind", ["path", "module"])
def test_run_local_asks_for_name_with_multiple_flows(tmpdir, multiflow_file, kind):
    if kind == "module":
        # Extend the sys.path so we can pull from the file like a module
        orig_sys_path = sys.path.copy()
        sys.path.insert(0, os.path.dirname(os.path.abspath(multiflow_file)))

    location = multiflow_file if kind == "path" else "flow"

    result = CliRunner().invoke(run, [f"--{kind}", location])

    assert result.exit_code
    assert (
        f"Found multiple flows at {location!r}: 'a', 'b'\n\nSpecify a flow name to run"
        in result.output
    )

    if kind == "module":
        sys.path = orig_sys_path


@pytest.mark.parametrize("log_level", ["ERROR", "DEBUG"])
def test_run_local_log_level(tmpdir, caplog, log_level):
    result = CliRunner().invoke(
        run, ["--module", "prefect.hello_world", "--log-level", log_level]
    )
    assert not result.exit_code
    assert "Running flow locally..." in result.output
    assert "Flow run succeeded" in result.output
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
    # CLI output is not there
    assert "Running flow locally..." not in result.output
    # Flow run logs are still happening for local runs
    assert "Hello World" in caplog.text


def test_run_local_respects_no_logs(caplog):
    result = CliRunner().invoke(run, ["--module", "prefect.hello_world", "--no-logs"])
    assert not result.exit_code
    # Run output still occurs
    assert "Running flow locally..." in result.output
    assert "Flow run succeeded" in result.output
    # Flow run logs are silenced
    assert caplog.text == ""


def test_run_local_passes_parameters(caplog):
    result = CliRunner().invoke(
        run, ["--module", "prefect.hello_world", "--param", 'name="foo"']
    )
    assert not result.exit_code
    assert "Running flow locally..." in result.output
    assert "Flow run succeeded" in result.output
    # A configured section will apppear now that a parameter is set
    assert "Configured local flow run\n└── Parameters: {'name': 'foo'}" in result.output
    # Parameter was used by the flow
    assert "Hello Foo" in caplog.text


def test_run_local_passes_parameters_from_file(caplog, tmpdir):
    params_file = tmpdir.join("params.json")
    params_file.write_text(json.dumps({"name": "foo"}), encoding="UTF-8")
    result = CliRunner().invoke(
        run, ["--module", "prefect.hello_world", "--param-file", str(params_file)]
    )
    assert not result.exit_code
    assert "Running flow locally..." in result.output
    assert "Flow run succeeded" in result.output
    # A configured section will apppear now that a parameter is set
    assert "Configured local flow run\n└── Parameters: {'name': 'foo'}" in result.output
    # Parameter was used by the flow
    assert "Hello Foo" in caplog.text


def test_run_local_passes_context(caplog, context_flow_file):
    result = CliRunner().invoke(
        run, ["--path", context_flow_file, "--context", 'x="custom-context-val"']
    )
    assert not result.exit_code
    assert "Running flow locally..." in result.output
    assert "Flow run succeeded" in result.output
    # A configured section will apppear now that the context is set
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
    assert "Running flow locally..." in result.output
    assert "Flow run succeeded" in result.output
    # A configured section will apppear now that the context is set
    assert (
        "Configured local flow run\n└── Context: {'x': 'custom-context-val'}"
        in result.output
    )
    # Parameter was used by the flow
    assert "custom-context-val" in caplog.text


def test_run_local_handles_flow_run_failure(caplog, runtime_failing_flow):
    result = CliRunner().invoke(run, ["--path", runtime_failing_flow])
    assert result.exit_code == 1
    assert "Running flow locally..." in result.output
    assert "Flow run failed" in result.output
    # Flow runner logged exception
    assert "ValueError: Some error" in caplog.text


def test_run_local_handles_flow_load_failure_with_script_issue(at_load_failing_flow):
    result = CliRunner().invoke(run, ["--path", at_load_failing_flow])
    assert result.exit_code
    assert "Retrieving local flow... Error" in result.output
    assert "Traceback" in result.output


@pytest.mark.skipif(
    sys.platform == "win32", reason="Full traceback displayed on Windows"
)
def test_run_local_handles_flow_load_failure_with_missing_file(tmpdir):
    missing_file = str(tmpdir.join("file"))
    result = CliRunner().invoke(run, ["--path", missing_file])
    assert result.exit_code
    assert "Retrieving local flow... Error" in result.output
    # Instead of a traceback there is a short error
    assert "Traceback" not in result.output
    assert f"File does not exist: {missing_file!r}" in result.output


def test_run_local_handles_flow_load_failure_with_missing_module(tmpdir):
    result = CliRunner().invoke(run, ["--module", "my_very_unique_module_name"])
    assert result.exit_code
    assert "Retrieving local flow... Error" in result.output
    # Instead of a traceback there is a short error
    assert "Traceback" not in result.output
    assert "No module named 'my_very_unique_module_name'" in result.output


def test_run_local_handles_flow_load_failure_with_missing_module_attr(tmpdir):
    result = CliRunner().invoke(run, ["--module", "prefect.foobar"])
    assert result.exit_code
    assert "Retrieving local flow... Error" in result.output
    # Instead of a traceback there is a short error
    assert "Traceback" not in result.output
    assert "Module 'prefect' has no attribute 'foobar'" in result.output


@pytest.mark.parametrize("execute_flag", (["--execute"], []))
@pytest.mark.parametrize(
    "cli_args,cloud_kwargs",
    [
        (
            ["--param", "a=2", "--param", "b=[1,2,3]"],
            dict(parameters={"a": 2, "b": [1, 2, 3]}),
        ),
        (
            ["--context", "a=1", "--context", 'b={"nested": 2}'],
            dict(context={"a": 1, "b": {"nested": 2}}),
        ),
        (["--label", "foo", "--label", "bar"], dict(labels=["foo", "bar"])),
        (["--run-name", "my-run"], dict(run_name="my-run")),
        (
            ["--log-level", "DEBUG"],
            dict(
                run_config=UniversalRun(
                    # Notice this tests for ENV merging
                    env={"ENV": "VAL", "PREFECT__LOGGING__LEVEL": "DEBUG"}
                )
            ),
        ),
        (
            # No logs does not alter the log level for cloud runs, we just don't query
            # for them in `watch_flow_run`
            ["--no-logs"],
            dict(),
        ),
        (["--idempotency-key", "foo-key"], dict(idempotency_key="foo-key")),
    ],
)
def test_run_cloud_creates_flow_run(
    cloud_mocks, cli_args, cloud_kwargs, execute_flag, monkeypatch
):
    cloud_mocks.FlowView.from_flow_id.return_value = TEST_FLOW_VIEW
    cloud_mocks.FlowRunView.from_flow_run_id.return_value = TEST_FLOW_RUN_VIEW

    if execute_flag:
        # Create a preset unique id for the agentless run label for easy determinism
        monkeypatch.setattr(
            "prefect.cli.run.uuid.uuid4", MagicMock(return_value="0" * 36)
        )

    result = CliRunner().invoke(run, ["--id", "flow-id"] + cli_args + execute_flag)

    assert not result.exit_code

    cloud_kwargs = cloud_kwargs.copy()  # Copy before mutating the pytest param dicts
    cloud_kwargs.setdefault("parameters", {})
    cloud_kwargs.setdefault("context", {})
    cloud_kwargs.setdefault("labels", None)
    cloud_kwargs.setdefault("run_name", None)
    cloud_kwargs.setdefault("run_config", None)
    cloud_kwargs.setdefault("idempotency_key", None)

    if execute_flag:
        labels = cloud_kwargs["labels"] or []
        cloud_kwargs["labels"] = labels + ["agentless-run-00000000"]

    cloud_mocks.Client().create_flow_run.assert_called_once_with(
        flow_id=TEST_FLOW_VIEW.flow_id,
        **cloud_kwargs,
    )

    if not execute_flag:
        # Called once to retrieve information
        cloud_mocks.FlowRunView.from_flow_run_id.assert_called_once()
    else:
        # Called again later to check final state
        assert cloud_mocks.FlowRunView.from_flow_run_id.call_count == 2


def test_run_cloud_handles_create_flow_run_failure(cloud_mocks):
    cloud_mocks.FlowView.from_flow_id.return_value = TEST_FLOW_VIEW
    cloud_mocks.Client().create_flow_run.side_effect = ValueError("Foo!")

    result = CliRunner().invoke(run, ["--id", "flow-id"])

    assert result.exit_code
    assert "Creating run for flow 'flow-name'... Error" in result.output
    assert "Traceback" in result.output
    assert "ValueError: Foo!" in result.output


def test_run_cloud_handles_keyboard_interrupt_during_create_flow_run(cloud_mocks):
    cloud_mocks.FlowView.from_flow_id.return_value = TEST_FLOW_VIEW
    cloud_mocks.Client().create_flow_run.side_effect = KeyboardInterrupt

    result = CliRunner().invoke(run, ["--id", "flow-id"])

    assert not result.exit_code
    assert "Creating run for flow 'flow-name'..." in result.output
    assert "Keyboard interrupt detected! Aborting..." in result.output
    assert "Aborted." in result.output


def test_run_cloud_handles_keyboard_interrupt_during_flow_run_info(cloud_mocks):
    # This test differs from `...interrupt_during_create_flow_run` in that the flow
    # run is created and the user has cancelled during metadata retrieval so we need
    # to actually cancel the run
    cloud_mocks.FlowView.from_flow_id.return_value = TEST_FLOW_VIEW
    cloud_mocks.Client().create_flow_run.return_value = "fake-run-id"
    cloud_mocks.FlowRunView.from_flow_run_id.side_effect = KeyboardInterrupt

    result = CliRunner().invoke(run, ["--id", "flow-id"])

    assert not result.exit_code
    assert "Creating run for flow 'flow-name'..." in result.output
    assert "Keyboard interrupt detected! Aborting..." in result.output
    assert "Cancelled flow run." in result.output
    cloud_mocks.Client().cancel_flow_run.assert_called_once_with(
        flow_run_id="fake-run-id"
    )


def test_run_cloud_respects_quiet(cloud_mocks):
    cloud_mocks.FlowRunView.from_flow_run_id.return_value = TEST_FLOW_RUN_VIEW
    cloud_mocks.Client().create_flow_run.return_value = "fake-run-id"

    result = CliRunner().invoke(run, ["--id", "flow-id", "--quiet"])

    assert not result.exit_code
    assert result.output == "fake-run-id\n"


@pytest.mark.parametrize("watch", [True, False])
def test_run_cloud_watch(cloud_mocks, watch):
    cloud_mocks.FlowRunView.from_flow_run_id.return_value = TEST_FLOW_RUN_VIEW
    cloud_mocks.Client().create_flow_run.return_value = "fake-run-id"

    result = CliRunner().invoke(
        run, ["--id", "flow-id"] + (["--watch"] if watch else [])
    )

    assert not result.exit_code

    if watch:
        cloud_mocks.watch_flow_run.assert_called_once()
        assert cloud_mocks.watch_flow_run.call_args[1]["flow_run_id"] == "fake-run-id"
    else:
        cloud_mocks.watch_flow_run.assert_not_called()


def test_run_cloud_watch_respects_no_logs(cloud_mocks):
    cloud_mocks.FlowRunView.from_flow_run_id.return_value = TEST_FLOW_RUN_VIEW

    result = CliRunner().invoke(run, ["--id", "flow-id", "--watch", "--no-logs"])

    assert not result.exit_code
    cloud_mocks.watch_flow_run.assert_called_once()
    assert cloud_mocks.watch_flow_run.call_args[1]["stream_logs"] is False


def test_run_cloud_lookup_by_flow_id(cloud_mocks):
    cloud_mocks.FlowRunView.from_flow_run_id.return_value = TEST_FLOW_RUN_VIEW
    result = CliRunner().invoke(run, ["--id", "flow-id"])

    assert not result.exit_code
    assert "Looking up flow metadata... Done" in result.output

    cloud_mocks.FlowView.from_flow_id.assert_called_once_with("flow-id")


def test_run_cloud_lookup_by_flow_group_id(cloud_mocks):
    cloud_mocks.FlowView.from_flow_id.side_effect = ValueError()  # flow id is not found
    cloud_mocks.FlowView.from_flow_group_id.return_value = TEST_FLOW_VIEW
    cloud_mocks.FlowRunView.from_flow_run_id.return_value = TEST_FLOW_RUN_VIEW

    result = CliRunner().invoke(run, ["--id", "flow-id"])
    assert not result.exit_code
    assert "Looking up flow metadata... Done" in result.output

    cloud_mocks.FlowView.from_flow_id.assert_called_once_with("flow-id")


@pytest.mark.parametrize("with_project", [True, False])
def test_run_cloud_lookup_by_name(cloud_mocks, with_project):
    cloud_mocks.FlowRunView.from_flow_run_id.return_value = TEST_FLOW_RUN_VIEW

    result = CliRunner().invoke(
        run,
        ["--name", "flow-name"]
        + (["--project", "project-name"] if with_project else []),
    )
    assert not result.exit_code
    assert "Looking up flow metadata... Done" in result.output

    expected = {"flow_name": "flow-name"}
    if with_project:
        expected["project_name"] = "project-name"

    cloud_mocks.FlowView.from_flow_name.assert_called_once_with(**expected)


def test_run_cloud_handles_ids_not_found(cloud_mocks):
    cloud_mocks.FlowView.from_flow_id.side_effect = ValueError()  # flow id is not found
    cloud_mocks.FlowView.from_flow_group_id.side_effect = ValueError()

    result = CliRunner().invoke(run, ["--id", "flow-id"])

    assert result.exit_code
    assert "Looking up flow metadata... Error" in result.output
    assert "Failed to find flow id or flow group id" in result.output
    assert "Traceback" not in result.output


def test_run_cloud_displays_name_lookup_errors(cloud_mocks):
    cloud_mocks.FlowView.from_flow_name.side_effect = ValueError("Example error")
    result = CliRunner().invoke(run, ["--name", "foo"])

    assert result.exit_code
    assert "Looking up flow metadata... Error" in result.output
    # TODO: Note this error message could be wrapped for a better UX
    assert "Example error" in result.output


def test_run_cloud_handles_project_without_name(cloud_mocks):
    cloud_mocks.FlowView.from_flow_name.side_effect = ValueError("No results found")
    result = CliRunner().invoke(run, ["--project", "foo"])

    assert result.exit_code
    assert "Looking up flow metadata... Error" in result.output
    assert (
        "Missing required option `--name`. Cannot look up a flow by project without "
        "also passing a name." in result.output
    )


def test_run_cloud_displays_flow_run_data(cloud_mocks):
    cloud_mocks.FlowRunView.from_flow_run_id.return_value = TEST_FLOW_RUN_VIEW
    cloud_mocks.Client.return_value.get_cloud_url.return_value = "fake-url"

    result = CliRunner().invoke(run, ["--id", "flow-id"])

    assert not result.exit_code
    assert (
        textwrap.dedent(
            """
        └── Name: flow-run-name
        └── UUID: flow-run-id
        └── Labels: ['label']
        └── Parameters: {'param': 'value'}
        └── Context: {'foo': 'bar'}
        └── URL: fake-url
        """
        )
        in result.output
    )


@pytest.mark.parametrize(
    "run_result", [FAILED_FLOW_RUN_VIEW, SUCCESS_FLOW_RUN_VIEW, SUBMITTED_FLOW_RUN_VIEW]
)
@pytest.mark.parametrize("flag", ["--execute", "--watch"])
def test_run_cloud_exit_code_reflects_final_run_state_when_watched_or_executed(
    cloud_mocks, flag, run_result
):
    cloud_mocks.Client().create_flow_run.return_value = "fake-run-id"
    cloud_mocks.FlowRunView.from_flow_run_id.return_value = run_result
    result = CliRunner().invoke(run, ["--id", "flow-id"] + [flag])

    if run_result != SUCCESS_FLOW_RUN_VIEW:
        assert result.exit_code == 1
    else:
        assert not result.exit_code


def test_run_cloud_execute_calls_subprocess(cloud_mocks):
    cloud_mocks.Client().create_flow_run.return_value = "fake-run-id"
    cloud_mocks.FlowRunView.from_flow_run_id.return_value = TEST_FLOW_RUN_VIEW
    result = CliRunner().invoke(run, ["--id", "flow-id", "--execute"])

    assert not result.exit_code
    assert "Executing flow run..." in result.output

    cloud_mocks.execute_flow_run_in_subprocess.assert_called_once_with("fake-run-id")


def test_run_cloud_execute_respects_quiet(cloud_mocks):
    cloud_mocks.FlowRunView.from_flow_run_id.return_value = TEST_FLOW_RUN_VIEW
    cloud_mocks.Client().create_flow_run.return_value = "fake-run-id"

    def show_a_log(*args, **kwargs):
        from prefect.utilities.logging import get_logger

        get_logger().error("LOG MESSAGE!")

    cloud_mocks.execute_flow_run_in_subprocess.side_effect = show_a_log

    result = CliRunner().invoke(run, ["--id", "flow-id", "--quiet", "--execute"])

    assert not result.exit_code
    assert result.output == "fake-run-id\n"


def test_run_cloud_execute_respects_no_logs(cloud_mocks):
    cloud_mocks.FlowRunView.from_flow_run_id.return_value = TEST_FLOW_RUN_VIEW

    def show_a_log(*args, **kwargs):
        from prefect.utilities.logging import get_logger

        get_logger().error("LOG MESSAGE!")

    cloud_mocks.execute_flow_run_in_subprocess.side_effect = show_a_log

    result = CliRunner().invoke(run, ["--id", "flow-id", "--no-logs", "--execute"])

    assert not result.exit_code
    # CLI messages display
    assert "Executing flow run..." in result.output
    # Run logs do not
    assert "LOG MESSAGE" not in result.output


def test_run_local_with_schedule(monkeypatch):
    mock_flow = MagicMock()

    def mock_get_flow_from_path_or_module(*args, **kwargs):
        return mock_flow

    monkeypatch.setattr(
        "prefect.cli.run.get_flow_from_path_or_module",
        mock_get_flow_from_path_or_module,
    )
    CliRunner().invoke(run, ["--path", hello_world_flow_file, "--schedule"])

    mock_flow.run.assert_called_once_with(parameters={}, run_on_schedule=True)


def test_run_cloud_with_schedule_fails():
    result = CliRunner().invoke(run, ["--id", "fake-run-id", "--schedule"])

    assert result.exit_code == 1
    assert "`--schedule` can only be specified for local flow runs" in result.output

    result = CliRunner().invoke(run, ["--name", "fake-run-name", "--schedule"])
    assert result.exit_code == 1
    assert "`--schedule` can only be specified for local flow runs" in result.output

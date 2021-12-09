import subprocess
import sys
from unittest.mock import MagicMock

import anyio
import pydantic
import pytest
from typing_extensions import Literal

from prefect.flow_runners import (
    FlowRunner,
    SubprocessFlowRunner,
    UniversalFlowRunner,
    lookup_flow_runner,
    register_flow_runner,
)
from prefect.orion.schemas.core import FlowRunnerSettings


if sys.version_info < (3, 8):
    # https://docs.python.org/3/library/unittest.mock.html#unittest.mock.AsyncMock

    from mock import AsyncMock
else:
    from unittest.mock import AsyncMock


class TestFlowRunner:
    def test_has_no_type(self):
        with pytest.raises(pydantic.ValidationError):
            FlowRunner()

    async def test_does_not_implement_submission(self):
        with pytest.raises(NotImplementedError):
            await FlowRunner(typename="test").submit_flow_run(None, None)

    def test_logger_based_on_name(self):
        assert FlowRunner(typename="foobar").logger.name == "prefect.flow_runner.foobar"


class TestFlowRunnerDispatch:
    def test_register_and_lookup(self):
        @register_flow_runner
        class TestFlowRunner(FlowRunner):
            typename: Literal["test"] = "test"

        assert lookup_flow_runner("test") == TestFlowRunner

    def test_to_settings(self):
        flow_runner = UniversalFlowRunner(env={"foo": "bar"})
        assert flow_runner.to_settings() == FlowRunnerSettings(
            type="universal", config={"env": {"foo": "bar"}}
        )

    def test_from_settings(self):
        settings = FlowRunnerSettings(type="universal", config={"env": {"foo": "bar"}})
        assert FlowRunner.from_settings(settings) == UniversalFlowRunner(
            env={"foo": "bar"}
        )


class TestUniversalFlowRunner:
    def test_unner_type(self):
        assert UniversalFlowRunner().typename == "universal"

    async def test_raises_submission_error(self):
        with pytest.raises(
            RuntimeError,
            match="universal flow runner cannot be used to submit flow runs",
        ):
            await UniversalFlowRunner().submit_flow_run(None, None)


class TestSubprocessFlowRunner:
    def test_runner_type(self):
        assert SubprocessFlowRunner().typename == "subprocess"

    async def test_creates_subprocess_then_marks_as_started(
        self, monkeypatch, flow_run
    ):
        monkeypatch.setattr("anyio.open_process", AsyncMock())
        fake_status = MagicMock()
        # By raising an exception when started is called we can assert the process
        # is opened before this time
        fake_status.started.side_effect = RuntimeError("Started called!")

        with pytest.raises(RuntimeError, match="Started called!"):
            await SubprocessFlowRunner().submit_flow_run(flow_run, fake_status)

        fake_status.started.assert_called_once()

        anyio.open_process.assert_awaited_once_with(
            ["python", "-m", "prefect.engine", flow_run.id.hex],
            stderr=subprocess.STDOUT,
        )

    async def test_executes_flow_run(self, deployment, capsys, orion_client):
        fake_status = MagicMock()

        flow_run = await orion_client.create_flow_run_from_deployment(deployment.id)

        successful = await SubprocessFlowRunner().submit_flow_run(flow_run, fake_status)

        assert successful
        fake_status.started.assert_called_once()
        assert (await orion_client.read_flow_run(flow_run.id)).state.is_completed()

    @pytest.mark.parametrize("stream_output", [True, False])
    async def test_stream_output_controls_local_printing(
        self, deployment, capsys, orion_client, stream_output
    ):
        fake_status = MagicMock()

        flow_run = await orion_client.create_flow_run_from_deployment(deployment.id)

        assert await SubprocessFlowRunner(stream_output=stream_output).submit_flow_run(
            flow_run, fake_status
        )

        output = capsys.readouterr()
        assert output.err == "", "stderr is never populated"

        if not stream_output:
            assert output.out == ""
        else:
            assert "Beginning flow run" in output.out, "Log from the engine is present"
            assert "\n\n" not in output.out, "Line endings are not double terminated"


# The following tests are for configuration options and can test all relevant types


@pytest.mark.parametrize("runner_type", [UniversalFlowRunner, SubprocessFlowRunner])
class TestFlowRunnerEnv:
    def test_flow_runner_env_config(self, runner_type):
        assert runner_type(env={"foo": "bar"}).env == {"foo": "bar"}

    def test_flow_runner_env_config_casts_to_strings(self, runner_type):
        assert runner_type(env={"foo": 1}).env == {"foo": "1"}

    def test_flow_runner_env_config_errors_if_not_castable(self, runner_type):
        with pytest.raises(pydantic.ValidationError):
            runner_type(env={"foo": object()})

    def test_flow_runner_env_to_settings(self, runner_type):
        runner = runner_type(env={"foo": "bar"})
        settings = runner.to_settings()
        assert settings.config["env"] == runner.env


@pytest.mark.parametrize("runner_type", [SubprocessFlowRunner])
class TestFlowRunnerStreamOutput:
    def test_flow_runner_stream_output_config(self, runner_type):
        assert runner_type(stream_output=True).stream_output == True

    def test_flow_runner_stream_output_config_casts_to_bool(self, runner_type):
        assert runner_type(stream_output=1).stream_output == True

    def test_flow_runner_stream_output_config_errors_if_not_castable(self, runner_type):
        with pytest.raises(pydantic.ValidationError):
            runner_type(stream_output=object())

    @pytest.mark.parametrize("value", [True, False])
    def test_flow_runner_stream_output_to_settings(self, runner_type, value):
        runner = runner_type(stream_output=value)
        settings = runner.to_settings()
        assert settings.config["stream_output"] == value

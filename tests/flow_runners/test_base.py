import os
import sys
from pathlib import Path
from typing import NamedTuple

import pydantic
import pytest
from typing_extensions import Literal

from prefect.flow_runners import (
    DockerFlowRunner,
    FlowRunner,
    SubprocessFlowRunner,
    UniversalFlowRunner,
    base_flow_run_environment,
    get_prefect_image_name,
    lookup_flow_runner,
    python_version_minor,
    register_flow_runner,
)
from prefect.orion.schemas.core import FlowRunnerSettings
from prefect.settings import PREFECT_API_KEY, SETTING_VARIABLES, temporary_settings


class VersionInfo(NamedTuple):
    major: int
    minor: int
    micro: int
    releaselevel: str
    serial: int


def fake_python_version(
    major=sys.version_info.major,
    minor=sys.version_info.minor,
    micro=sys.version_info.micro,
    releaselevel=sys.version_info.releaselevel,
    serial=sys.version_info.serial,
):
    return VersionInfo(major, minor, micro, releaselevel, serial)


class TestFlowRunner:
    def test_has_no_type(self):
        with pytest.raises(pydantic.ValidationError):
            FlowRunner()

    async def test_does_not_implement_submission(self):
        with pytest.raises(NotImplementedError):
            await FlowRunner(typename="test").submit_flow_run(None, None)

    def test_logger_based_on_name(self):
        assert FlowRunner(typename="foobar").logger.name == "prefect.flow_runner.foobar"


class TestFlowRunnerRegistration:
    def test_register_and_lookup(self):
        @register_flow_runner
        class TestFlowRunnerConfig(FlowRunner):
            typename: Literal["test"] = "test"

        assert lookup_flow_runner("test") == TestFlowRunnerConfig

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


class TestBaseFlowRunEnvironment:
    def test_includes_all_set_settings(self):
        assert {
            setting.name: setting.value()
            for setting in SETTING_VARIABLES.values()
            if setting.value() is not None
        }

    def test_drops_null_settings(self):
        with temporary_settings(updates={PREFECT_API_KEY: None}):
            assert "PREFECT_API_KEY" not in base_flow_run_environment()


class TestUniversalFlowRunner:
    def test_unner_type(self):
        assert UniversalFlowRunner().typename == "universal"

    async def test_raises_submission_error(self):
        with pytest.raises(
            RuntimeError,
            match="universal flow runner cannot be used to submit flow runs",
        ):
            await UniversalFlowRunner().submit_flow_run(None, None)


class TestGetPrefectImageName:
    async def test_tag_includes_python_minor_version(self, monkeypatch):
        monkeypatch.setattr("prefect.__version__", "2.0.0")
        assert (
            get_prefect_image_name()
            == f"prefecthq/prefect:2.0.0-python{python_version_minor()}"
        )

    @pytest.mark.parametrize("prerelease", ["a", "a5", "b1", "rc2"])
    async def test_tag_includes_prereleases(self, monkeypatch, prerelease):
        monkeypatch.setattr("prefect.__version__", "2.0.0" + prerelease)
        assert (
            get_prefect_image_name()
            == f"prefecthq/prefect:2.0.0{prerelease}-python{python_version_minor()}"
        )

    async def test_tag_detects_development(self, monkeypatch):
        monkeypatch.setattr("prefect.__version__", "2.0.0+5.g6fcc2b9a")
        monkeypatch.setattr("sys.version_info", fake_python_version(major=3, minor=10))
        assert get_prefect_image_name() == "prefecthq/prefect:dev-python3.10"


# The following tests are for configuration options and can test all relevant types


@pytest.mark.parametrize(
    "runner_type", [UniversalFlowRunner, SubprocessFlowRunner, DockerFlowRunner]
)
class TestFlowRunnerConfigEnv:
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


@pytest.mark.parametrize("runner_type", [SubprocessFlowRunner, DockerFlowRunner])
class TestFlowRunnerConfigStreamOutput:
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


@pytest.mark.parametrize("runner_type", [SubprocessFlowRunner])
class TestFlowRunnerConfigCondaEnv:
    @pytest.mark.parametrize("value", ["test", Path("test")])
    def test_flow_runner_condaenv_config(self, runner_type, value):
        assert runner_type(condaenv=value).condaenv == value

    def test_flow_runner_condaenv_config_casts_to_string(self, runner_type):
        assert runner_type(condaenv=1).condaenv == "1"

    @pytest.mark.parametrize("value", [f"~{os.sep}test", f"{os.sep}test"])
    def test_flow_runner_condaenv_config_casts_to_path(self, runner_type, value):
        assert runner_type(condaenv=value).condaenv == Path(value)

    def test_flow_runner_condaenv_config_errors_if_not_castable(self, runner_type):
        with pytest.raises(pydantic.ValidationError):
            runner_type(condaenv=object())

    @pytest.mark.parametrize("value", ["test", Path("test")])
    def test_flow_runner_condaenv_to_settings(self, runner_type, value):
        runner = runner_type(condaenv=value)
        settings = runner.to_settings()
        assert settings.config["condaenv"] == value

    def test_flow_runner_condaenv_cannot_be_provided_with_virtualenv(self, runner_type):
        with pytest.raises(
            pydantic.ValidationError, match="cannot provide both a conda and virtualenv"
        ):
            runner_type(condaenv="foo", virtualenv="bar")


@pytest.mark.parametrize("runner_type", [SubprocessFlowRunner])
class TestFlowRunnerConfigVirtualEnv:
    def test_flow_runner_virtualenv_config(self, runner_type):
        path = Path("~").expanduser()
        assert runner_type(virtualenv=path).virtualenv == path

    def test_flow_runner_virtualenv_config_casts_to_path(self, runner_type):
        assert runner_type(virtualenv="~/test").virtualenv == Path("~/test")
        assert (
            Path("~/test") != Path("~/test").expanduser()
        ), "We do not want to expand user at configuration time"

    def test_flow_runner_virtualenv_config_errors_if_not_castable(self, runner_type):
        with pytest.raises(pydantic.ValidationError):
            runner_type(virtualenv=object())

    def test_flow_runner_virtualenv_to_settings(self, runner_type):
        runner = runner_type(virtualenv=Path("~/test"))
        settings = runner.to_settings()
        assert settings.config["virtualenv"] == Path("~/test")


@pytest.mark.parametrize("runner_type", [DockerFlowRunner])
class TestFlowRunnerConfigVolumes:
    def test_flow_runner_volumes_config(self, runner_type):
        volumes = ["a:b", "c:d"]
        assert runner_type(volumes=volumes).volumes == volumes

    def test_flow_runner_volumes_config_does_not_expand_paths(self, runner_type):
        assert runner_type(volumes=["~/a:b"]).volumes == ["~/a:b"]

    def test_flow_runner_volumes_config_casts_to_list(self, runner_type):
        assert type(runner_type(volumes={"a:b", "c:d"}).volumes) == list

    def test_flow_runner_volumes_config_errors_if_invalid_format(self, runner_type):
        with pytest.raises(
            pydantic.ValidationError, match="Invalid volume specification"
        ):
            runner_type(volumes=["a"])

    def test_flow_runner_volumes_config_errors_if_invalid_type(self, runner_type):
        with pytest.raises(pydantic.ValidationError):
            runner_type(volumes={"a": "b"})

    def test_flow_runner_volumes_to_settings(self, runner_type):
        runner = runner_type(volumes=["a:b", "c:d"])
        settings = runner.to_settings()
        assert settings.config["volumes"] == ["a:b", "c:d"]


@pytest.mark.parametrize("runner_type", [DockerFlowRunner])
class TestFlowRunnerConfigNetworks:
    def test_flow_runner_networks_config(self, runner_type):
        networks = ["a", "b"]
        assert runner_type(networks=networks).networks == networks

    def test_flow_runner_networks_config_casts_to_list(self, runner_type):
        assert type(runner_type(networks={"a", "b"}).networks) == list

    def test_flow_runner_networks_config_errors_if_invalid_type(self, runner_type):
        with pytest.raises(pydantic.ValidationError):
            runner_type(volumes={"foo": "bar"})

    def test_flow_runner_networks_to_settings(self, runner_type):
        runner = runner_type(networks=["a", "b"])
        settings = runner.to_settings()
        assert settings.config["networks"] == ["a", "b"]


@pytest.mark.parametrize("runner_type", [DockerFlowRunner])
class TestFlowRunnerConfigAutoRemove:
    def test_flow_runner_auto_remove_config(self, runner_type):
        assert runner_type(auto_remove=True).auto_remove == True

    def test_flow_runner_auto_remove_config_casts_to_bool(self, runner_type):
        assert runner_type(auto_remove=1).auto_remove == True

    def test_flow_runner_auto_remove_config_errors_if_not_castable(self, runner_type):
        with pytest.raises(pydantic.ValidationError):
            runner_type(auto_remove=object())

    @pytest.mark.parametrize("value", [True, False])
    def test_flow_runner_auto_remove_to_settings(self, runner_type, value):
        runner = runner_type(auto_remove=value)
        settings = runner.to_settings()
        assert settings.config["auto_remove"] == value


@pytest.mark.parametrize("runner_type", [DockerFlowRunner])
class TestFlowRunnerConfigImage:
    def test_flow_runner_image_config_defaults_to_orion_image(self, runner_type):
        assert runner_type().image == get_prefect_image_name()

    def test_flow_runner_image_config(self, runner_type):
        value = "foo"
        assert runner_type(image=value).image == value

    def test_flow_runner_image_config_casts_to_string(self, runner_type):
        assert runner_type(image=1).image == "1"

    def test_flow_runner_image_config_errors_if_not_castable(self, runner_type):
        with pytest.raises(pydantic.ValidationError):
            runner_type(image=object())

    def test_flow_runner_image_to_settings(self, runner_type):
        runner = runner_type(image="test")
        settings = runner.to_settings()
        assert settings.config["image"] == "test"


@pytest.mark.parametrize("runner_type", [DockerFlowRunner])
class TestFlowRunnerConfigLabels:
    def test_flow_runner_labels_config(self, runner_type):
        assert runner_type(labels={"foo": "bar"}).labels == {"foo": "bar"}

    def test_flow_runner_labels_config_casts_to_strings(self, runner_type):
        assert runner_type(labels={"foo": 1}).labels == {"foo": "1"}

    def test_flow_runner_labels_config_errors_if_not_castable(self, runner_type):
        with pytest.raises(pydantic.ValidationError):
            runner_type(labels={"foo": object()})

    def test_flow_runner_labels_to_settings(self, runner_type):
        runner = runner_type(labels={"foo": "bar"})
        settings = runner.to_settings()
        assert settings.config["labels"] == runner.labels

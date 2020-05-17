import json
import platform
import tempfile
import toml

import prefect
from prefect.utilities import diagnostics


def test_system_information():
    system_info = diagnostics.system_information()

    assert system_info["system_information"]["prefect_version"] == prefect.__version__
    assert system_info["system_information"]["platform"] == platform.platform()
    assert (
        system_info["system_information"]["python_version"] == platform.python_version()
    )


def test_config_overrides_empty():
    config_overrides = diagnostics.config_overrides()

    assert config_overrides["config_overrides"] == {}


def test_config_overrides_populated(monkeypatch):
    with tempfile.TemporaryDirectory() as tempdir:
        file = open("{}/config.toml".format(tempdir), "w+")
        toml.dump({"debug": "true"}, file)
        file.close()

        monkeypatch.setattr(
            "prefect.configuration.USER_CONFIG", "{}/config.toml".format(tempdir)
        )

        config_overrides = diagnostics.config_overrides()

        assert config_overrides["config_overrides"] == {"debug": True}


def test_config_overrides_secrets(monkeypatch):
    with tempfile.TemporaryDirectory() as tempdir:
        file = open("{}/config.toml".format(tempdir), "w+")
        toml.dump({"secrets": {"key": "value"}}, file)
        file.close()

        monkeypatch.setattr(
            "prefect.configuration.USER_CONFIG", "{}/config.toml".format(tempdir)
        )

        config_overrides = diagnostics.config_overrides(include_secret_names=True)

        assert config_overrides["config_overrides"] == {"secrets": {"key": True}}


def test_config_overrides_no_secrets(monkeypatch):
    with tempfile.TemporaryDirectory() as tempdir:
        file = open("{}/config.toml".format(tempdir), "w+")
        toml.dump({"secrets": {"key": "value"}}, file)
        file.close()

        monkeypatch.setattr(
            "prefect.configuration.USER_CONFIG", "{}/config.toml".format(tempdir)
        )

        config_overrides = diagnostics.config_overrides()

        assert config_overrides["config_overrides"] == {"secrets": False}


def test_environment_variables_populated(monkeypatch):
    monkeypatch.setenv("PREFECT__TEST", "VALUE" "NOT__PREFECT", "VALUE2")

    env_vars = diagnostics.environment_variables()

    assert "PREFECT__TEST" in env_vars["env_vars"]
    assert "NOT__PREFECT" not in env_vars["env_vars"]


def test_flow_information():
    @prefect.task
    def t1():
        pass

    @prefect.task
    def t2():
        pass

    flow = prefect.Flow(
        "test",
        tasks=[t1, t2],
        storage=prefect.environments.storage.Local(),
        schedule=prefect.schedules.Schedule(clocks=[]),
        result=prefect.engine.results.PrefectResult(),
    )

    flow_information = diagnostics.flow_information(flow)["flow_information"]
    assert flow_information

    # Type information
    assert flow_information["environment"]["type"] == "RemoteEnvironment"
    assert flow_information["storage"]["type"] == "Local"
    assert flow_information["result"]["type"] == "PrefectResult"
    assert flow_information["schedule"]["type"] == "Schedule"
    assert flow_information["task_count"] == 2

    # Kwargs presence check
    assert flow_information["environment"]["executor"] is True
    assert flow_information["environment"]["executor_kwargs"] is False
    assert flow_information["environment"]["labels"] is False
    assert flow_information["environment"]["on_start"] is False
    assert flow_information["environment"]["on_exit"] is False
    assert flow_information["environment"]["logger"] is True


def test_diagnostic_info_with_flow_no_secrets(monkeypatch):
    with tempfile.TemporaryDirectory() as tempdir:
        file = open("{}/config.toml".format(tempdir), "w+")
        toml.dump({"secrets": {"key": "value"}}, file)
        file.close()

        monkeypatch.setattr(
            "prefect.configuration.USER_CONFIG", "{}/config.toml".format(tempdir)
        )

        @prefect.task
        def t1():
            pass

        @prefect.task
        def t2():
            pass

        flow = prefect.Flow(
            "test",
            tasks=[t1, t2],
            storage=prefect.environments.storage.Local(),
            schedule=prefect.schedules.Schedule(clocks=[]),
            result=prefect.engine.results.PrefectResult(),
        )

        monkeypatch.setenv("PREFECT__TEST", "VALUE" "NOT__PREFECT", "VALUE2")

        diagnostic_info = diagnostics.diagnostic_info(flow=flow)
        diagnostic_info = json.loads(diagnostic_info)

        config_overrides = diagnostic_info["config_overrides"]
        env_vars = diagnostic_info["env_vars"]
        flow_information = diagnostic_info["flow_information"]
        system_info = diagnostic_info["system_information"]

        assert config_overrides == {"secrets": False}

        assert "PREFECT__TEST" in env_vars
        assert "NOT__PREFECT" not in env_vars

        assert flow_information

        # Type information
        assert flow_information["environment"]["type"] == "RemoteEnvironment"
        assert flow_information["storage"]["type"] == "Local"
        assert flow_information["result"]["type"] == "PrefectResult"
        assert flow_information["schedule"]["type"] == "Schedule"
        assert flow_information["task_count"] == 2

        # Kwargs presence check
        assert flow_information["environment"]["executor"] is True
        assert flow_information["environment"]["executor_kwargs"] is False
        assert flow_information["environment"]["labels"] is False
        assert flow_information["environment"]["on_start"] is False
        assert flow_information["environment"]["on_exit"] is False
        assert flow_information["environment"]["logger"] is True

        assert system_info["prefect_version"] == prefect.__version__
        assert system_info["platform"] == platform.platform()
        assert system_info["python_version"] == platform.python_version()

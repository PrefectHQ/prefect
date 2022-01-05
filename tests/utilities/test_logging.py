from unittest.mock import MagicMock

import pytest


from prefect.utilities.logging import (
    DEFAULT_LOGGING_SETTINGS_PATH,
    get_logger,
    setup_logging,
    load_logging_config,
    flow_run_logger,
    task_run_logger,
    run_logger,
)
from prefect.utilities.settings import LoggingSettings, Settings
from prefect import flow, task
from prefect.context import TaskRunContext


@pytest.fixture
def dictConfigMock(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("logging.config.dictConfig", mock)
    return mock


def test_setup_logging_uses_default_path(tmp_path, dictConfigMock):
    fake_settings = Settings(
        logging=LoggingSettings(settings_path=tmp_path.joinpath("does-not-exist.yaml"))
    )

    expected_config = load_logging_config(
        DEFAULT_LOGGING_SETTINGS_PATH, fake_settings.logging
    )

    setup_logging(fake_settings)

    dictConfigMock.assert_called_once_with(expected_config)


def test_setup_logging_uses_settings_path_if_exists(tmp_path, dictConfigMock):
    config_file = tmp_path.joinpath("exists.yaml")
    config_file.write_text("foo: bar")
    fake_settings = Settings(logging=LoggingSettings(settings_path=config_file))

    setup_logging(fake_settings)
    expected_config = load_logging_config(
        tmp_path.joinpath("exists.yaml"), fake_settings.logging
    )

    dictConfigMock.assert_called_once_with(expected_config)


def test_setup_logging_uses_env_var_overrides(tmp_path, dictConfigMock, monkeypatch):
    fake_settings = Settings(
        logging=LoggingSettings(settings_path=tmp_path.joinpath("does-not-exist.yaml"))
    )
    expected_config = load_logging_config(
        DEFAULT_LOGGING_SETTINGS_PATH, fake_settings.logging
    )

    # Test setting a simple value
    monkeypatch.setenv(
        LoggingSettings.Config.env_prefix + "LOGGERS_ROOT_LEVEL", "ROOT_LEVEL_VAL"
    )
    expected_config["loggers"]["root"]["level"] = "ROOT_LEVEL_VAL"

    # Test setting a value where the a key contains underscores
    monkeypatch.setenv(
        LoggingSettings.Config.env_prefix + "FORMATTERS_FLOW_RUNS_DATEFMT",
        "UNDERSCORE_KEY_VAL",
    )
    expected_config["formatters"]["flow_runs"]["datefmt"] = "UNDERSCORE_KEY_VAL"

    # Test setting a value where the key contains a period
    monkeypatch.setenv(
        LoggingSettings.Config.env_prefix + "LOGGERS_PREFECT_FLOW_RUNS_LEVEL",
        "FLOW_RUN_VAL",
    )
    expected_config["loggers"]["prefect.flow_runs"]["level"] = "FLOW_RUN_VAL"

    # Test setting a value that does not exist in the yaml config and should not be
    # set in the expected_config since there is no value to override
    monkeypatch.setenv(LoggingSettings.Config.env_prefix + "_FOO", "IGNORED")

    setup_logging(fake_settings)

    dictConfigMock.assert_called_once_with(expected_config)


@pytest.mark.parametrize("name", ["default", None, ""])
def test_get_logger_returns_prefect_logger_by_default(name):
    if name == "default":
        logger = get_logger()
    else:
        logger = get_logger(name)

    assert logger.name == "prefect"


def test_get_logger_returns_prefect_child_logger():
    logger = get_logger("foo")
    assert logger.name == "prefect.foo"


def test_get_logger_does_not_duplicate_prefect_prefix():
    logger = get_logger("prefect.foo")
    assert logger.name == "prefect.foo"


def test_default_level_is_applied_to_interpolated_yaml_values(dictConfigMock):
    fake_settings = Settings(logging=LoggingSettings(default_level="WARNING"))

    expected_config = load_logging_config(
        DEFAULT_LOGGING_SETTINGS_PATH, fake_settings.logging
    )

    assert expected_config["handlers"]["console"]["level"] == "WARNING"
    assert expected_config["handlers"]["orion"]["level"] == "WARNING"

    setup_logging(fake_settings)
    dictConfigMock.assert_called_once_with(expected_config)


def test_flow_run_logger(flow_run):
    logger = flow_run_logger(flow_run)
    assert logger.name == "prefect.flow_runs"
    assert logger.extra == {
        "flow_run_name": flow_run.name,
        "flow_run_id": str(flow_run.id),
        "flow_name": "<unknown>",
    }


def test_flow_run_logger_with_flow(flow_run):
    @flow(name="foo")
    def test_flow():
        pass

    logger = flow_run_logger(flow_run, test_flow)
    assert logger.extra["flow_name"] == "foo"


def test_flow_run_logger_with_kwargs(flow_run):
    logger = flow_run_logger(flow_run, foo="test", flow_run_name="bar")
    assert logger.extra["foo"] == "test"
    assert logger.extra["flow_run_name"] == "bar"


def test_task_run_logger(task_run):
    logger = task_run_logger(task_run)
    assert logger.name == "prefect.task_runs"
    assert logger.extra == {
        "task_run_name": task_run.name,
        "task_run_id": str(task_run.id),
        "flow_run_id": str(task_run.flow_run_id),
        "flow_run_name": "<unknown>",
        "flow_name": "<unknown>",
        "task_name": "<unknown>",
    }


def test_task_run_logger_with_task(task_run):
    @task(name="foo")
    def test_task():
        pass

    logger = task_run_logger(task_run, test_task)
    assert logger.extra["task_name"] == "foo"


def test_task_run_logger_with_flow_run(task_run, flow_run):
    logger = task_run_logger(task_run, flow_run=flow_run)
    assert logger.extra["flow_run_id"] == str(task_run.flow_run_id)
    assert logger.extra["flow_run_name"] == flow_run.name


def test_task_run_logger_with_flow(task_run):
    @flow(name="foo")
    def test_flow():
        pass

    logger = task_run_logger(task_run, flow=test_flow)
    assert logger.extra["flow_name"] == "foo"


def test_task_run_logger_with_kwargs(task_run):
    logger = task_run_logger(task_run, foo="test", task_run_name="bar")
    assert logger.extra["foo"] == "test"
    assert logger.extra["task_run_name"] == "bar"


def test_run_logger_fails_outside_context():
    with pytest.raises(RuntimeError, match="no active flow or task run context"):
        run_logger()


async def test_run_logger_with_explicit_context(orion_client, flow_run):
    @task
    def foo():
        pass

    task_run = await orion_client.create_task_run(foo, flow_run.id, dynamic_key="")
    context = TaskRunContext(task=foo, task_run=task_run, client=orion_client)

    logger = run_logger(context)

    assert logger.name == "prefect.task_runs"
    assert logger.extra == {
        "task_name": foo.name,
        "task_run_id": str(task_run.id),
        "task_run_name": task_run.name,
        "flow_run_id": str(flow_run.id),
        "flow_name": "<unknown>",
        "flow_run_name": "<unknown>",
    }


async def test_run_logger_with_explicit_context_overrides_existing(
    orion_client, flow_run
):
    @task
    def foo():
        pass

    @task
    def bar():
        pass

    task_run = await orion_client.create_task_run(foo, flow_run.id, dynamic_key="")
    # Use `bar` instead of `foo` in context
    context = TaskRunContext(task=bar, task_run=task_run, client=orion_client)

    logger = run_logger(context)
    assert logger.extra["task_name"] == bar.name


async def test_run_logger_in_flow(orion_client):
    @flow
    def test_flow():
        return run_logger()

    state = test_flow()
    flow_run = await orion_client.read_flow_run(state.state_details.flow_run_id)
    logger = state.result()
    assert logger.name == "prefect.flow_runs"
    assert logger.extra == {
        "flow_name": test_flow.name,
        "flow_run_id": str(flow_run.id),
        "flow_run_name": flow_run.name,
    }


async def test_run_logger_extra_data(orion_client):
    @flow
    def test_flow():
        return run_logger(foo="test", flow_name="bar")

    state = test_flow()
    flow_run = await orion_client.read_flow_run(state.state_details.flow_run_id)
    logger = state.result()
    assert logger.name == "prefect.flow_runs"
    assert logger.extra == {
        "flow_name": "bar",
        "foo": "test",
        "flow_run_id": str(flow_run.id),
        "flow_run_name": flow_run.name,
    }


async def test_run_logger_in_nested_flow(orion_client):
    @flow
    def child_flow():
        return run_logger()

    @flow
    def test_flow():
        return child_flow()

    child_state = test_flow().result()
    flow_run = await orion_client.read_flow_run(child_state.state_details.flow_run_id)
    logger = child_state.result()
    assert logger.name == "prefect.flow_runs"
    assert logger.extra == {
        "flow_name": child_flow.name,
        "flow_run_id": str(flow_run.id),
        "flow_run_name": flow_run.name,
    }


async def test_run_logger_in_task(orion_client):
    @task
    def test_task():
        return run_logger()

    @flow
    def test_flow():
        return test_task().wait()

    flow_state = test_flow()
    flow_run = await orion_client.read_flow_run(flow_state.state_details.flow_run_id)
    task_state = flow_state.result()
    task_run = await orion_client.read_task_run(task_state.state_details.task_run_id)
    logger = task_state.result()
    assert logger.name == "prefect.task_runs"
    assert logger.extra == {
        "task_name": test_task.name,
        "task_run_id": str(task_run.id),
        "task_run_name": task_run.name,
        "flow_name": test_flow.name,
        "flow_run_id": str(flow_run.id),
        "flow_run_name": flow_run.name,
    }

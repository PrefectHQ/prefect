from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextlib import nullcontext
from datetime import datetime
from functools import partial
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Generator
from unittest import mock
from unittest.mock import ANY, MagicMock, patch

import pytest
from rich.color import Color, ColorType
from rich.console import Console
from rich.highlighter import NullHighlighter, ReprHighlighter
from rich.style import Style

import prefect
import prefect.logging.configuration
import prefect.settings
from prefect import flow, task
from prefect._internal.concurrency.api import create_call, from_sync
from prefect.client.orchestration import PrefectClient
from prefect.context import FlowRunContext, TaskRunContext
from prefect.exceptions import MissingContextError
from prefect.logging import LogEavesdropper
from prefect.logging.configuration import (
    DEFAULT_LOGGING_SETTINGS_PATH,
    load_logging_config,
    setup_logging,
)
from prefect.logging.filters import ObfuscateApiKeyFilter
from prefect.logging.formatters import JsonFormatter
from prefect.logging.handlers import (
    APILogHandler,
    APILogWorker,
    PrefectConsoleHandler,
    WorkerAPILogHandler,
)
from prefect.logging.highlighters import PrefectConsoleHighlighter
from prefect.logging.loggers import (
    PrefectLogAdapter,
    disable_logger,
    disable_run_logger,
    flow_run_logger,
    get_logger,
    get_run_logger,
    get_worker_logger,
    patch_print,
    task_run_logger,
)
from prefect.server.schemas.actions import LogCreate
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_LOGGING_COLORS,
    PREFECT_LOGGING_EXTRA_LOGGERS,
    PREFECT_LOGGING_LEVEL,
    PREFECT_LOGGING_MARKUP,
    PREFECT_LOGGING_SETTINGS_PATH,
    PREFECT_LOGGING_TO_API_BATCH_INTERVAL,
    PREFECT_LOGGING_TO_API_BATCH_SIZE,
    PREFECT_LOGGING_TO_API_ENABLED,
    PREFECT_LOGGING_TO_API_MAX_LOG_SIZE,
    PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW,
    PREFECT_SERVER_LOGGING_LEVEL,
    PREFECT_TEST_MODE,
    temporary_settings,
)
from prefect.testing.cli import temporary_console_width
from prefect.testing.utilities import AsyncMock
from prefect.types._datetime import from_timestamp, now
from prefect.utilities.names import obfuscate
from prefect.workers.base import BaseJobConfiguration, BaseWorker

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun, TaskRun
    from prefect.server.events.pipeline import EventsPipeline


def _normalize_timestamp(timestamp: str) -> str:
    if timestamp.endswith("Z"):
        if "." in timestamp:
            base, frac = timestamp[:-1].split(".")
            # Normalize fractional seconds to 6 digits
            frac = (frac + "000000")[:6]
            timestamp = f"{base}.{frac}+00:00"
        else:
            timestamp = timestamp[:-1] + "+00:00"
    return timestamp


@pytest.fixture
def dictConfigMock(monkeypatch: pytest.MonkeyPatch):
    mock = MagicMock()
    monkeypatch.setattr("logging.config.dictConfig", mock)
    # Reset the process global since we're testing `setup_logging`
    old = prefect.logging.configuration.PROCESS_LOGGING_CONFIG
    prefect.logging.configuration.PROCESS_LOGGING_CONFIG = {}
    yield mock
    prefect.logging.configuration.PROCESS_LOGGING_CONFIG = old


@pytest.fixture
async def logger_test_deployment(prefect_client: PrefectClient):
    """
    A deployment with a flow that returns information about the given loggers
    """

    @prefect.flow
    def my_flow() -> dict[str, Any]:
        import logging

        settings: dict[str, Any] = {}

        for logger_name in ["foo", "bar", "prefect"]:
            logger = logging.getLogger(logger_name)
            settings[logger_name] = {
                "handlers": [handler.name for handler in logger.handlers],
                "level": logger.level,
            }
            logger.info(f"Hello from {logger_name}")

        return settings

    flow_id = await prefect_client.create_flow(my_flow)

    deployment_id = await prefect_client.create_deployment(
        flow_id=flow_id,
        name="logger_test_deployment",
    )

    return deployment_id


def test_setup_logging_uses_default_path(tmp_path: Path, dictConfigMock: MagicMock):
    with temporary_settings(
        {PREFECT_LOGGING_SETTINGS_PATH: tmp_path.joinpath("does-not-exist.yaml")}
    ):
        expected_config = load_logging_config(DEFAULT_LOGGING_SETTINGS_PATH)
        expected_config["incremental"] = False
        setup_logging()

    dictConfigMock.assert_called_once_with(expected_config)


def test_setup_logging_sets_incremental_on_repeated_calls(dictConfigMock: MagicMock):
    setup_logging()
    assert dictConfigMock.call_count == 1
    setup_logging()
    assert dictConfigMock.call_count == 2
    assert dictConfigMock.mock_calls[0][1][0]["incremental"] is False
    assert dictConfigMock.mock_calls[1][1][0]["incremental"] is True


def test_setup_logging_uses_settings_path_if_exists(
    tmp_path: Path, dictConfigMock: MagicMock
):
    config_file = tmp_path.joinpath("exists.yaml")
    config_file.write_text("foo: bar")

    with temporary_settings({PREFECT_LOGGING_SETTINGS_PATH: config_file}):
        setup_logging()
        expected_config = load_logging_config(tmp_path.joinpath("exists.yaml"))
        expected_config["incremental"] = False

    dictConfigMock.assert_called_once_with(expected_config)


def test_setup_logging_uses_env_var_overrides(
    tmp_path: Path, dictConfigMock: MagicMock, monkeypatch: pytest.MonkeyPatch
):
    with temporary_settings(
        {PREFECT_LOGGING_SETTINGS_PATH: tmp_path.joinpath("does-not-exist.yaml")}
    ):
        expected_config = load_logging_config(DEFAULT_LOGGING_SETTINGS_PATH)
    env: dict[str, Any] = {}

    expected_config["incremental"] = False

    # Test setting a value for a simple key
    env["PREFECT_LOGGING_HANDLERS_API_LEVEL"] = "API_LEVEL_VAL"
    expected_config["handlers"]["api"]["level"] = "API_LEVEL_VAL"

    # Test setting a value for the root logger
    env["PREFECT_LOGGING_ROOT_LEVEL"] = "ROOT_LEVEL_VAL"
    expected_config["root"]["level"] = "ROOT_LEVEL_VAL"

    # Test setting a single list value
    env["PREFECT_LOGGING_ROOT_HANDLERS"] = "ROOT_HANDLERS_SINGLE_VAL"
    expected_config["root"]["handlers"] = ["ROOT_HANDLERS_SINGLE_VAL"]

    # Test setting a multi list value
    env["PREFECT_LOGGING_ROOT_HANDLERS"] = (
        "ROOT_HANDLERS_FIRST_VAL,ROOT_HANDLERS_SECOND_VAL"
    )
    expected_config["root"]["handlers"] = [
        "ROOT_HANDLERS_FIRST_VAL",
        "ROOT_HANDLERS_SECOND_VAL",
    ]

    # Test setting a value where the a key contains underscores
    env["PREFECT_LOGGING_FORMATTERS_STANDARD_FLOW_RUN_FMT"] = "UNDERSCORE_KEY_VAL"
    expected_config["formatters"]["standard"]["flow_run_fmt"] = "UNDERSCORE_KEY_VAL"

    # Test setting a value where the key contains a period
    env["PREFECT_LOGGING_LOGGERS_PREFECT_EXTRA_LEVEL"] = "VAL"

    expected_config["loggers"]["prefect.extra"]["level"] = "VAL"

    # Test setting a value that does not exist in the yaml config and should not be
    # set in the expected_config since there is no value to override
    env["PREFECT_LOGGING_FOO"] = "IGNORED"

    for var, value in env.items():
        monkeypatch.setenv(var, value)

    with temporary_settings(
        {PREFECT_LOGGING_SETTINGS_PATH: tmp_path.joinpath("does-not-exist.yaml")}
    ):
        setup_logging()

    dictConfigMock.assert_called_once_with(expected_config)


def test_setup_logging_preserves_existing_root_logger_configuration(
    dictConfigMock: MagicMock,
):
    """
    Test that setup_logging does not override the root logger configuration
    if the user has already configured it.

    This addresses issue #18872 where importing Prefect would overwrite
    user-defined logging formats and handlers.
    """
    import logging

    # Simulate user configuring the root logger before importing Prefect
    root_logger = logging.getLogger()
    handler = MagicMock()
    root_logger.handlers = [handler]

    # Run setup_logging (normally happens on import)
    setup_logging()

    # The config passed to dictConfig should not have a 'root' key
    # since we detected existing root logger configuration
    called_config = dictConfigMock.call_args[0][0]
    assert "root" not in called_config

    # Clean up
    root_logger.handlers = []


def test_setup_logging_applies_root_config_when_no_prior_configuration(
    dictConfigMock: MagicMock,
):
    """
    Test that setup_logging applies the root logger configuration
    when the user hasn't configured logging beforehand.
    """
    import logging

    # Ensure root logger has no handlers (fresh state)
    root_logger = logging.getLogger()
    root_logger.handlers = []

    # Run setup_logging
    setup_logging()

    # The config should include root logger configuration
    called_config = dictConfigMock.call_args[0][0]
    assert "root" in called_config
    assert called_config["root"]["level"] == "WARNING"
    assert called_config["root"]["handlers"] == ["console"]


def test_setting_aliases_respected_for_logging_config(tmp_path: Path):
    logging_config_content = """
loggers:
  prefect:
    level: "${PREFECT_LOGGING_SERVER_LEVEL}"
"""
    config_file = tmp_path / "logging.yaml"
    config_file.write_text(logging_config_content)

    with temporary_settings(
        {
            PREFECT_LOGGING_SETTINGS_PATH: config_file,
            PREFECT_SERVER_LOGGING_LEVEL: "INFO",
        }
    ):
        config = setup_logging()
        assert config["loggers"]["prefect"]["level"] == "INFO"


@pytest.mark.parametrize("name", ["default", None, ""])
def test_get_logger_returns_prefect_logger_by_default(name: str | None):
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


def test_default_level_is_applied_to_interpolated_yaml_values(
    dictConfigMock: MagicMock,
):
    with temporary_settings(
        {PREFECT_LOGGING_LEVEL: "WARNING", PREFECT_TEST_MODE: False}
    ):
        expected_config = load_logging_config(DEFAULT_LOGGING_SETTINGS_PATH)
        expected_config["incremental"] = False

        assert expected_config["loggers"]["prefect"]["level"] == "WARNING"
        assert expected_config["loggers"]["prefect.extra"]["level"] == "WARNING"

        setup_logging()

    dictConfigMock.assert_called_once_with(expected_config)


@pytest.fixture()
def external_logger_setup(request: pytest.FixtureRequest):
    # This fixture will create a logger with the specified name, level, and propagate value
    name, level = request.param
    logger = logging.getLogger(name)
    old_level, old_propagate = logger.level, logger.propagate
    assert logger.level == logging.NOTSET, "Logger should start with NOTSET level"
    assert logger.handlers == [], "Logger should start with no handlers"
    logger.setLevel(level)
    yield name, level, old_propagate
    # Reset the logger to its original state
    logger.setLevel(old_level)
    logger.propagate = old_propagate
    logger.handlers = []


@pytest.mark.parametrize(
    "external_logger_setup",
    [
        ("foo", logging.DEBUG),
        ("foo.child", logging.DEBUG),
        ("foo", logging.INFO),
        ("foo.child", logging.INFO),
        ("foo", logging.WARNING),
        ("foo.child", logging.WARNING),
        ("foo", logging.ERROR),
        ("foo.child", logging.ERROR),
        ("foo", logging.CRITICAL),
        ("foo.child", logging.CRITICAL),
    ],
    indirect=True,
    ids=lambda x: f"logger='{x[0]}'-level='{logging._levelToName[x[1]]}'",  # type: ignore[reportPrivateUsage]
)
def test_setup_logging_extra_loggers_does_not_modify_external_logger_level(
    dictConfigMock: MagicMock, external_logger_setup: tuple[str, int, bool]
):
    ext_name, ext_level, ext_propagate = external_logger_setup
    with temporary_settings(
        {
            PREFECT_LOGGING_LEVEL: "WARNING",
            PREFECT_TEST_MODE: False,
            PREFECT_LOGGING_EXTRA_LOGGERS: ext_name,
        }
    ):
        expected_config = load_logging_config(DEFAULT_LOGGING_SETTINGS_PATH)
        expected_config["incremental"] = False
        setup_logging()

    dictConfigMock.assert_called_once_with(expected_config)
    external_logger = logging.getLogger(ext_name)
    assert external_logger.level == ext_level, "External logger level was not preserved"
    if ext_level > logging.NOTSET:
        assert external_logger.isEnabledFor(ext_level), (
            "External effective level was not preserved"
        )
    assert external_logger.propagate == ext_propagate, (
        "External logger propagate was not preserved"
    )


@pytest.fixture
def mock_log_worker(monkeypatch: pytest.MonkeyPatch):
    mock = MagicMock()
    monkeypatch.setattr("prefect.logging.handlers.APILogWorker", mock)
    return mock


@pytest.mark.enable_api_log_handler
class TestAPILogHandler:
    @pytest.fixture
    def handler(self) -> Generator[APILogHandler, None, None]:
        yield APILogHandler()

    @pytest.fixture
    def logger(self, handler: APILogHandler):
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        yield logger
        logger.removeHandler(handler)

    def test_worker_is_not_flushed_on_handler_close(self, mock_log_worker: MagicMock):
        handler = APILogHandler()
        handler.close()
        mock_log_worker.drain_all.assert_not_called()

    async def test_logs_can_still_be_sent_after_close(
        self,
        logger: logging.Logger,
        handler: APILogHandler,
        flow_run: "FlowRun",
        prefect_client: PrefectClient,
    ):
        logger.info("Test", extra={"flow_run_id": flow_run.id})
        handler.close()  # Close it
        logger.info("Test", extra={"flow_run_id": flow_run.id})
        await handler.aflush()

        logs = await prefect_client.read_logs()
        assert len(logs) == 2

    async def test_logs_can_still_be_sent_after_flush(
        self,
        logger: logging.Logger,
        handler: APILogHandler,
        flow_run: "FlowRun",
        prefect_client: PrefectClient,
    ):
        logger.info("Test", extra={"flow_run_id": flow_run.id})
        await handler.aflush()
        logger.info("Test", extra={"flow_run_id": flow_run.id})
        await handler.aflush()

        logs = await prefect_client.read_logs()
        assert len(logs) == 2

    async def test_sync_flush_from_async_context(
        self,
        logger: logging.Logger,
        handler: APILogHandler,
        flow_run: "FlowRun",
        prefect_client: PrefectClient,
    ):
        logger.info("Test", extra={"flow_run_id": flow_run.id})
        handler.flush()

        # Yield to the worker thread
        time.sleep(2)

        logs = await prefect_client.read_logs()
        assert len(logs) == 1

    def test_sync_flush_from_global_event_loop(
        self, logger: logging.Logger, handler: APILogHandler, flow_run: "FlowRun"
    ):
        logger.info("Test", extra={"flow_run_id": flow_run.id})
        with pytest.raises(RuntimeError, match="would block"):
            from_sync.call_soon_in_loop_thread(create_call(handler.flush)).result()

    def test_sync_flush_from_sync_context(
        self, logger: logging.Logger, handler: APILogHandler, flow_run: "FlowRun"
    ):
        logger.info("Test", extra={"flow_run_id": flow_run.id})
        handler.flush()

    def test_sends_task_run_log_to_worker(
        self, logger: logging.Logger, mock_log_worker: MagicMock, task_run: "TaskRun"
    ):
        with TaskRunContext.model_construct(task_run=task_run):
            logger.info("test-task")

        expected = LogCreate.model_construct(
            flow_run_id=task_run.flow_run_id,
            task_run_id=task_run.id,
            name=logger.name,
            level=logging.INFO,
            message="test-task",
        ).model_dump(mode="json")
        expected["timestamp"] = ANY  # Tested separately
        expected["__payload_size__"] = ANY  # Tested separately

        mock_log_worker.instance().send.assert_called_once_with(expected)

    def test_sends_flow_run_log_to_worker(
        self, logger: logging.Logger, mock_log_worker: MagicMock, flow_run: "FlowRun"
    ):
        with FlowRunContext.model_construct(flow_run=flow_run):
            logger.info("test-flow")

        expected = LogCreate.model_construct(
            flow_run_id=flow_run.id,
            task_run_id=None,
            name=logger.name,
            level=logging.INFO,
            message="test-flow",
        ).model_dump(mode="json")
        expected["timestamp"] = ANY  # Tested separately
        expected["__payload_size__"] = ANY  # Tested separately

        mock_log_worker.instance().send.assert_called_once_with(expected)

    @pytest.mark.parametrize("with_context", [True, False])
    def test_respects_explicit_flow_run_id(
        self,
        logger: logging.Logger,
        mock_log_worker: MagicMock,
        flow_run: "FlowRun",
        with_context: bool,
    ):
        flow_run_id = uuid.uuid4()
        context = (
            FlowRunContext.model_construct(flow_run=flow_run)
            if with_context
            else nullcontext()
        )
        with context:
            logger.info("test-task", extra={"flow_run_id": flow_run_id})

        expected = LogCreate.model_construct(
            flow_run_id=flow_run_id,
            task_run_id=None,
            name=logger.name,
            level=logging.INFO,
            message="test-task",
        ).model_dump(mode="json")
        expected["timestamp"] = ANY  # Tested separately
        expected["__payload_size__"] = ANY  # Tested separately

        mock_log_worker.instance().send.assert_called_once_with(expected)

    @pytest.mark.parametrize("with_context", [True, False])
    def test_respects_explicit_task_run_id(
        self,
        logger: logging.Logger,
        mock_log_worker: MagicMock,
        flow_run: "FlowRun",
        with_context: bool,
        task_run: "TaskRun",
    ):
        task_run_id = uuid.uuid4()
        context = (
            TaskRunContext.model_construct(task_run=task_run)
            if with_context
            else nullcontext()
        )
        with FlowRunContext.model_construct(flow_run=flow_run):
            with context:
                logger.warning("test-task", extra={"task_run_id": task_run_id})

        expected = LogCreate.model_construct(
            flow_run_id=flow_run.id,
            task_run_id=task_run_id,
            name=logger.name,
            level=logging.WARNING,
            message="test-task",
        ).model_dump(mode="json")
        expected["timestamp"] = ANY  # Tested separately
        expected["__payload_size__"] = ANY  # Tested separately

        mock_log_worker.instance().send.assert_called_once_with(expected)

    def test_does_not_emit_logs_below_level(
        self, logger: logging.Logger, mock_log_worker: MagicMock
    ):
        logger.setLevel(logging.WARNING)
        logger.info("test-task", extra={"flow_run_id": uuid.uuid4()})
        mock_log_worker.instance().send.assert_not_called()

    def test_explicit_task_run_id_still_requires_flow_run_id(
        self, logger: logging.Logger, mock_log_worker: MagicMock
    ):
        task_run_id = uuid.uuid4()
        with pytest.warns(
            UserWarning, match="attempted to send logs .* without a flow run id"
        ):
            logger.info("test-task", extra={"task_run_id": task_run_id})

        mock_log_worker.instance().send.assert_not_called()

    def test_sets_timestamp_from_record_created_time(
        self,
        logger: logging.Logger,
        mock_log_worker: MagicMock,
        flow_run: "FlowRun",
        handler: APILogHandler,
    ):
        # Capture the record
        handler.emit = MagicMock(side_effect=handler.emit)

        with FlowRunContext.model_construct(flow_run=flow_run):
            logger.info("test-flow")

        record = handler.emit.call_args[0][0]
        log_dict = mock_log_worker.instance().send.call_args[0][0]
        timestamp = log_dict["timestamp"]

        if sys.version_info < (3, 11):
            timestamp = _normalize_timestamp(timestamp)

        assert datetime.fromisoformat(timestamp) == from_timestamp(record.created)

    def test_sets_timestamp_from_time_if_missing_from_recrod(
        self,
        logger: logging.Logger,
        mock_log_worker: MagicMock,
        flow_run: "FlowRun",
        handler: APILogHandler,
        monkeypatch: pytest.MonkeyPatch,
    ):
        def drop_created_and_emit(
            emit: Callable[[logging.LogRecord], None], record: logging.LogRecord
        ):
            record.created = None  # type: ignore
            return emit(record)

        handler.emit = MagicMock(
            side_effect=partial(drop_created_and_emit, handler.emit)
        )

        now = time.time()
        monkeypatch.setattr("time.time", lambda: now)

        with FlowRunContext.model_construct(flow_run=flow_run):
            logger.info("test-flow")

        log_dict = mock_log_worker.instance().send.call_args[0][0]

        timestamp = log_dict["timestamp"]

        if sys.version_info < (3, 11):
            timestamp = _normalize_timestamp(timestamp)

        assert datetime.fromisoformat(timestamp) == from_timestamp(now)

    def test_does_not_send_logs_that_opt_out(
        self,
        logger: logging.Logger,
        mock_log_worker: MagicMock,
        task_run: "TaskRun",
    ):
        with TaskRunContext.model_construct(task_run=task_run):
            logger.info("test", extra={"send_to_api": False})

        mock_log_worker.instance().send.assert_not_called()

    def test_does_not_send_logs_when_handler_is_disabled(
        self,
        logger: logging.Logger,
        mock_log_worker: MagicMock,
        task_run: "TaskRun",
    ):
        with temporary_settings(
            updates={PREFECT_LOGGING_TO_API_ENABLED: "False"},
        ):
            with TaskRunContext.model_construct(task_run=task_run):
                logger.info("test")

        mock_log_worker.instance().send.assert_not_called()

    def test_does_not_send_logs_outside_of_run_context_with_default_setting(
        self,
        logger: logging.Logger,
        mock_log_worker: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ):
        # Warns in the main process
        with pytest.warns(
            UserWarning, match="attempted to send logs .* without a flow run id"
        ):
            logger.info("test")

        mock_log_worker.instance().send.assert_not_called()

        # No stderr output
        output = capsys.readouterr()
        assert output.err == ""

    def test_does_not_raise_when_logger_outside_of_run_context_with_default_setting(
        self,
        logger: logging.Logger,
        capsys: pytest.CaptureFixture[str],
    ):
        with pytest.warns(
            UserWarning,
            match=(
                "Logger 'tests.test_logging' attempted to send logs to the API without"
                " a flow run id."
            ),
        ):
            logger.info("test")

    def test_does_not_send_logs_outside_of_run_context_with_error_setting(
        self,
        logger: logging.Logger,
        mock_log_worker: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ):
        with temporary_settings(
            updates={PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW: "error"},
        ):
            with pytest.raises(
                MissingContextError,
                match="attempted to send logs .* without a flow run id",
            ):
                logger.info("test")

        mock_log_worker.instance().send.assert_not_called()

        # No stderr output
        output = capsys.readouterr()
        assert output.err == ""

    def test_does_not_warn_when_logger_outside_of_run_context_with_error_setting(
        self,
        logger: logging.Logger,
    ):
        with temporary_settings(
            updates={PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW: "error"},
        ):
            with pytest.raises(
                MissingContextError,
                match=(
                    "Logger 'tests.test_logging' attempted to send logs to the API"
                    " without a flow run id."
                ),
            ):
                logger.info("test")

    def test_does_not_send_logs_outside_of_run_context_with_ignore_setting(
        self,
        logger: logging.Logger,
        mock_log_worker: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ):
        with temporary_settings(
            updates={PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW: "ignore"},
        ):
            logger.info("test")

        mock_log_worker.instance().send.assert_not_called()

        # No stderr output
        output = capsys.readouterr()
        assert output.err == ""

    def test_does_not_raise_or_warn_when_logger_outside_of_run_context_with_ignore_setting(
        self,
        logger: logging.Logger,
    ):
        with temporary_settings(
            updates={PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW: "ignore"},
        ):
            logger.info("test")

    def test_does_not_send_logs_outside_of_run_context_with_warn_setting(
        self,
        logger: logging.Logger,
        mock_log_worker: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ):
        with temporary_settings(
            updates={PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW: "warn"},
        ):
            # Warns in the main process
            with pytest.warns(
                UserWarning, match="attempted to send logs .* without a flow run id"
            ):
                logger.info("test")

        mock_log_worker.instance().send.assert_not_called()

        # No stderr output
        output = capsys.readouterr()
        assert output.err == ""

    def test_does_not_raise_when_logger_outside_of_run_context_with_warn_setting(
        self,
        logger: logging.Logger,
    ):
        with temporary_settings(
            updates={PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW: "warn"},
        ):
            with pytest.warns(
                UserWarning,
                match=(
                    "Logger 'tests.test_logging' attempted to send logs to the API"
                    " without a flow run id."
                ),
            ):
                logger.info("test")

    def test_missing_context_warning_refers_to_caller_lineno(
        self,
        logger: logging.Logger,
        mock_log_worker: MagicMock,
    ):
        from inspect import currentframe, getframeinfo

        # Warns in the main process
        with pytest.warns(
            UserWarning, match="attempted to send logs .* without a flow run id"
        ) as warnings:
            logger.info("test")
            lineno = getframeinfo(currentframe()).lineno - 1  # type: ignore
            # The above dynamic collects the line number so that added tests do not
            # break this test

        mock_log_worker.instance().send.assert_not_called()
        assert warnings.pop().lineno == lineno

    def test_writes_logging_errors_to_stderr(
        self,
        logger: logging.Logger,
        mock_log_worker: MagicMock,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr(
            "prefect.logging.handlers.APILogHandler.prepare",
            MagicMock(side_effect=RuntimeError("Oh no!")),
        )
        # No error raised
        logger.info("test")

        mock_log_worker.instance().send.assert_not_called()

        # Error is in stderr
        output = capsys.readouterr()
        assert "RuntimeError: Oh no!" in output.err

    def test_does_not_write_error_for_logs_outside_run_context_that_opt_out(
        self,
        logger: logging.Logger,
        mock_log_worker: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ):
        logger.info("test", extra={"send_to_api": False})

        mock_log_worker.instance().send.assert_not_called()
        output = capsys.readouterr()
        assert (
            "RuntimeError: Attempted to send logs to the API without a flow run id."
            not in output.err
        )

    async def test_does_not_enqueue_logs_that_are_too_big(
        self,
        task_run: "TaskRun",
        logger: logging.Logger,
        capsys: pytest.CaptureFixture[str],
        mock_log_worker: MagicMock,
    ):
        with TaskRunContext.model_construct(task_run=task_run):
            with temporary_settings(updates={PREFECT_LOGGING_TO_API_MAX_LOG_SIZE: "1"}):
                logger.info("test")

        mock_log_worker.instance().send.assert_called_once()
        sent_log = mock_log_worker.instance().send.call_args[0][0]
        output = capsys.readouterr()
        assert sent_log["message"].endswith("... [truncated]")
        assert sent_log["__payload_truncated__"] is True
        assert "ValueError" not in output.err

    def test_handler_knows_how_large_logs_are(self):
        dict_log = {
            "name": "prefect.flow_runs",
            "level": 20,
            "message": "Finished in state Completed()",
            "timestamp": "2023-02-08T17:55:52.993831+00:00",
            "flow_run_id": "47014fb1-9202-4a78-8739-c993d8c24415",
            "task_run_id": None,
        }

        log_size = len(json.dumps(dict_log))
        assert log_size == 211
        handler = APILogHandler()
        assert handler._get_payload_size(dict_log) == log_size  # type: ignore[reportPrivateUsage]


WORKER_ID = uuid.uuid4()


class TestWorkerLogging:
    class CloudWorkerTestImpl(BaseWorker[Any, Any, Any]):
        type: str = "cloud_logging_test"
        job_configuration = BaseJobConfiguration

        async def _send_worker_heartbeat(self, *_, **__):
            """
            Workers only return an ID here if they're connected to Cloud,
            so this simulates the worker being connected to Cloud.
            """
            return WORKER_ID

        async def run(self, *_, **__):
            pass

    class ServerWorkerTestImpl(BaseWorker[Any, Any, Any]):
        type: str = "server_logging_test"
        job_configuration = BaseJobConfiguration

        async def run(self, *_, **__):
            pass

        async def _send_worker_heartbeat(self, *_, **__):
            """
            Workers only return an ID here if they're connected to Cloud,
            so this simulates the worker not being connected to Cloud.
            """
            return None

    @pytest.fixture
    def logging_to_api_enabled(self):
        with temporary_settings(updates={PREFECT_LOGGING_TO_API_ENABLED: True}):
            yield

    @pytest.fixture
    def worker_handler(self):
        yield WorkerAPILogHandler()

    @pytest.fixture
    def logger(self, worker_handler: WorkerAPILogHandler):
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(worker_handler)
        yield logger
        logger.removeHandler(worker_handler)

    async def test_get_worker_logger_works_with_no_backend_id(self):
        async with self.CloudWorkerTestImpl(
            name="test", work_pool_name="test-work-pool"
        ) as worker:
            logger = get_worker_logger(worker)
            assert logger.name == "prefect.workers.cloud_logging_test.test"

    async def test_get_worker_logger_works_with_backend_id(self):
        async with self.CloudWorkerTestImpl(
            name="test", work_pool_name="test-work-pool"
        ) as worker:
            await worker.sync_with_backend()
            logger = get_worker_logger(worker)
            assert logger.name == "prefect.workers.cloud_logging_test.test"
            assert logger.extra["worker_id"] == str(WORKER_ID)

    async def test_worker_emits_logs_with_worker_id(
        self, caplog: pytest.LogCaptureFixture
    ):
        async with self.CloudWorkerTestImpl(
            name="test", work_pool_name="test-work-pool"
        ) as worker:
            await worker.sync_with_backend()
            worker._logger.info("testing_with_extras")

            record_with_extras = [
                r for r in caplog.records if "testing_with_extras" in r.message
            ]

            assert "testing_with_extras" in caplog.text
            assert record_with_extras[0].worker_id == str(worker.backend_id)
            assert worker._logger.extra["worker_id"] == str(worker.backend_id)

    @pytest.mark.usefixtures("worker_handler", "logging_to_api_enabled")
    async def test_worker_logger_sends_log_to_api_worker_when_connected_to_cloud(
        self, mock_log_worker: MagicMock
    ):
        async with self.CloudWorkerTestImpl(
            name="test", work_pool_name="test-work-pool"
        ) as worker:
            await worker.sync_with_backend()
            worker._logger.debug("test-worker-log")

        log_statement = [
            log
            for call in mock_log_worker.instance().send.call_args_list
            for log in call.args
            if log["name"] == worker._logger.name
            and log["message"] == "test-worker-log"
        ]

        assert len(log_statement) == 1
        assert log_statement[0]["worker_id"] == str(worker.backend_id)

    @pytest.mark.usefixtures("worker_handler", "logging_to_api_enabled")
    async def test_worker_logger_does_not_send_logs_when_not_connected_to_cloud(
        self, mock_log_worker: MagicMock
    ):
        async with self.ServerWorkerTestImpl(
            name="test", work_pool_name="test-work-pool"
        ) as worker:
            assert isinstance(worker._logger, logging.Logger)
            worker._logger.debug("test-worker-log")

        mock_log_worker.instance().send.assert_not_called()


class TestAPILogWorker:
    @pytest.fixture
    async def worker(self):
        return APILogWorker.instance()

    @pytest.fixture
    def log_dict(self):
        return LogCreate(
            flow_run_id=uuid.uuid4(),
            task_run_id=uuid.uuid4(),
            name="test.logger",
            level=10,
            timestamp=now("UTC"),
            message="hello",
        ).model_dump(mode="json")

    async def test_send_logs_single_record(
        self,
        log_dict: dict[str, Any],
        prefect_client: PrefectClient,
        worker: APILogWorker,
    ):
        worker.send(log_dict)
        await worker.drain()
        logs = await prefect_client.read_logs()
        assert len(logs) == 1
        assert logs[0].model_dump(include=log_dict.keys(), mode="json") == log_dict

    async def test_send_logs_many_records(
        self,
        log_dict: dict[str, Any],
        prefect_client: PrefectClient,
        worker: APILogWorker,
    ):
        # Use the read limit as the count since we'd need multiple read calls otherwise
        count = prefect.settings.PREFECT_API_DEFAULT_LIMIT.value()
        log_dict.pop("message")

        for i in range(count):
            new_log = log_dict.copy()
            new_log["message"] = str(i)
            worker.send(new_log)
        await worker.drain()

        logs = await prefect_client.read_logs()
        assert len(logs) == count
        for log in logs:
            assert (
                log.model_dump(
                    include=log_dict.keys(), exclude={"message"}, mode="json"
                )
                == log_dict
            )
        assert len(set(log.message for log in logs)) == count, "Each log is unique"

    async def test_send_logs_writes_exceptions_to_stderr(
        self,
        log_dict: dict[str, Any],
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
        worker: APILogWorker,
    ):
        monkeypatch.setattr(
            "prefect.client.orchestration.PrefectClient.create_logs",
            MagicMock(side_effect=ValueError("Test")),
        )

        worker.send(log_dict)
        await worker.drain()

        err = capsys.readouterr().err
        assert "--- Error logging to API ---" in err
        assert "ValueError: Test" in err

    async def test_send_logs_batches_by_size(
        self, log_dict: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ):
        mock_create_logs = AsyncMock()
        monkeypatch.setattr(
            "prefect.client.orchestration.PrefectClient.create_logs", mock_create_logs
        )

        log_size = APILogHandler()._get_payload_size(log_dict)

        with temporary_settings(
            updates={
                PREFECT_LOGGING_TO_API_BATCH_SIZE: log_size + 1,
                PREFECT_LOGGING_TO_API_MAX_LOG_SIZE: log_size,
            }
        ):
            worker = APILogWorker.instance()
            worker.send(log_dict)
            worker.send(log_dict)
            worker.send(log_dict)
            await worker.drain()

        assert mock_create_logs.call_count == 3

    async def test_logs_are_sent_immediately_when_stopped(
        self, log_dict: dict[str, Any], prefect_client: PrefectClient
    ):
        # Set a long interval
        start_time = time.time()
        with temporary_settings(updates={PREFECT_LOGGING_TO_API_BATCH_INTERVAL: "10"}):
            worker = APILogWorker.instance()
            worker.send(log_dict)
            worker.send(log_dict)
            await worker.drain()
        end_time = time.time()

        assert (
            end_time - start_time
        ) < 5  # An arbitrary time less than the 10s interval

        logs = await prefect_client.read_logs()
        assert len(logs) == 2

    async def test_logs_are_sent_immediately_when_flushed(
        self,
        log_dict: dict[str, Any],
        prefect_client: PrefectClient,
        worker: APILogWorker,
    ):
        # Set a long interval
        start_time = time.time()
        with temporary_settings(updates={PREFECT_LOGGING_TO_API_BATCH_INTERVAL: "10"}):
            worker.send(log_dict)
            worker.send(log_dict)
            await worker.drain()
        end_time = time.time()

        assert (
            end_time - start_time
        ) < 5  # An arbitrary time less than the 10s interval

        logs = await prefect_client.read_logs()
        assert len(logs) == 2

    async def test_logs_include_worker_id_if_available(
        self, worker: APILogWorker, log_dict: dict[str, Any]
    ):
        worker_id = str(uuid.uuid4())
        log_dict["worker_id"] = worker_id

        with mock.patch(
            "prefect.client.orchestration.PrefectClient.create_logs", autospec=True
        ) as mock_create_logs:
            worker.send(log_dict)
            await worker.drain()
            assert mock_create_logs.call_count == 1
            logs = mock_create_logs.call_args.args[1]
            assert len(logs) == 1
            assert logs[0]["worker_id"] == worker_id


def test_flow_run_logger(flow_run: "FlowRun"):
    logger = flow_run_logger(flow_run)
    assert logger.name == "prefect.flow_runs"
    assert logger.extra == {
        "flow_run_name": flow_run.name,
        "flow_run_id": str(flow_run.id),
        "flow_name": "<unknown>",
    }


def test_flow_run_logger_with_flow(flow_run: "FlowRun"):
    @flow(name="foo")
    def test_flow():
        pass

    logger = flow_run_logger(flow_run, test_flow)
    assert logger.extra["flow_name"] == "foo"


def test_flow_run_logger_with_kwargs(flow_run: "FlowRun"):
    logger = flow_run_logger(flow_run, foo="test", flow_run_name="bar")
    assert logger.extra["foo"] == "test"
    assert logger.extra["flow_run_name"] == "bar"


def test_task_run_logger(task_run: "TaskRun"):
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


def test_task_run_logger_with_task(task_run: "TaskRun"):
    @task(name="task_run_logger_with_task")
    def test_task():
        pass

    logger = task_run_logger(task_run, test_task)
    assert logger.extra["task_name"] == "task_run_logger_with_task"


def test_task_run_logger_with_flow_run(task_run: "TaskRun", flow_run: "FlowRun"):
    logger = task_run_logger(task_run, flow_run=flow_run)
    assert logger.extra["flow_run_id"] == str(task_run.flow_run_id)
    assert logger.extra["flow_run_name"] == flow_run.name


def test_task_run_logger_with_flow(task_run: "TaskRun"):
    @flow(name="foo")
    def test_flow():
        pass

    logger = task_run_logger(task_run, flow=test_flow)
    assert logger.extra["flow_name"] == "foo"


def test_task_run_logger_with_flow_run_from_context(
    task_run: "TaskRun", flow_run: "FlowRun"
):
    @flow(name="foo")
    def test_flow():
        pass

    with FlowRunContext.model_construct(flow_run=flow_run, flow=test_flow):
        logger = task_run_logger(task_run)
        assert (
            logger.extra["flow_run_id"] == str(task_run.flow_run_id) == str(flow_run.id)
        )
        assert logger.extra["flow_run_name"] == flow_run.name
        assert logger.extra["flow_name"] == test_flow.name == "foo"


def test_run_logger_with_flow_run_context_without_parent_flow_run_id(
    caplog: pytest.LogCaptureFixture,
):
    """Test that get_run_logger works when called from a constructed FlowRunContext"""

    with FlowRunContext.model_construct(flow_run=None, flow=None):
        logger = get_run_logger()

        with caplog.at_level(logging.INFO):
            logger.info("test3141592")

        assert "prefect.flow_runs" in caplog.text
        assert "test3141592" in caplog.text

        assert logger.extra["flow_run_id"] == "<unknown>"
        assert logger.extra["flow_run_name"] == "<unknown>"
        assert logger.extra["flow_name"] == "<unknown>"


async def test_run_logger_with_task_run_context_without_parent_flow_run_id(
    prefect_client: PrefectClient, caplog: pytest.LogCaptureFixture
):
    """Test that get_run_logger works when passed a constructed TaskRunContext"""

    @task
    def foo():
        pass

    task_run = await prefect_client.create_task_run(
        foo, flow_run_id=None, dynamic_key=""
    )

    task_run_context = TaskRunContext.model_construct(
        task=foo, task_run=task_run, client=prefect_client
    )

    logger = get_run_logger(task_run_context)

    with caplog.at_level(logging.INFO):
        logger.info("test3141592")

    assert "prefect.task_runs" in caplog.text
    assert "test3141592" in caplog.text


def test_task_run_logger_with_kwargs(task_run: "TaskRun"):
    logger = task_run_logger(task_run, foo="test", task_run_name="bar")
    assert logger.extra["foo"] == "test"
    assert logger.extra["task_run_name"] == "bar"


def test_run_logger_fails_outside_context():
    with pytest.raises(MissingContextError, match="no active flow or task run context"):
        get_run_logger()


async def test_run_logger_with_explicit_context_of_invalid_type():
    with pytest.raises(TypeError, match="Received unexpected type 'str' for context."):
        get_run_logger("my man!")


async def test_run_logger_with_explicit_context(
    prefect_client: PrefectClient,
    flow_run: "FlowRun",
):
    @task
    def foo():
        pass

    task_run = await prefect_client.create_task_run(foo, flow_run.id, dynamic_key="")
    context = TaskRunContext.model_construct(
        task=foo,
        task_run=task_run,
        client=prefect_client,
    )

    logger = get_run_logger(context)

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
    prefect_client: PrefectClient,
    flow_run: "FlowRun",
):
    @task
    def foo():
        pass

    @task
    def bar():
        pass

    task_run = await prefect_client.create_task_run(foo, flow_run.id, dynamic_key="")
    # Use `bar` instead of `foo` in context
    context = TaskRunContext.model_construct(
        task=bar,
        task_run=task_run,
        client=prefect_client,
    )

    logger = get_run_logger(context)
    assert logger.extra["task_name"] == bar.name


async def test_run_logger_in_flow(prefect_client: PrefectClient):
    @flow
    def test_flow():
        return get_run_logger()

    state = test_flow(return_state=True)
    flow_run = await prefect_client.read_flow_run(state.state_details.flow_run_id)
    logger = await state.result()
    assert logger.name == "prefect.flow_runs"
    assert logger.extra == {
        "flow_name": test_flow.name,
        "flow_run_id": str(flow_run.id),
        "flow_run_name": flow_run.name,
    }


async def test_run_logger_extra_data(prefect_client: PrefectClient):
    @flow
    def test_flow():
        return get_run_logger(foo="test", flow_name="bar")

    state = test_flow(return_state=True)
    flow_run = await prefect_client.read_flow_run(state.state_details.flow_run_id)
    logger = await state.result()
    assert logger.name == "prefect.flow_runs"
    assert logger.extra == {
        "flow_name": "bar",
        "foo": "test",
        "flow_run_id": str(flow_run.id),
        "flow_run_name": flow_run.name,
    }


async def test_run_logger_in_nested_flow(prefect_client: PrefectClient):
    @flow
    def child_flow():
        return get_run_logger()

    @flow
    def test_flow():
        return child_flow(return_state=True)

    child_state = await test_flow(return_state=True).result()
    flow_run = await prefect_client.read_flow_run(child_state.state_details.flow_run_id)
    logger = await child_state.result()
    assert logger.name == "prefect.flow_runs"
    assert logger.extra == {
        "flow_name": child_flow.name,
        "flow_run_id": str(flow_run.id),
        "flow_run_name": flow_run.name,
    }


async def test_run_logger_in_task(
    prefect_client: PrefectClient, events_pipeline: "EventsPipeline"
):
    @task
    def test_task():
        return get_run_logger()

    @flow
    def test_flow():
        return test_task(return_state=True)

    flow_state = test_flow(return_state=True)
    flow_run = await prefect_client.read_flow_run(flow_state.state_details.flow_run_id)
    task_state = await flow_state.result()

    await events_pipeline.process_events()

    task_run = await prefect_client.read_task_run(task_state.state_details.task_run_id)
    logger = await task_state.result()
    assert logger.name == "prefect.task_runs"
    assert logger.extra == {
        "task_name": test_task.name,
        "task_run_id": str(task_run.id),
        "task_run_name": task_run.name,
        "flow_name": test_flow.name,
        "flow_run_id": str(flow_run.id),
        "flow_run_name": flow_run.name,
    }


class TestPrefectConsoleHandler:
    @pytest.fixture
    def handler(self):
        yield PrefectConsoleHandler()

    @pytest.fixture
    def logger(self, handler: PrefectConsoleHandler):
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        yield logger
        logger.removeHandler(handler)

    def test_init_defaults(self):
        handler = PrefectConsoleHandler()
        console = handler.console
        assert isinstance(console, Console)
        assert isinstance(console.highlighter, PrefectConsoleHighlighter)
        assert console._theme_stack._entries == [{}]  # inherit=False
        assert handler.level == logging.NOTSET

    def test_init_styled_console_disabled(self):
        with temporary_settings({PREFECT_LOGGING_COLORS: False}):
            handler = PrefectConsoleHandler()
            console = handler.console
            assert isinstance(console, Console)
            assert isinstance(console.highlighter, NullHighlighter)
            assert console._theme_stack._entries == [{}]
            assert handler.level == logging.NOTSET

    def test_init_override_kwargs(self):
        handler = PrefectConsoleHandler(
            highlighter=ReprHighlighter, styles={"number": "red"}, level=logging.DEBUG
        )
        console = handler.console
        assert isinstance(console, Console)
        assert isinstance(console.highlighter, ReprHighlighter)
        assert console._theme_stack._entries == [
            {"number": Style(color=Color("red", ColorType.STANDARD, number=1))}
        ]
        assert handler.level == logging.DEBUG

    def test_uses_stderr_by_default(self, capsys: pytest.CaptureFixture[str]):
        logger = get_logger(uuid.uuid4().hex)
        logger.handlers = [PrefectConsoleHandler()]
        logger.info("Test!")
        stdout, stderr = capsys.readouterr()
        assert stdout == ""
        assert "Test!" in stderr

    def test_respects_given_stream(self, capsys: pytest.CaptureFixture[str]):
        logger = get_logger(uuid.uuid4().hex)
        logger.handlers = [PrefectConsoleHandler(stream=sys.stdout)]
        logger.info("Test!")
        stdout, stderr = capsys.readouterr()
        assert stderr == ""
        assert "Test!" in stdout

    def test_includes_tracebacks_during_exceptions(
        self, capsys: pytest.CaptureFixture[str]
    ):
        logger = get_logger(uuid.uuid4().hex)
        logger.handlers = [PrefectConsoleHandler()]

        try:
            raise ValueError("oh my")
        except Exception:
            logger.exception("Helpful context!")

        _, stderr = capsys.readouterr()
        assert "Helpful context!" in stderr
        assert "Traceback" in stderr
        assert 'raise ValueError("oh my")' in stderr
        assert "ValueError: oh my" in stderr

    def test_does_not_word_wrap_or_crop_messages(
        self, capsys: pytest.CaptureFixture[str]
    ):
        logger = get_logger(uuid.uuid4().hex)
        handler = PrefectConsoleHandler()
        logger.handlers = [handler]

        # Pretend we have a narrow little console
        with temporary_console_width(handler.console, 10):
            logger.info("x" * 1000)

        _, stderr = capsys.readouterr()
        # There will be newlines in the middle if cropped
        assert "x" * 1000 in stderr

    def test_outputs_square_brackets_as_text(self, capsys: pytest.CaptureFixture[str]):
        logger = get_logger(uuid.uuid4().hex)
        handler = PrefectConsoleHandler()
        logger.handlers = [handler]

        msg = "DROP TABLE [dbo].[SomeTable];"
        logger.info(msg)

        _, stderr = capsys.readouterr()
        assert msg in stderr

    def test_outputs_square_brackets_as_style(self, capsys: pytest.CaptureFixture[str]):
        with temporary_settings({PREFECT_LOGGING_MARKUP: True}):
            logger = get_logger(uuid.uuid4().hex)
            handler = PrefectConsoleHandler()
            logger.handlers = [handler]

            msg = "this applies [red]style[/red]!;"
            logger.info(msg)

            _, stderr = capsys.readouterr()
            assert "this applies style" in stderr


class TestJsonFormatter:
    def test_json_log_formatter(self):
        formatter = JsonFormatter("default", None, "%")
        record = logging.LogRecord(
            name="Test Log",
            level=1,
            pathname="/path/file.py",
            lineno=1,
            msg="log message",
            args=None,
            exc_info=None,
        )

        formatted = formatter.format(record)

        # we should be able to load the formatted JSON successfully
        deserialized = json.loads(formatted)

        # we can't check for an exact JSON string because some attributes vary at
        # runtime, so check some known attributes instead
        assert deserialized["name"] == "Test Log"
        assert deserialized["levelname"] == "Level 1"
        assert deserialized["filename"] == "file.py"
        assert deserialized["lineno"] == 1

    def test_json_log_formatter_with_exception(self):
        exc_info = None
        try:
            raise Exception("test exception")  # noqa
        except Exception as exc:  # noqa
            exc_info = sys.exc_info()

        formatter = JsonFormatter("default", None, "%")
        record = logging.LogRecord(
            name="Test Log",
            level=1,
            pathname="/path/file.py",
            lineno=1,
            msg="log message",
            args=None,
            exc_info=exc_info,
        )

        formatted = formatter.format(record)

        # we should be able to load the formatted JSON successfully
        deserialized = json.loads(formatted)

        # we can't check for an exact JSON string because some attributes vary at
        # runtime, so check some known attributes instead
        assert deserialized["name"] == "Test Log"
        assert deserialized["levelname"] == "Level 1"
        assert deserialized["filename"] == "file.py"
        assert deserialized["lineno"] == 1
        assert deserialized["exc_info"] is not None
        assert deserialized["exc_info"]["type"] == "Exception"
        assert deserialized["exc_info"]["message"] == "test exception"
        assert deserialized["exc_info"]["traceback"] is not None
        assert len(deserialized["exc_info"]["traceback"]) > 0


class TestObfuscateApiKeyFilter:
    def test_filters_current_api_key(self):
        test_api_key = "hi-hello-im-an-api-key"
        with temporary_settings({PREFECT_API_KEY: test_api_key}):
            filter = ObfuscateApiKeyFilter()
            record = logging.LogRecord(
                name="Test Log",
                level=1,
                pathname="/path/file.py",
                lineno=1,
                msg=test_api_key,
                args=None,
                exc_info=None,
            )

            filter.filter(record)

        assert test_api_key not in record.getMessage()
        assert obfuscate(test_api_key) in record.getMessage()

    def test_current_api_key_is_not_logged(self, caplog):
        test_api_key = "hot-dog-theres-a-logger-this-is-my-big-chance-for-stardom"
        with temporary_settings({PREFECT_API_KEY: test_api_key}):
            logger = get_logger("test")
            logger.info(test_api_key)

        assert test_api_key not in caplog.text
        assert obfuscate(test_api_key) in caplog.text

    def test_current_api_key_is_not_logged_from_flow(
        self, caplog: pytest.LogCaptureFixture
    ):
        test_api_key = "i-am-a-plaintext-api-key-and-i-dream-of-being-logged-one-day"
        with temporary_settings({PREFECT_API_KEY: test_api_key}):

            @flow
            def test_flow():
                logger = get_run_logger()
                logger.info(test_api_key)

            test_flow()

        assert test_api_key not in caplog.text
        assert obfuscate(test_api_key) in caplog.text

    def test_current_api_key_is_not_logged_from_flow_log_prints(
        self, caplog: pytest.LogCaptureFixture
    ):
        test_api_key = "i-am-a-sneaky-little-api-key"
        with temporary_settings({PREFECT_API_KEY: test_api_key}):

            @flow(log_prints=True)
            def test_flow():
                print(test_api_key)

            test_flow()

        assert test_api_key not in caplog.text
        assert obfuscate(test_api_key) in caplog.text

    def test_current_api_key_is_not_logged_from_task(
        self, caplog: pytest.LogCaptureFixture
    ):
        test_api_key = "i-am-jacks-security-risk"
        with temporary_settings({PREFECT_API_KEY: test_api_key}):

            @task
            def test_task():
                logger = get_run_logger()
                logger.info(test_api_key)

            @flow
            def test_flow():
                test_task()

            test_flow()

        assert test_api_key not in caplog.text
        assert obfuscate(test_api_key) in caplog.text

    @pytest.mark.parametrize(
        "raw_log_record,expected_log_record",
        [
            (
                ["super-mega-admin-key", "in", "a", "list"],
                ["********", "in", "a", "list"],
            ),
            (
                {"super-mega-admin-key": "in", "a": "dict"},
                {"********": "in", "a": "dict"},
            ),
            (
                {
                    "key1": "some_value",
                    "key2": [
                        {"nested_key": "api_key: super-mega-admin-key"},
                        "another_value",
                    ],
                },
                {
                    "key1": "some_value",
                    "key2": [
                        {"nested_key": "api_key: ********"},
                        "another_value",
                    ],
                },
            ),
        ],
    )
    def test_redact_substr_from_collections(
        self,
        caplog: pytest.LogCaptureFixture,
        raw_log_record: Any,
        expected_log_record: Any,
    ):
        """
        This is a regression test for https://github.com/PrefectHQ/prefect/issues/12139
        """

        @flow()
        def test_log_list():
            logger = get_run_logger()
            logger.info(raw_log_record)

        with temporary_settings({PREFECT_API_KEY: "super-mega-admin-key"}):
            test_log_list()

        assert str(expected_log_record) in caplog.text


def test_log_in_flow(caplog: pytest.LogCaptureFixture):
    msg = "Hello world!"

    @flow
    def test_flow():
        logger = get_run_logger()
        logger.warning(msg)

    test_flow()

    for record in caplog.records:
        if record.msg == msg:
            assert record.levelno == logging.WARNING
            break
    else:
        raise AssertionError(f"{msg} was not found in records: {caplog.records}")


def test_log_in_task(caplog: pytest.LogCaptureFixture):
    msg = "Hello world!"

    @task
    def test_task():
        logger = get_run_logger()
        logger.warning(msg)

    @flow
    def test_flow():
        test_task()

    test_flow()
    for record in caplog.records:
        if record.msg == msg:
            assert record.levelno == logging.WARNING
            break
    else:
        raise AssertionError(f"{msg} was not found in records")


def test_without_disable_logger(caplog: pytest.LogCaptureFixture):
    """
    Sanity test to double check whether caplog actually works
    so can be more confident in the asserts in test_disable_logger.
    """
    logger = logging.getLogger("griffe.agents.nodes")

    def function_with_logging(logger: logging.Logger):
        assert not logger.disabled
        logger.critical("it's enabled!")
        return 42

    function_with_logging(logger)
    assert not logger.disabled
    assert ("griffe.agents.nodes", 50, "it's enabled!") in caplog.record_tuples


def test_disable_logger(caplog: pytest.LogCaptureFixture):
    logger = logging.getLogger("griffe.agents.nodes")

    def function_with_logging(logger):
        logger.critical("I know this is critical, but it's disabled!")
        return 42

    with disable_logger(logger.name):
        assert logger.disabled
        function_with_logging(logger)

    assert not logger.disabled
    assert caplog.record_tuples == []


def test_disable_run_logger_with_task(caplog: pytest.LogCaptureFixture):
    @task
    def task_with_run_logger():
        logger = get_run_logger()
        logger.critical("won't show")

    flow_run_logger = get_logger("prefect.flow_runs")
    task_run_logger = get_logger("prefect.task_runs")

    # Can call the task as normal and the underlying function without issue inside the context manager
    with disable_run_logger():
        task_with_run_logger()
        task_with_run_logger.fn()
        assert flow_run_logger.disabled
        assert task_run_logger.disabled

    # Loggers should return to normal state and the disabled logs should not be in the caplog
    assert not flow_run_logger.disabled
    assert not task_run_logger.disabled
    assert "won't show" not in caplog.text

    caplog.clear()

    # Should operate normally outside of the context manager
    task_with_run_logger()
    assert "won't show" in caplog.text

    with pytest.raises(MissingContextError):
        task_with_run_logger.fn()


def test_disable_run_logger_with_flow(caplog: pytest.LogCaptureFixture):
    @flow
    def test_flow():
        logger = get_run_logger()
        logger.critical("won't show")

    flow_run_logger = get_logger("prefect.flow_runs")
    task_run_logger = get_logger("prefect.task_runs")

    # Can call the flow as normal and the underlying function without issue inside the context manager
    with disable_run_logger():
        test_flow()
        test_flow.fn()
        assert flow_run_logger.disabled
        assert task_run_logger.disabled

    # Loggers should return to normal state and the disabled logs should not be in the caplog
    assert not flow_run_logger.disabled
    assert not task_run_logger.disabled
    assert "won't show" not in caplog.text

    caplog.clear()

    # Should operate normally outside of the context manager
    test_flow()
    assert "won't show" in caplog.text

    with pytest.raises(MissingContextError):
        test_flow.fn()


def test_patch_print_writes_to_stdout_without_run_context(
    caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
):
    with patch_print():
        print("foo")

    assert "foo" in capsys.readouterr().out
    assert "foo" not in caplog.text


@pytest.mark.parametrize("run_context_cls", [TaskRunContext, FlowRunContext])
def test_patch_print_writes_to_stdout_with_run_context_and_no_log_prints(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
    run_context_cls: type,
):
    with patch_print():
        with run_context_cls.model_construct(log_prints=False):
            print("foo")

    assert "foo" in capsys.readouterr().out
    assert "foo" not in caplog.text


def test_patch_print_does_not_write_to_logger_with_custom_file(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
    task_run: "TaskRun",
):
    string_io = StringIO()

    @task
    def my_task():
        pass

    with patch_print():
        with TaskRunContext.model_construct(
            log_prints=True, task_run=task_run, task=my_task
        ):
            print("foo", file=string_io)

    assert "foo" not in caplog.text
    assert "foo" not in capsys.readouterr().out
    assert string_io.getvalue().rstrip() == "foo"


def test_patch_print_writes_to_logger_with_task_run_context(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
    task_run: "TaskRun",
):
    @task
    def my_task():
        pass

    with patch_print():
        with TaskRunContext.model_construct(
            log_prints=True, task_run=task_run, task=my_task
        ):
            print("foo")

    assert "foo" not in capsys.readouterr().out
    assert "foo" in caplog.text

    for record in caplog.records:
        if record.message == "foo":
            break

    assert record.levelname == "INFO"
    assert record.name == "prefect.task_runs"
    assert record.task_run_id == str(task_run.id)
    assert record.task_name == my_task.name


@pytest.mark.parametrize("file", ["stdout", "stderr"])
def test_patch_print_writes_to_logger_with_explicit_file(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
    task_run: "TaskRun",
    file: str,
):
    @task
    def my_task():
        pass

    with patch_print():
        with TaskRunContext.model_construct(
            log_prints=True, task_run=task_run, task=my_task
        ):
            # We must defer retrieval of sys.<file> because pytest overrides sys!
            print("foo", file=getattr(sys, file))

    out, err = capsys.readouterr()
    assert "foo" not in out
    assert "foo" not in err
    assert "foo" in caplog.text

    for record in caplog.records:
        if record.message == "foo":
            break

    assert record.levelname == "INFO"
    assert record.name == "prefect.task_runs"
    assert record.task_run_id == str(task_run.id)
    assert record.task_name == my_task.name


def test_patch_print_writes_to_logger_with_flow_run_context(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
    flow_run: "FlowRun",
):
    @flow
    def my_flow():
        pass

    with patch_print():
        with FlowRunContext.model_construct(
            log_prints=True, flow_run=flow_run, flow=my_flow
        ):
            print("foo")

    assert "foo" not in capsys.readouterr().out
    assert "foo" in caplog.text

    for record in caplog.records:
        if record.message == "foo":
            break

    assert record.levelname == "INFO"
    assert record.name == "prefect.flow_runs"
    assert record.flow_run_id == str(flow_run.id)
    assert record.flow_name == my_flow.name


def test_log_adapter_get_child():
    logger = PrefectLogAdapter(get_logger("prefect.parent"), {"hello": "world"})
    assert logger.extra == {"hello": "world"}

    child_logger = logger.getChild("child", {"goodnight": "moon"})
    assert child_logger.logger.name == "prefect.parent.child"
    assert child_logger.extra == {"hello": "world", "goodnight": "moon"}


def test_eavesdropping():
    logging.getLogger("my_logger").debug("This is before the context")

    with LogEavesdropper("my_logger", level=logging.INFO) as eavesdropper:
        logging.getLogger("my_logger").info("Hello, world!")
        logging.getLogger("my_logger.child_module").warning("Another one!")
        logging.getLogger("my_logger").debug("Not this one!")

    logging.getLogger("my_logger").debug("This is after the context")

    assert eavesdropper.text() == "[INFO]: Hello, world!\n[WARNING]: Another one!"


def test_prepare_truncates_oversized_log():
    max_log_size = 500

    handler = APILogHandler()

    very_long_msg = "X" * (max_log_size * 2)
    record = logging.LogRecord(
        name="test.logger.flow",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg=very_long_msg,
        args=(),
        exc_info=None,
    )
    record.flow_run_id = str(uuid.uuid4())

    with patch(
        "prefect.settings.PREFECT_LOGGING_TO_API_MAX_LOG_SIZE.value",
        return_value=max_log_size,
    ):
        log = handler.prepare(record)

    # Check truncation suffix is present
    assert "... [truncated]" in log["message"]

    # Check size does not exceed max_log_size
    assert log["__payload_size__"] <= max_log_size

    # flow_run_id should match
    assert log["flow_run_id"] == record.flow_run_id

    # Message should not be empty (except the truncation text)
    assert log["message"].strip() != ""

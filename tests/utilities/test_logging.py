import contextlib
import datetime
import logging
import time
from unittest.mock import MagicMock

import click
import pytest

import prefect
from prefect import context, utilities
from prefect.utilities.logging import (
    CloudHandler,
    LogManager,
    temporary_logger_config,
    get_logger,
)


@pytest.fixture
def log_manager(monkeypatch):
    log_manager = LogManager()
    Client = MagicMock()
    monkeypatch.setattr(log_manager, "enqueue", MagicMock(wraps=log_manager.enqueue))
    monkeypatch.setattr(prefect, "Client", Client)
    monkeypatch.setattr(utilities.logging, "LOG_MANAGER", log_manager)
    try:
        yield log_manager
    finally:
        log_manager.stop()


@pytest.fixture
def logger(log_manager):
    # Clean logger for every test run
    with utilities.configuration.set_temporary_config(
        {
            "logging.level": "INFO",
            "cloud.logging_heartbeat": 0.25,
            "cloud.send_flow_run_logs": True,
        }
    ):
        logger = utilities.logging.configure_logging(testing=True)
        # Enable logs to the backend by pretending this is during a run
        with prefect.context(running_with_backend=True):
            yield logger
        logger.handlers.clear()


def test_root_logger_level_responds_to_config():
    with utilities.configuration.set_temporary_config({"logging.level": "DEBUG"}):
        assert utilities.logging.configure_logging(testing=True).level == logging.DEBUG

    with utilities.configuration.set_temporary_config({"logging.level": "WARNING"}):
        assert (
            utilities.logging.configure_logging(testing=True).level == logging.WARNING
        )


@pytest.mark.parametrize("datefmt", ["%Y", "%Y -- %D"])
def test_root_logger_datefmt_responds_to_config(caplog, datefmt):
    with utilities.configuration.set_temporary_config({"logging.datefmt": datefmt}):
        logger = utilities.logging.configure_logging(testing=True)
        logger.error("badness")
        logs = [r for r in caplog.records if r.levelname == "ERROR"]
        assert logs[0].asctime == datetime.datetime.now().strftime(datefmt)


def test_root_logger_has_cloud_handler(logger):
    assert logger.handlers
    assert any(isinstance(h, CloudHandler) for h in logger.handlers)


def test_diagnostic_logger_has_no_cloud_handler():
    logger = utilities.logging.create_diagnostic_logger(name="diagnostic-test")
    assert logger.handlers
    assert not any(isinstance(h, CloudHandler) for h in logger.handlers)


def test_cloud_handler_emit_noop_if_cloud_logging_disabled(logger, log_manager):
    with utilities.configuration.set_temporary_config(
        {"cloud.send_flow_run_logs": False}
    ):
        logger.info("testing")
    assert not log_manager.enqueue.called
    assert log_manager.client is None
    assert log_manager.thread is None


def test_cloud_handler_emit_noop_if_cloud_logging_disabled_deprecated(
    logger, log_manager
):
    with utilities.configuration.set_temporary_config({"logging.log_to_cloud": False}):
        logger.info("testing")
    assert not log_manager.enqueue.called
    assert log_manager.client is None
    assert log_manager.thread is None


def test_cloud_handler_emit_noop_if_below_log_level(logger, log_manager):
    logger.debug("testing")
    assert not log_manager.enqueue.called
    assert log_manager.client is None
    assert log_manager.thread is None


def test_cloud_handler_emit_noop_if_below_log_level_in_context(logger, log_manager):
    # Log level in context is higher than log level of logger
    assert logger.level == logging.INFO
    with utilities.configuration.set_temporary_config({"logging.level": "WARNING"}):
        logger.info("testing")
    assert not log_manager.enqueue.called
    assert log_manager.client is None
    assert log_manager.thread is None


def test_cloud_handler_emit_warns_and_truncates_long_messages(
    monkeypatch, logger, log_manager, caplog
):
    # Smaller value for testing
    monkeypatch.setattr(prefect.utilities.logging, "MAX_LOG_LENGTH", 100)

    logger.info("h" * 120)
    # warning about truncating long messages
    assert any(
        r.getMessage().startswith("Received a log message of 120 bytes")
        for r in caplog.records
    )
    assert log_manager.enqueue.call_count == 2
    assert log_manager.enqueue.call_args_list[0][0][0]["message"].startswith(
        "Received a log message of 120 bytes"
    )
    # Truncated log message
    assert log_manager.enqueue.call_args_list[1][0][0]["message"] == "h" * 100


@pytest.mark.parametrize(
    "flow_run_id, task_run_id",
    [("flow-run-id", "task-run-id"), ("flow-run-id", None), (None, None)],
)
def test_cloud_handler_emit_json_spec(logger, log_manager, flow_run_id, task_run_id):
    with prefect.context(flow_run_id=flow_run_id, task_run_id=task_run_id):
        logger.info("testing %d %s", 1, "hello")

    log = log_manager.enqueue.call_args[0][0]

    # Timestamp set on log
    timestamp = log.pop("timestamp")
    assert isinstance(timestamp, str)

    # Remaining fields are deterministic
    assert log == {
        "message": "testing 1 hello",
        "flow_run_id": flow_run_id,
        "task_run_id": task_run_id,
        "name": logger.name,
        "level": "INFO",
    }


@pytest.mark.parametrize(
    "flow_run_id, task_run_id",
    [("flow-run-id", "task-run-id"), ("flow-run-id", None), (None, None)],
)
def test_cloud_handler_emit_json_spec_exception(
    logger, log_manager, flow_run_id, task_run_id
):
    with prefect.context(flow_run_id=flow_run_id, task_run_id=task_run_id):
        try:
            1 / 0
        except Exception:
            logger.exception("An error occurred:")

    log = log_manager.enqueue.call_args[0][0]

    # Timestamp set on log
    timestamp = log.pop("timestamp")
    assert isinstance(timestamp, str)

    message = log.pop("message")
    assert "An error occurred:" in message
    assert "1 / 0" in message
    assert "ZeroDivisionError" in message

    # Remaining fields are deterministic
    assert log == {
        "flow_run_id": flow_run_id,
        "task_run_id": task_run_id,
        "name": logger.name,
        "level": "ERROR",
    }


def test_log_manager_startup_and_shutdown(logger, log_manager):
    heartbeat = 5
    with utilities.configuration.set_temporary_config(
        {"cloud.logging_heartbeat": heartbeat}
    ):
        # On creation, neither thread or client are initialized
        assert log_manager.client is None
        assert log_manager.thread is None

        # After enqueue, thread and client are started
        logger.info("testing")
        assert log_manager.client is not None
        assert log_manager.thread is not None

        client = log_manager.client

        # Calling `_on_shutdown` (which calls stop) will flush the queue and
        # cleanup resources
        start = time.time()
        log_manager._on_shutdown()
        assert log_manager.queue.empty()
        assert client.write_run_logs.called
        assert log_manager.client is None
        assert log_manager.thread is None
        end = time.time()
        assert end - start < heartbeat

        # Calling `stop` is idempotent
        log_manager.stop()


def test_log_manager_batches_logs(logger, log_manager, monkeypatch):
    monkeypatch.setattr(prefect.utilities.logging, "MAX_BATCH_LOG_LENGTH", 100)
    # Fill up log queue with multiple logs exceeding the total batch length
    for i in range(10):
        logger.info(str(i) * 50)
    time.sleep(0.5)

    assert log_manager.queue.empty()
    messages = [
        l["message"]
        for call in log_manager.client.write_run_logs.call_args_list
        for l in call[0][0]
    ]
    assert messages == [f"{i}" * 50 for i in range(10)]
    assert log_manager.client.write_run_logs.call_count == 5


def test_log_manager_warns_and_retries_on_client_error(
    logger, log_manager, monkeypatch
):
    first_call = True

    def write_run_logs(*args, **kwargs):
        nonlocal first_call
        if first_call:
            first_call = False
            raise ValueError("Oh no!")

    log_manager.ensure_started()
    log_manager.client.write_run_logs = MagicMock(wraps=write_run_logs)

    with pytest.warns(UserWarning, match="Failed to write logs with error:"):
        logger.info("testing")

        time.sleep(0.75)

    assert log_manager.client.write_run_logs.call_count == 2
    for call in log_manager.client.write_run_logs.call_args_list:
        logs = call[0][0]
        assert isinstance(logs, list)
        assert len(logs) == 1
        assert logs[0]["message"] == "testing"


def test_get_logger_returns_root_logger():
    assert utilities.logging.get_logger() is logging.getLogger("prefect")


def test_get_logger_with_name_returns_child_logger():
    child_logger = logging.getLogger("prefect.test")
    prefect_logger = utilities.logging.get_logger("test")

    assert prefect_logger is child_logger
    assert prefect_logger is logging.getLogger("prefect").getChild("test")


def test_context_attributes():
    items = {
        "flow_run_id": "fri",
        "flow_name": "fn",
        "task_run_id": "tri",
        "task_name": "tn",
        "task_slug": "ts",
    }

    class DummyFilter(logging.Filter):
        called = False

        def filter(self, record):
            self.called = True
            for k, v in items.items():
                assert getattr(record, k, None) == v

    test_filter = DummyFilter()
    logger = logging.getLogger("prefect")
    logger.addFilter(test_filter)

    with context(items):
        logger.info("log entry!")

    logger.filters.pop()

    assert test_filter.called


def test_users_can_specify_additional_context_attributes():
    class MyHandler(logging.StreamHandler):
        log_traces = []

        def emit(self, record):
            self.log_traces.append(getattr(record, "trace_id", None))

    handler = MyHandler()

    items = {
        "flow_run_id": "fri",
        "flow_name": "fn",
        "task_run_id": "tri",
        "task_name": "tn",
        "task_slug": "ts",
        "trace_id": "ID",
    }

    with utilities.configuration.set_temporary_config(
        {"logging.log_attributes": ["trace_id"]}
    ):
        logger = logging.getLogger("test-logger")
        logger.addHandler(handler)

        with context(items):
            logger.critical("log entry!")

    assert handler.log_traces[0] == "ID"


def test_users_can_specify_additional_context_attributes_and_fails_gracefully():
    class MyHandler(logging.StreamHandler):
        log_attrs = []

        def emit(self, record):
            data = dict(trace_id=record.trace_id, foo=record.foo)
            self.log_attrs.append(data)

    handler = MyHandler()
    items = {
        "flow_run_id": "fri",
        "flow_name": "fn",
        "task_run_id": "tri",
        "task_name": "tn",
        "task_slug": "ts",
        "trace_id": "ID",
    }

    with utilities.configuration.set_temporary_config(
        {"logging.log_attributes": ["trace_id", "foo"]}
    ):
        logger = logging.getLogger("test-logger")
        logger.addHandler(handler)

        with context(items):
            logger.critical("log entry!")

    assert handler.log_attrs[0]["foo"] is None
    assert handler.log_attrs[0]["trace_id"] == "ID"


def test_context_only_specified_attributes():
    items = {
        "flow_run_id": "fri",
        "flow_name": "fn",
        "task_run_id": "tri",
    }

    class DummyFilter(logging.Filter):
        called = False

        def filter(self, record):
            self.called = True
            for k, v in items.items():
                assert getattr(record, k, None) == v

            not_expected = set(utilities.logging.PREFECT_LOG_RECORD_ATTRIBUTES) - set(
                items.keys()
            )
            for key in not_expected:
                assert key not in record.__dict__.keys()

    test_filter = DummyFilter()
    logger = logging.getLogger("prefect")
    logger.addFilter(test_filter)

    with context(items):
        logger.info("log entry!")

    logger.filters.pop()

    assert test_filter.called

    with utilities.configuration.set_temporary_config(
        {"logging.extra_loggers": ["extra_logger"]}
    ):
        utilities.logging.configure_extra_loggers()
        assert (
            type(logging.root.manager.loggerDict.get("extra_logger")) == logging.Logger
        )


def test_redirect_to_log(caplog):
    log_stdout = utilities.logging.RedirectToLog()

    log_stdout.write("TEST1")
    log_stdout.write("")
    log_stdout.write("TEST2")

    logs = [r.message for r in caplog.records if r.levelname == "INFO"]
    assert logs == ["TEST1", "TEST2"]

    log_stdout.flush()


def test_redirect_to_log_is_textwriter(caplog):
    log_stdout = utilities.logging.RedirectToLog()
    with contextlib.redirect_stdout(log_stdout):
        click.secho("There is color on this line", fg="red")
        click.secho("Standard")
    log_stdout.flush()

    logs = [r.message for r in caplog.records if r.levelname == "INFO"]
    assert logs == ["There is color on this line\n", "Standard\n"]

    log_stdout.flush()


def test_temporary_config_sets_and_resets(caplog):
    with temporary_logger_config(
        level=logging.CRITICAL,
        stream_fmt="%(message)s",
        stream_datefmt="%H:%M:%S",
    ):
        logger = get_logger()
        assert logger.level == logging.CRITICAL
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                assert handler.formatter._fmt == "%(message)s"
                assert handler.formatter.datefmt == "%H:%M:%S"
        logger.info("Info log not shown")
        logger.critical("Critical log shown")

    logger.info("Info log shown")
    for handler in logger.handlers:
        handler.flush()

    output = caplog.text
    assert "Info log not shown" not in output
    assert "Critical log shown" in output
    assert "Info log shown" in output

    assert logger.level == logging.DEBUG
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            assert handler.formatter._fmt != "%(message)s"
            assert handler.formatter.datefmt != "%H:%M:%S"


@pytest.mark.parametrize("level", [logging.CRITICAL, None])
@pytest.mark.parametrize("stream_fmt", ["%(message)s", None])
@pytest.mark.parametrize("stream_datefmt", ["%H:%M:%S", None])
def test_temporary_config_does_not_require_all_args(
    caplog, level, stream_fmt, stream_datefmt
):
    with temporary_logger_config(
        level=level,
        stream_fmt=stream_fmt,
        stream_datefmt=stream_datefmt,
    ):
        pass


def test_temporary_config_resets_on_exception(caplog):
    with pytest.raises(ValueError):
        with temporary_logger_config(
            level=logging.CRITICAL,
        ):
            raise ValueError()

    logger = get_logger()
    assert logger.level == logging.DEBUG

import logging
import queue
import sys
import time
import uuid
from contextlib import nullcontext
from functools import partial
from unittest.mock import ANY, MagicMock

import anyio
import pendulum
import pytest

import prefect
from prefect.context import FlowRunContext, TaskRunContext
from prefect.orion.schemas.actions import LogCreate
from prefect.utilities.logging import (
    DEFAULT_LOGGING_SETTINGS_PATH,
    OrionHandler,
    OrionLogWorker,
    get_logger,
    load_logging_config,
    setup_logging,
)
from prefect.utilities.compat import AsyncMock
from prefect.utilities.settings import LoggingSettings, Settings, temporary_settings


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


def test_default_level_is_applied_to_interpolated_yaml_values(dictConfigMock):
    fake_settings = Settings(logging=LoggingSettings(default_level="WARNING"))

    expected_config = load_logging_config(
        DEFAULT_LOGGING_SETTINGS_PATH, fake_settings.logging
    )

    assert expected_config["handlers"]["console"]["level"] == "WARNING"
    assert expected_config["handlers"]["orion"]["level"] == "WARNING"

    setup_logging(fake_settings)
    dictConfigMock.assert_called_once_with(expected_config)


@pytest.fixture
def mock_log_worker(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("prefect.utilities.logging.OrionLogWorker", mock)
    return mock


class TestOrionHandler:
    @pytest.fixture(autouse=True)
    def reset_log_worker(self):
        """
        Since we have a singleton worker for the runtime of the module, we must reset
        it to `None` between tests
        """
        yield
        OrionHandler.worker = None

    @pytest.fixture
    def handler(self):
        yield OrionHandler()

    @pytest.fixture
    def logger(self, handler):
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        yield logger
        logger.removeHandler(handler)

    def test_handler_instances_share_log_worker(self):
        assert OrionHandler().get_worker() is OrionHandler().get_worker()

    def test_instantiates_log_worker(self, mock_log_worker):
        OrionHandler().get_worker()
        mock_log_worker.assert_called_once_with()
        mock_log_worker().start.assert_called_once_with()

    def test_worker_is_not_started_until_log_is_emitted(self, mock_log_worker, logger):
        mock_log_worker().start.assert_not_called()
        logger.setLevel(logging.INFO)
        logger.debug("test-task", extra={"flow_run_id": uuid.uuid4()})
        mock_log_worker().start.assert_not_called()
        logger.info("test-task", extra={"flow_run_id": uuid.uuid4()})
        mock_log_worker().start.assert_called()

    def test_worker_is_stopped_on_handler_close(self, mock_log_worker):
        handler = OrionHandler()
        handler.get_worker()
        handler.close()
        mock_log_worker().stop.assert_called_once()

    def test_worker_is_not_stopped_if_not_set_on_handler_close(self, mock_log_worker):
        OrionHandler().close()
        mock_log_worker().stop.assert_not_called()

    def test_sends_task_run_log_to_worker(self, logger, mock_log_worker, task_run):
        with TaskRunContext.construct(task_run=task_run):
            logger.info("test-task")

        expected = LogCreate.construct(
            flow_run_id=task_run.flow_run_id,
            task_run_id=task_run.id,
            name=logger.name,
            level=logging.INFO,
            message="test-task",
        ).dict(json_compatible=True)
        expected["timestamp"] = ANY  # Tested separately

        mock_log_worker().enqueue.assert_called_once_with(expected)

    def test_sends_flow_run_log_to_worker(self, logger, mock_log_worker, flow_run):
        with FlowRunContext.construct(flow_run=flow_run):
            logger.info("test-flow")

        expected = LogCreate.construct(
            flow_run_id=flow_run.id,
            task_run_id=None,
            name=logger.name,
            level=logging.INFO,
            message="test-flow",
        ).dict(json_compatible=True)
        expected["timestamp"] = ANY  # Tested separately

        mock_log_worker().enqueue.assert_called_once_with(expected)

    @pytest.mark.parametrize("with_context", [True, False])
    def test_respects_explicit_flow_run_id(
        self, logger, mock_log_worker, flow_run, with_context
    ):
        flow_run_id = uuid.uuid4()
        context = (
            FlowRunContext.construct(flow_run=flow_run)
            if with_context
            else nullcontext()
        )
        with context:
            logger.info("test-task", extra={"flow_run_id": flow_run_id})

        expected = LogCreate.construct(
            flow_run_id=flow_run_id,
            task_run_id=None,
            name=logger.name,
            level=logging.INFO,
            message="test-task",
        ).dict(json_compatible=True)
        expected["timestamp"] = ANY  # Tested separately

        mock_log_worker().enqueue.assert_called_once_with(expected)

    @pytest.mark.parametrize("with_context", [True, False])
    def test_respects_explicit_task_run_id(
        self, logger, mock_log_worker, flow_run, with_context, task_run
    ):
        task_run_id = uuid.uuid4()
        context = (
            TaskRunContext.construct(task_run=task_run)
            if with_context
            else nullcontext()
        )
        with FlowRunContext.construct(flow_run=flow_run):
            with context:
                logger.warning("test-task", extra={"task_run_id": task_run_id})

        expected = LogCreate.construct(
            flow_run_id=flow_run.id,
            task_run_id=task_run_id,
            name=logger.name,
            level=logging.WARNING,
            message="test-task",
        ).dict(json_compatible=True)
        expected["timestamp"] = ANY  # Tested separately

        mock_log_worker().enqueue.assert_called_once_with(expected)

    def test_does_not_emit_logs_below_level(self, logger, mock_log_worker):
        logger.setLevel(logging.WARNING)
        logger.info("test-task", extra={"flow_run_id": uuid.uuid4()})
        mock_log_worker().enqueue.assert_not_called()

    def test_explicit_task_run_id_still_requires_flow_run_id(
        self, logger, mock_log_worker, capsys
    ):
        task_run_id = uuid.uuid4()
        logger.info("test-task", extra={"task_run_id": task_run_id})
        mock_log_worker().enqueue.assert_not_called()
        output = capsys.readouterr()
        assert (
            "RuntimeError: Attempted to send logs to Orion without a flow run id."
            in output.err
        )

    def test_sets_timestamp_from_record_created_time(
        self, logger, mock_log_worker, flow_run, handler
    ):
        # Capture the record
        handler.emit = MagicMock(side_effect=handler.emit)

        with FlowRunContext.construct(flow_run=flow_run):
            logger.info("test-flow")

        record = handler.emit.call_args[0][0]
        log_json = mock_log_worker().enqueue.call_args[0][0]

        assert (
            log_json["timestamp"] == pendulum.from_timestamp(record.created).isoformat()
        )

    def test_sets_timestamp_from_time_if_missing_from_recrod(
        self, logger, mock_log_worker, flow_run, handler, monkeypatch
    ):
        def drop_created_and_emit(emit, record):
            record.created = None
            return emit(record)

        handler.emit = MagicMock(
            side_effect=partial(drop_created_and_emit, handler.emit)
        )

        now = time.time()
        monkeypatch.setattr("time.time", lambda: now)

        with FlowRunContext.construct(flow_run=flow_run):
            logger.info("test-flow")

        log_json = mock_log_worker().enqueue.call_args[0][0]

        assert log_json["timestamp"] == pendulum.from_timestamp(now).isoformat()

    def test_does_not_send_logs_that_opt_out(self, logger, mock_log_worker, task_run):
        with TaskRunContext.construct(task_run=task_run):
            logger.info("test", extra={"send_to_orion": False})

        mock_log_worker().enqueue.assert_not_called()

    def test_does_not_send_logs_outside_of_run_context(
        self, logger, mock_log_worker, capsys
    ):
        # Does not raise error in the main process
        logger.info("test")

        mock_log_worker().enqueue.assert_not_called()

        output = capsys.readouterr()
        assert (
            "RuntimeError: Attempted to send logs to Orion without a flow run id."
            in output.err
        )

    def test_does_not_write_error_for_logs_outside_run_context_that_opt_out(
        self, logger, mock_log_worker, capsys
    ):
        logger.info("test", extra={"send_to_orion": False})

        mock_log_worker().enqueue.assert_not_called()
        output = capsys.readouterr()
        assert (
            "RuntimeError: Attempted to send logs to Orion without a flow run id."
            not in output.err
        )

    async def test_does_not_enqueue_logs_that_are_too_big(
        self, task_run, logger, capsys, mock_log_worker
    ):
        with TaskRunContext.construct(task_run=task_run):
            with temporary_settings(
                PREFECT_LOGGING_ORION_MAX_SINGLE_LOG_SIZE="1",
            ):
                logger.info("test")

        mock_log_worker().enqueue.assert_not_called()
        output = capsys.readouterr()
        assert "ValueError" in output.err
        assert "is greater than the max size of 1" in output.err


class TestOrionLogWorker:
    @pytest.fixture
    def log_json(self):
        return LogCreate(
            flow_run_id=uuid.uuid4(),
            task_run_id=uuid.uuid4(),
            name="test.logger",
            level=10,
            timestamp=pendulum.now("utc"),
            message="hello",
        ).dict(json_compatible=True)

    def test_start_is_idempotent(self):
        worker = OrionLogWorker()
        worker._send_thread = MagicMock()
        worker.start()
        worker.start()
        worker._send_thread.start.assert_called_once()

    def test_stop_is_idempotent(self):
        worker = OrionLogWorker()
        worker._send_thread = MagicMock()
        worker._stop_event = MagicMock()
        worker.stop()
        worker._stop_event.set.assert_not_called()
        worker._send_thread.join.assert_not_called()
        worker.start()
        worker.stop()
        worker.stop()
        worker._stop_event.set.assert_called_once()
        worker._send_thread.join.assert_called_once()

    def test_enqueue(self, log_json):
        worker = OrionLogWorker()
        worker.enqueue(log_json)
        assert worker._queue.get_nowait() == log_json

    async def test_send_logs_single_record(self, log_json, orion_client):
        worker = OrionLogWorker()
        worker.enqueue(log_json)
        await worker.send_logs()
        logs = await orion_client.read_logs()
        assert len(logs) == 1
        assert logs[0].dict(include=log_json.keys(), json_compatible=True) == log_json

    async def test_send_logs_many_records(self, log_json, orion_client):
        # Use the read limit as the count since we'd need multiple read calls otherwise
        count = prefect.settings.orion.api.default_limit
        worker = OrionLogWorker()
        log_json.pop("message")

        for i in range(count):
            new_log = log_json.copy()
            new_log["message"] = str(i)
            worker.enqueue(new_log)
        await worker.send_logs()

        logs = await orion_client.read_logs()
        assert len(logs) == count
        for log in logs:
            assert (
                log.dict(
                    include=log_json.keys(), exclude={"message"}, json_compatible=True
                )
                == log_json
            )
        assert len(set(log.message for log in logs)) == count, "Each log is unique"

    async def test_send_logs_retries_on_next_call_on_exception(
        self, log_json, orion_client, monkeypatch, capsys
    ):
        worker = OrionLogWorker()
        create_logs = orion_client.create_logs
        monkeypatch.setattr(
            "prefect.client.OrionClient.create_logs",
            MagicMock(side_effect=ValueError("Test")),
        )

        worker.enqueue(log_json)
        await worker.send_logs()

        # Log moved from queue to pending logs
        assert worker._pending_logs == [log_json]
        with pytest.raises(queue.Empty):
            worker._queue.get_nowait()

        # Restore client
        monkeypatch.setattr(
            "prefect.client.OrionClient.create_logs",
            create_logs,
        )
        await worker.send_logs()

        logs = await orion_client.read_logs()
        assert len(logs) == 1

    @pytest.mark.parametrize("exiting", [True, False])
    async def test_send_logs_writes_exceptions_to_stderr(
        self, log_json, capsys, monkeypatch, exiting
    ):
        worker = OrionLogWorker()
        monkeypatch.setattr(
            "prefect.client.OrionClient.create_logs",
            MagicMock(side_effect=ValueError("Test")),
        )

        worker.enqueue(log_json)
        await worker.send_logs(exiting=exiting)

        err = capsys.readouterr().err
        assert "--- Orion logging error ---" in err
        assert "ValueError: Test" in err
        if not exiting:
            assert "will attempt to send these logs again" in err
        else:
            assert "log worker is stopping and these logs will not be sent" in err

    async def test_send_logs_batches_by_size(self, log_json, monkeypatch):
        test_log_size = sys.getsizeof(log_json)
        mock_create_logs = AsyncMock()
        worker = OrionLogWorker()
        monkeypatch.setattr("prefect.client.OrionClient.create_logs", mock_create_logs)

        worker.enqueue(log_json)
        worker.enqueue(log_json)
        worker.enqueue(log_json)
        with temporary_settings(
            PREFECT_LOGGING_ORION_MAX_BATCH_LOG_SIZE=str(test_log_size + 1),
            PREFECT_LOGGING_ORION_MAX_SINGLE_LOG_SIZE=str(test_log_size),
        ):
            await worker.send_logs()

        assert mock_create_logs.call_count == 3

    async def test_logs_are_sent_when_started(self, log_json, orion_client):
        with temporary_settings(PREFECT_LOGGING_ORION_LOG_INTERVAL="0.0001"):
            worker = OrionLogWorker()
            worker.enqueue(log_json)
            worker.start()
            worker.enqueue(log_json)

        # We want to ensure logs are written without the thread being joined
        await anyio.sleep(0.1)
        logs = await orion_client.read_logs()
        assert len(logs) == 2

    async def test_logs_are_sent_immediately_when_stopped(self, log_json, orion_client):
        # Set a long interval
        start_time = time.time()
        with temporary_settings(PREFECT_LOGGING_ORION_LOG_INTERVAL="10"):
            worker = OrionLogWorker()
            worker.enqueue(log_json)
            worker.start()
            worker.enqueue(log_json)
            worker.stop()
            worker.enqueue(log_json)  # Extra log will not be sent
        end_time = time.time()

        assert (
            end_time - start_time
        ) < 5  # An arbitary time less than the 10s interval

        logs = await orion_client.read_logs()
        assert len(logs) == 2

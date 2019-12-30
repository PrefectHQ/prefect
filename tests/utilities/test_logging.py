import json
import logging
import time
from unittest.mock import MagicMock

from prefect import utilities


def test_root_logger_level_responds_to_config():
    try:
        with utilities.configuration.set_temporary_config({"logging.level": "DEBUG"}):
            assert (
                utilities.logging.configure_logging(testing=True).level == logging.DEBUG
            )

        with utilities.configuration.set_temporary_config({"logging.level": "WARNING"}):
            assert (
                utilities.logging.configure_logging(testing=True).level
                == logging.WARNING
            )
    finally:
        # reset root_logger
        logger = utilities.logging.configure_logging(testing=True)
        logger.handlers = []


def test_remote_handler_is_configured_for_cloud():
    try:
        with utilities.configuration.set_temporary_config(
            {"logging.log_to_cloud": True}
        ):
            logger = utilities.logging.configure_logging(testing=True)
            assert hasattr(logger.handlers[-1], "client")
    finally:
        # reset root_logger
        logger = utilities.logging.configure_logging(testing=True)
        logger.handlers = []


def test_remote_handler_captures_errors_and_logs_them(caplog, monkeypatch):
    try:
        with utilities.configuration.set_temporary_config(
            {"logging.log_to_cloud": True, "cloud.auth_token": None}
        ):
            logger = utilities.logging.configure_logging(testing=True)
            assert hasattr(logger.handlers[-1], "client")
            logger.handlers[-1].client = MagicMock()
            child_logger = logger.getChild("sub-test")
            child_logger.critical("this should raise an error in the handler")

            time.sleep(1.5)  # wait for batch upload to occur
            critical_logs = [r for r in caplog.records if r.levelname == "CRITICAL"]
            assert len(critical_logs) == 2

            assert (
                "Failed to write log with error"
                in [
                    log.message for log in critical_logs if log.name == "CloudHandler"
                ].pop()
            )
    finally:
        # reset root_logger
        logger = utilities.logging.configure_logging(testing=True)
        logger.handlers = []


def test_remote_handler_captures_tracebacks(caplog, monkeypatch):
    monkeypatch.setattr("prefect.client.Client", MagicMock)
    client = MagicMock()
    try:
        with utilities.configuration.set_temporary_config(
            {"logging.log_to_cloud": True}
        ):
            logger = utilities.logging.configure_logging(testing=True)
            assert hasattr(logger.handlers[-1], "client")
            logger.handlers[-1].client = client

            child_logger = logger.getChild("sub-test")
            try:
                ## informative comment
                1 + "2"
            except:
                child_logger.exception("unexpected error")

            time.sleep(0.75)
            error_logs = [r for r in caplog.records if r.levelname == "ERROR"]
            assert len(error_logs) == 1

            cloud_logs = client.write_run_logs.call_args[0][0]
            assert len(cloud_logs) == 1
            logged_msg = cloud_logs[0]["message"]
            assert "TypeError" in logged_msg
            assert '1 + "2"' in logged_msg
            assert "unexpected error" in logged_msg

    finally:
        # reset root_logger
        logger = utilities.logging.configure_logging(testing=True)
        logger.handlers = []


def test_remote_handler_ships_json_payloads(caplog, monkeypatch):
    monkeypatch.setattr("prefect.client.Client", MagicMock)
    client = MagicMock()
    try:
        with utilities.configuration.set_temporary_config(
            {"logging.log_to_cloud": True}
        ):
            logger = utilities.logging.configure_logging(testing=True)
            assert hasattr(logger.handlers[-1], "client")
            logger.handlers[-1].client = client

            child_logger = logger.getChild("sub-test")
            try:
                ## informative comment
                f = lambda x: x + "2"
                f(1)
            except:
                child_logger.exception("unexpected error")

            time.sleep(0.75)
            error_logs = [r for r in caplog.records if r.levelname == "ERROR"]
            assert len(error_logs) == 1

            cloud_logs = client.write_run_logs.call_args[0][0]
            assert len(cloud_logs) == 1
            info = cloud_logs[0]["info"]
            assert json.loads(json.dumps(info))

    finally:
        # reset root_logger
        logger = utilities.logging.configure_logging(testing=True)
        logger.handlers = []


def test_cloud_handler_responds_to_config(caplog, monkeypatch):
    calls = []

    class Client:
        def write_run_logs(self, *args, **kwargs):
            calls.append(1)

    monkeypatch.setattr("prefect.client.Client", Client)
    try:
        logger = utilities.logging.configure_logging(testing=True)
        cloud_handler = logger.handlers[-1]
        assert isinstance(cloud_handler, utilities.logging.CloudHandler)

        with utilities.configuration.set_temporary_config(
            {"logging.log_to_cloud": False}
        ):
            logger.critical("testing")

        with utilities.configuration.set_temporary_config(
            {"logging.log_to_cloud": True}
        ):
            logger.critical("testing")

        with utilities.configuration.set_temporary_config(
            {"logging.log_to_cloud": False}
        ):
            logger.critical("testing")

        time.sleep(0.75)
        assert len(calls) == 1
    finally:
        # reset root_logger
        logger = utilities.logging.configure_logging(testing=True)
        logger.handlers = []


def test_cloud_handler_removes_bad_logs_from_queue_and_continues(caplog, monkeypatch):
    calls = []

    class Client:
        def write_run_logs(self, *args, **kwargs):
            calls.append(dict(args=args, kwargs=kwargs))

    monkeypatch.setattr("prefect.client.Client", Client)
    try:
        logger = utilities.logging.configure_logging(testing=True)
        cloud_handler = logger.handlers[-1]
        assert isinstance(cloud_handler, utilities.logging.CloudHandler)

        with utilities.configuration.set_temporary_config(
            {"logging.log_to_cloud": True}
        ):
            logger.critical("one")
            logger.critical(b"two")
            logger.critical("three")

        time.sleep(0.75)
        assert len(calls) == 1
        msgs = [c["message"] for c in calls[0]["args"][0]]
        assert msgs == ["one", "three"]
    finally:
        # reset root_logger
        logger = utilities.logging.configure_logging(testing=True)
        logger.handlers = []


def test_get_logger_returns_root_logger():
    assert utilities.logging.get_logger() is logging.getLogger("prefect")


def test_get_logger_with_name_returns_child_logger():
    child_logger = logging.getLogger("prefect.test")
    prefect_logger = utilities.logging.get_logger("test")

    assert prefect_logger is child_logger
    assert prefect_logger is logging.getLogger("prefect").getChild("test")

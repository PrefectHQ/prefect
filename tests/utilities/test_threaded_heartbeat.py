import threading
import time
from unittest.mock import MagicMock

from prefect.utilities.threaded_heartbeat import HeartbeatThread


def test_events_can_stop_the_heartbeat(monkeypatch):
    Client = MagicMock()
    monkeypatch.setattr("prefect.utilities.threaded_heartbeat.Client", Client)
    stop_event = threading.Event()
    heartbeat = HeartbeatThread(stop_event, "no-flow-run-id")
    heartbeat.start()
    assert heartbeat.is_alive()
    stop_event.set()
    heartbeat.join()
    assert heartbeat.is_alive() is False


def test_multiple_heartbeats_can_be_independently_stopped(monkeypatch):
    Client = MagicMock()
    monkeypatch.setattr("prefect.utilities.threaded_heartbeat.Client", Client)

    def heartbeat_factory():
        stop_event = threading.Event()
        heartbeat = HeartbeatThread(stop_event, "no-flow-run-id")
        heartbeat.start()
        return heartbeat, stop_event

    first_heartbeat, first_event = heartbeat_factory()
    other_heartbeat, other_event = heartbeat_factory()
    assert first_heartbeat.is_alive()
    assert other_heartbeat.is_alive()
    first_event.set()
    first_heartbeat.join()
    assert first_heartbeat.is_alive() is False
    assert other_heartbeat.is_alive() is True
    other_event.set()
    other_heartbeat.join()
    assert other_heartbeat.is_alive() is False


def test_heartbeat_is_daemonic_by_default(monkeypatch):
    Client = MagicMock()
    monkeypatch.setattr("prefect.utilities.threaded_heartbeat.Client", Client)
    stop_event = threading.Event()
    heartbeat = HeartbeatThread(stop_event, "no-flow-run-id")
    assert heartbeat.isDaemon()


def test_heartbeat_sends_signals_to_client(monkeypatch):
    Client = MagicMock()
    monkeypatch.setattr("prefect.utilities.threaded_heartbeat.Client", Client)
    stop_event = threading.Event()
    heartbeat = HeartbeatThread(stop_event, "no-flow-run-id")
    heartbeat.start()
    assert heartbeat.is_alive()
    stop_event.set()
    time.sleep(0.1)
    assert Client().update_flow_run_heartbeat.call_count == 1


def test_heartbeat_exceptions_are_logged_to_cloud(monkeypatch):
    Client = MagicMock()
    LOG_MANAGER = MagicMock()
    monkeypatch.setattr("prefect.utilities.threaded_heartbeat.Client", Client)
    monkeypatch.setattr("prefect.utilities.logging.LOG_MANAGER", LOG_MANAGER)
    Client().update_flow_run_heartbeat.side_effect = ValueError("Foo")

    stop_event = threading.Event()
    heartbeat = HeartbeatThread(stop_event, "my-special-flow-run-id")
    heartbeat.start()
    stop_event.set()
    heartbeat.join()

    log = LOG_MANAGER.enqueue.call_args[0][0]
    assert log["flow_run_id"] == "my-special-flow-run-id"
    assert log["name"] == "prefect.threaded_heartbeat"
    assert log["level"] == "ERROR"
    assert "Traceback" in log["message"]
    assert (
        f"Failed to send heartbeat with exception: {ValueError('Foo')!r}"
        in log["message"]
    )

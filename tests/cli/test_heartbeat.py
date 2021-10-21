import pytest
from click.testing import CliRunner
from unittest.mock import MagicMock

from prefect.cli.heartbeat import heartbeat, flow_run
from prefect.utilities.configuration import set_temporary_config


def test_heartbeat_init():
    runner = CliRunner()
    result = runner.invoke(heartbeat)
    assert result.exit_code == 0
    assert "Send heartbeats back to the Prefect API." in result.output


def test_heartbeat_help():
    runner = CliRunner()
    result = runner.invoke(heartbeat, ["--help"])
    assert result.exit_code == 0
    assert "Send heartbeats back to the Prefect API." in result.output


def test_heartbeat_flow_run(patch_post, cloud_api):
    patch_post(dict(data=dict(update_flow_run_heartbeat="success")))

    with set_temporary_config({"cloud.heartbeat_interval": 0.1}):
        runner = CliRunner()
        result = runner.invoke(heartbeat, ["flow-run", "--id", "id", "--num", "1"])
        assert result.exit_code == 0


def test_heartbeat_multiple_flow_run_heartbeats(patch_post, cloud_api):
    post = patch_post(dict(data=dict(update_flow_run_heartbeat="success")))

    with set_temporary_config({"cloud.heartbeat_interval": 0.1}):
        runner = CliRunner()
        result = runner.invoke(heartbeat, ["flow-run", "--id", "id", "--num", "2"])
        assert result.exit_code == 0
        assert post.called
        assert post.call_count == 2


def test_heartbeat_is_robust_to_exceptions(cloud_api, monkeypatch, caplog):
    Client = MagicMock()
    monkeypatch.setattr("prefect.cli.heartbeat.Client", Client)
    monkeypatch.setattr("prefect.cli.heartbeat.time.sleep", MagicMock())
    Client().update_flow_run_heartbeat.side_effect = ValueError("Foo")

    runner = CliRunner()
    result = runner.invoke(heartbeat, ["flow-run", "--id", "id", "--num", "2"])
    assert result.exit_code == 0

    # Called twice despite raising errors
    assert Client().update_flow_run_heartbeat.call_count == 2

    assert (
        f"Failed to send heartbeat with exception: {ValueError('Foo')!r}" in caplog.text
    )
    assert "Traceback" in caplog.text


def test_heartbeat_does_not_ignore_base_exceptions(cloud_api, monkeypatch, caplog):
    Client = MagicMock()
    monkeypatch.setattr("prefect.cli.heartbeat.Client", Client)
    monkeypatch.setattr("prefect.cli.heartbeat.time.sleep", MagicMock())
    Client().update_flow_run_heartbeat.side_effect = KeyboardInterrupt()

    runner = CliRunner()
    result = runner.invoke(heartbeat, ["flow-run", "--id", "id", "--num", "2"])
    assert result.exit_code == 1

    # Called _once_, error caused immediate exit
    assert Client().update_flow_run_heartbeat.call_count == 1

    assert (
        "Heartbeat process encountered terminal exception: KeyboardInterrupt()"
        in caplog.text
    )
    assert "Traceback" in caplog.text


@pytest.mark.parametrize("terminal_exc", [True, False])
def test_heartbeat_exceptions_are_logged_to_cloud(cloud_api, monkeypatch, terminal_exc):
    Client = MagicMock()
    LOG_MANAGER = MagicMock()
    monkeypatch.setattr("prefect.cli.heartbeat.Client", Client)
    monkeypatch.setattr("prefect.utilities.logging.LOG_MANAGER", LOG_MANAGER)
    monkeypatch.setattr("prefect.cli.heartbeat.time.sleep", MagicMock())
    Client().update_flow_run_heartbeat.side_effect = (
        KeyboardInterrupt() if terminal_exc else ValueError("Foo")
    )

    runner = CliRunner()
    runner.invoke(heartbeat, ["flow-run", "--id", "id", "--num", "2"])

    # The exception was logged both times
    log = LOG_MANAGER.enqueue.call_args[0][0]
    assert log["flow_run_id"] == "id"
    assert log["name"] == "prefect.subprocess_heartbeat"
    assert log["level"] == "ERROR"

    if terminal_exc:
        assert (
            "Heartbeat process encountered terminal exception: KeyboardInterrupt()"
            in log["message"]
        )
    else:
        assert (
            f"Failed to send heartbeat with exception: {ValueError('Foo')!r}"
            in log["message"]
        )
    assert "Traceback" in log["message"]

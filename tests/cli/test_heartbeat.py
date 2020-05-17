from unittest.mock import MagicMock

from click.testing import CliRunner
import pytest

from prefect.cli.heartbeat import heartbeat
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


def test_heartbeat_task_run(patch_post):
    patch_post(dict(data=dict(update_task_run_heartbeat="success")))

    with set_temporary_config(
        {
            "cloud.graphql": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "cloud.heartbeat_interval": 0.1,
        }
    ):
        runner = CliRunner()
        result = runner.invoke(heartbeat, ["task-run", "--id", "id", "--num", "1"])
        assert result.exit_code == 0


def test_heartbeat_multiple_task_run_heartbeats(patch_post):
    post = patch_post(dict(data=dict(update_task_run_heartbeat="success")))

    with set_temporary_config(
        {
            "cloud.graphql": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "cloud.heartbeat_interval": 0.1,
        }
    ):
        runner = CliRunner()
        result = runner.invoke(heartbeat, ["task-run", "--id", "id", "--num", "2"])
        assert result.exit_code == 0
        assert post.called
        assert post.call_count == 2


def test_heartbeat_flow_run(patch_post):
    patch_post(dict(data=dict(update_flow_run_heartbeat="success")))

    with set_temporary_config(
        {
            "cloud.graphql": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "cloud.heartbeat_interval": 0.1,
        }
    ):
        runner = CliRunner()
        result = runner.invoke(heartbeat, ["flow-run", "--id", "id", "--num", "1"])
        assert result.exit_code == 0


def test_heartbeat_multiple_flow_run_heartbeats(patch_post):
    post = patch_post(dict(data=dict(update_flow_run_heartbeat="success")))

    with set_temporary_config(
        {
            "cloud.graphql": "http://my-cloud.foo",
            "cloud.auth_token": "secret_token",
            "cloud.heartbeat_interval": 0.1,
        }
    ):
        runner = CliRunner()
        result = runner.invoke(heartbeat, ["flow-run", "--id", "id", "--num", "2"])
        assert result.exit_code == 0
        assert post.called
        assert post.call_count == 2

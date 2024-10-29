import os
from unittest.mock import AsyncMock, patch

from prefect.cli.shell import run_shell_process
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import run_sync_in_worker_thread


async def test_shell_serve(prefect_client):
    flow_name = "Flood Brothers"

    await run_sync_in_worker_thread(
        invoke_and_assert,
        [
            "shell",
            "serve",
            "echo 'Hello, World!'",
            "--flow-name",
            flow_name,
            "--run-once",
        ],
        expected_code=0,
        expected_output_contains=[
            f"Your flow {flow_name!r} is being served and polling for scheduled runs!"
        ],
    )
    deployment = await prefect_client.read_deployment_by_name(
        f"{flow_name}/CLI Runner Deployment"
    )
    assert deployment.name == "CLI Runner Deployment"
    assert deployment.tags == ["shell"]


async def test_shell_serve_options(prefect_client):
    flow_name = "Flood Brothers"
    deployment_name = "3065 Rockwell Export"
    deployments_tags = ["dry", "wet", "dipped"]

    await run_sync_in_worker_thread(
        invoke_and_assert,
        [
            "shell",
            "serve",
            "echo 'Hello, World!'",
            "--flow-name",
            flow_name,
            "--concurrency-limit",
            "5",
            "--deployment-name",
            deployment_name,
            "--run-once",
            "--tag",
            deployments_tags[0],
            "--tag",
            deployments_tags[1],
            "--tag",
            deployments_tags[2],
            "--timezone",
            "America/Chicago",
            "--cron-schedule",
            "0 4 * * *",
        ],
        expected_code=0,
        expected_output_contains=[
            f"Your flow {flow_name!r} is being served and polling for scheduled runs!"
        ],
    )
    deployment = await prefect_client.read_deployment_by_name(
        f"{flow_name}/{deployment_name}"
    )
    deployments_tags.append("shell")
    assert deployment.name == deployment_name
    assert deployment.tags == deployments_tags

    schedule = deployment.schedules[0].schedule
    assert schedule.cron == "0 4 * * *"
    assert schedule.timezone == "America/Chicago"


async def test_shell_watch(caplog, prefect_client):
    flow_name = "Chicago River Flow"
    flows_run_name = "Reverse Flow"
    flow_run_tags = ["chair", "table", "bucket"]
    await run_sync_in_worker_thread(
        invoke_and_assert,
        [
            "shell",
            "watch",
            "echo 'Hello, World!'",
            "--flow-name",
            flow_name,
            "--flow-run-name",
            flows_run_name,
            "--tag",
            flow_run_tags[0],
            "--tag",
            flow_run_tags[1],
            "--tag",
            flow_run_tags[2],
        ],
        expected_code=0,
    )
    assert "Hello, World!" in caplog.text

    assert len(flow_runs := await prefect_client.read_flow_runs()) == 1
    flow_run_tags.append("shell")
    flow_run = flow_runs[0]
    assert flow_run.name == flows_run_name
    assert set(flow_run.tags) == set(flow_run_tags)


async def test_shell_watch_options(caplog, prefect_client):
    await run_sync_in_worker_thread(
        invoke_and_assert,
        [
            "shell",
            "watch",
            "echo 'Hello, World!'",
        ],
        expected_code=0,
    )
    assert "Hello, World!" in caplog.text

    assert len(flow_runs := await prefect_client.read_flow_runs()) == 1
    flow_run = flow_runs[0]
    assert flow_run.tags == ["shell"]


async def test_shell_runner_integration(monkeypatch):
    with patch("prefect.cli.shell.Runner.start", new_callable=AsyncMock) as runner_mock:
        flow_name = "Flood Brothers"

        await run_sync_in_worker_thread(
            invoke_and_assert,
            [
                "shell",
                "serve",
                "echo 'Hello, World!'",
                "--flow-name",
                flow_name,
                "--run-once",
            ],
            expected_code=0,
            expected_output_contains=[
                f"Your flow {flow_name!r} is being served and polling for scheduled runs!"
            ],
        )

        runner_mock.assert_awaited_once_with(run_once=True)


class TestRunShellProcess:
    def test_run_shell_process_basic(self, tmp_path):
        """Test basic command execution"""
        test_file = tmp_path / "test.txt"
        run_shell_process(f"touch {test_file}")
        assert test_file.exists()

    def test_run_shell_process_with_cwd(self, tmp_path):
        """Test command execution with custom working directory"""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        test_file = "test.txt"

        run_shell_process(f"touch {test_file}", popen_kwargs={"cwd": str(subdir)})

        assert (subdir / test_file).exists()

    def test_run_shell_process_with_env(self, tmp_path):
        """Test command execution with custom environment variables"""
        custom_env = os.environ.copy()
        custom_env["TEST_VAR"] = "hello"

        run_shell_process(
            "echo $TEST_VAR > output.txt",
            popen_kwargs={"env": custom_env, "cwd": str(tmp_path)},
        )

        assert (tmp_path / "output.txt").read_text().strip() == "hello"

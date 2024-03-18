from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import run_sync_in_worker_thread


###
# Test flow success and failure
# run flow, test success and failure in serve
# Test deployment flags correctly represented
###
async def test_shell_serve(prefect_client):
    flow_name = "Flood Brothers"
    deployment_name = "3065 Rockwell Export"
    deployments_tags = ["dry", "wet", "dipped"]

    await run_sync_in_worker_thread(
        invoke_and_assert,
        [
            "shell",
            "serve",
            "echo 'Hello, World!'",
            "--name",
            flow_name,
            "--timezone",
            "America/New_York",
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
    assert deployment.name == deployment_name
    assert deployment.tags == deployments_tags.append("shell")

    schedule = deployment.schedules[0].schedule
    assert schedule.cron == "0 4 * * *"
    assert schedule.timezone == "America/Chicago"


def test_shell_watch(caplog):
    invoke_and_assert(
        ["shell", "watch", "echo 'Hello, World!'"],
        expected_code=0,
    )
    assert "Hello, World!" in caplog.text

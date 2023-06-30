import prefect
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import run_sync_in_worker_thread


async def test_ls_deployment_shows_deployments(
    prefect_client: prefect.PrefectClient, deployment
):
    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=[
            "deployment",
            "ls",
        ],
        expected_output_contains=[
            "Deployments",
            str(deployment.name),
            str(deployment.id),
        ],
    )

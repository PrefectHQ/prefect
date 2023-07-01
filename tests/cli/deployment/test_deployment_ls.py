import prefect
from prefect.server import models
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import run_sync_in_worker_thread


async def test_ls_deployment_shows_all_deployments(
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


async def test_ls_deployment_crashes_if_flow_not_found(
    prefect_client: prefect.PrefectClient, session, deployment, deployment_2
):
    await models.flows.delete_flow(session, deployment_2.flow_id)

    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=[
            "deployment",
            "ls",
        ],
        expected_code=1,
        expected_output_contains=[
            "Deployments",
        ],
    )

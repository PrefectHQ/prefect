from uuid import UUID

import pytest

import prefect.exceptions
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncio import sync_compatible


@sync_compatible
async def assert_flow_run_is_deleted(orion_client, flow_run_id: UUID):
    """
    Make sure that the flow run created for our CLI test is actually deleted.
    """
    with pytest.raises(prefect.exceptions.ObjectNotFound):
        await orion_client.read_flow_run(flow_run_id)


@pytest.mark.usefixtures("disable_terminal_wrapping")
def test_delete_flow_run_fails_correctly():
    missing_flow_run_id = "ccb86ed0-e824-4d8b-b825-880401320e41"
    invoke_and_assert(
        command=["flow-run", "delete", missing_flow_run_id],
        expected_output=f"Flow run '{missing_flow_run_id}' not found!",
        expected_code=1,
    )


@pytest.mark.usefixtures("disable_terminal_wrapping")
def test_delete_flow_run_succeeds(orion_client, flow_run):
    invoke_and_assert(
        command=["flow-run", "delete", str(flow_run.id)],
        expected_output=f"Successfully deleted flow run '{str(flow_run.id)}'.",
        expected_code=0,
    )

    assert_flow_run_is_deleted(orion_client, flow_run.id)

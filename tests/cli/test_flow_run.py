from prefect.testing.cli import invoke_and_assert


def test_delete_flow_run_fails_correctly():
    missing_flow_run_id = "ccb86ed0-e824-4d8b-b825-880401320e41"
    invoke_and_assert(
        command=["flow-run", "delete", missing_flow_run_id],
        expected_output=f"Flow run '{missing_flow_run_id}' not found!",
        expected_code=1,
    )


def test_delete_flow_run_succeeds(flow_run):

    invoke_and_assert(
        command=["flow-run", "delete", str(flow_run.id)],
        expected_output=f"Successfully deleted flow run '{str(flow_run.id)}'.",
        expected_code=0,
    )

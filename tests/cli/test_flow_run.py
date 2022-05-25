import asyncio
import pdb
import time

from prefect import flow
from prefect.flow_runners import UniversalFlowRunner
from prefect.testing.cli import invoke_and_assert


def test_delete_flow_run_fails_correctly():
    UUID_404_input = "ccb86ed0-e824-4d8b-b825-880401320e41"
    UUID_404_output = "Flow run ccb86ed0-e824-4d8b-b825-880401320e41 not found!"
    invoke_and_assert(
        command=["flow-run", "delete", UUID_404_input],
        expected_output=UUID_404_output,
        expected_code=1,
    )


def test_delete_flow_run_succeeds(flow_run):

    flow_id_string = str(flow_run.id)
    print(f"flow run: {flow_run!r}")
    good_output = f"Successfully deleted flow run {flow_id_string}."
    invoke_and_assert(
        command=["flow-run", "delete", flow_id_string],
        expected_output=good_output,
        expected_code=0,
    )

import pytest
from unittest.mock import MagicMock

from prefect import Flow
from prefect.tasks.prefect.flow_run_cancel import CancelFlowRun


def test_flow_run_cancel(monkeypatch):
    client = MagicMock()
    client.cancel_flow_run = MagicMock(return_value=True)
    monkeypatch.setattr(
        "prefect.tasks.prefect.flow_run_cancel.Client", MagicMock(return_value=client)
    )
    flow_cancel_task = CancelFlowRun(flow_run_id="id123")

    # Verify correct initialization
    assert flow_cancel_task.flow_run_id == "id123"
    # Verify client called with arguments
    flow = Flow("TestContext")
    flow.add_task(flow_cancel_task)
    flow.run()
    assert client.cancel_flow_run.called
    assert client.cancel_flow_run.call_args[0][0] == "id123"

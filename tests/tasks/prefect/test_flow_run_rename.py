import pytest
from unittest.mock import MagicMock

import prefect
from prefect.tasks.prefect.flow_run_rename import RenameFlowRunTask


def test_flow_run_rename_task(monkeypatch):
    client = MagicMock()
    client.set_flow_run_name = MagicMock(return_value=True)
    monkeypatch.setattr(
        "prefect.tasks.prefect.flow_run_rename.Client", MagicMock(return_value=client)
    )

    task = RenameFlowRunTask(flow_run_id="id123", flow_run_name="a_new_name!")

    # Verify correct initialization
    assert task.flow_run_id == "id123"
    assert task.flow_run_name == "a_new_name!"

    # Verify client called with arguments
    task.run()
    assert client.set_flow_run_name.called
    assert client.set_flow_run_name.call_args[0][0] == "id123"
    assert client.set_flow_run_name.call_args[0][1] == "a_new_name!"


def test_default_flow_run_id(monkeypatch):
    client = MagicMock()
    client.set_flow_run_name = MagicMock(return_value=True)
    monkeypatch.setattr(
        "prefect.tasks.prefect.flow_run_rename.Client", MagicMock(return_value=client)
    )

    task = RenameFlowRunTask(flow_run_name="a_new_name!")


    # Verify client called with arguments
    with prefect.context(flow_run_id="id123"):
        task.run()
    assert client.set_flow_run_name.called
    assert client.set_flow_run_name.call_args[0][0] == "id123"
    assert client.set_flow_run_name.call_args[0][1] == "a_new_name!"


def test_missing_flow_run_id():
    task = RenameFlowRunTask()
    with pytest.raises(
        ValueError, match="No flow run ID found in context. Must provide a flow run id."
    ):
        task.run(flow_run_name="a_new_name!")


def test_missing_flow_run_name():
    task = RenameFlowRunTask()
    with pytest.raises(ValueError, match="Must provide a flow name."):
        task.run(flow_run_id="id123")

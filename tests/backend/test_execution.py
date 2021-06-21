import pytest
from unittest.mock import MagicMock

from prefect.backend.execution import _fail_flow_run
from prefect.engine.state import Failed


@pytest.fixture()
def cloud_mocks(monkeypatch):
    class CloudMocks:
        FlowRunView = MagicMock()
        Client = MagicMock()

    mocks = CloudMocks()
    monkeypatch.setattr("prefect.backend.execution.FlowRunView", mocks.FlowRunView)
    monkeypatch.setattr("prefect.Client", mocks.Client)

    return mocks


def test_fail_flow_run(cloud_mocks):
    _fail_flow_run(flow_run_id="flow-run-id", message="fail message")
    cloud_mocks.Client().set_flow_run_state.assert_called_once_with(
        flow_run_id="flow-run-id", state=Failed("fail message")
    )
    cloud_mocks.Client().write_run_logs.assert_called_once_with(
        [
            dict(
                flow_run_id="flow-run-id",
                name="prefect.backend.execution",
                message="fail message",
                level="ERROR",
            )
        ]
    )

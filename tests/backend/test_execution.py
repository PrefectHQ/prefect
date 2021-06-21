import pytest
from unittest.mock import MagicMock

import prefect
from prefect.backend.execution import _fail_flow_run, _fail_flow_run_on_exception
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


@pytest.mark.parametrize("is_finished", [True, False])
def test_fail_flow_run_on_exception(monkeypatch, cloud_mocks, is_finished, caplog):
    monkeypatch.setattr("prefect.backend.execution._fail_flow_run", MagicMock())
    cloud_mocks.FlowRunView.from_flow_run_id().state.is_finished.return_value = (
        is_finished
    )

    with pytest.raises(ValueError):  # Reraises the exception
        with _fail_flow_run_on_exception(
            flow_run_id="flow-run-id", message="fail message: {exc}"
        ):
            raise ValueError("Exception message")

    # Fails in Cloud if the run is not finished already
    if is_finished:
        prefect.backend.execution._fail_flow_run.assert_not_called()
    else:
        prefect.backend.execution._fail_flow_run.assert_called_once_with(
            "flow-run-id",
            message="fail message: ValueError('Exception message')",
        )

    # Logs locally
    assert "fail message: ValueError('Exception message')" in caplog.text
    assert "Traceback" in caplog.text


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

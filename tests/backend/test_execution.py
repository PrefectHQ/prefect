import pendulum
import pytest
from unittest.mock import MagicMock

import prefect
from prefect.backend.execution import (
    _fail_flow_run,
    _fail_flow_run_on_exception,
    _get_flow_run_scheduled_start_time,
)
from prefect.engine.state import Failed, Scheduled
from prefect.utilities.graphql import GraphQLResult


@pytest.fixture()
def cloud_mocks(monkeypatch):
    class CloudMocks:
        FlowRunView = MagicMock()
        Client = MagicMock()

    mocks = CloudMocks()
    monkeypatch.setattr("prefect.backend.execution.FlowRunView", mocks.FlowRunView)
    monkeypatch.setattr("prefect.Client", mocks.Client)

    return mocks


def test_get_flow_run_scheduled_start_time_from_state_time(cloud_mocks):
    start_time = pendulum.now("utc")
    states = [
        Scheduled(start_time=start_time.add(seconds=10)).serialize(),
        Scheduled(start_time=start_time).serialize(),
        Scheduled().serialize(),
    ]

    # Attach db "created" times to the states, the second one is the newest
    states[0]["created"] = pendulum.now().subtract(seconds=10).isoformat()
    states[1]["created"] = pendulum.now().isoformat()

    # The last state will have an empty start time and no created time to test handling
    # of malformed data
    states[2]["start_time"] = None

    cloud_mocks.Client().graphql.return_value = GraphQLResult(
        {
            "data": {
                "flow_run": [
                    {
                        "scheduled_start_time": (
                            start_time.subtract(seconds=10).isoformat()
                        ),
                        "states": states,
                    }
                ]
            }
        }
    )

    result = _get_flow_run_scheduled_start_time("flow-run-id")
    assert result == start_time


@pytest.mark.parametrize("with_states", [True, False])
def test_get_flow_run_scheduled_start_time_from_flow_run_scheduled_time(
    cloud_mocks, with_states
):
    # This occurs when there are no states available or when the states have no start
    # time on them
    states = []
    if with_states:
        states = [Failed().serialize()]
        states[0]["created"] = pendulum.now()

    start_time = pendulum.now("utc")

    cloud_mocks.Client().graphql.return_value = GraphQLResult(
        {
            "data": {
                "flow_run": [
                    {
                        "scheduled_start_time": start_time.isoformat(),
                        "states": states,
                    }
                ]
            }
        }
    )

    result = _get_flow_run_scheduled_start_time("flow-run-id")
    assert result == start_time


def test_get_flow_run_scheduled_start_time_query_is_correct(cloud_mocks):

    # Just return nothing to simplify the test / cover malformed response
    cloud_mocks.Client().graphql.return_value = {}

    with pytest.raises(ValueError, match="Unexpected result"):
        _get_flow_run_scheduled_start_time("flow-run-id")

    cloud_mocks.Client().graphql.assert_called_once_with(
        {
            "query": {
                'flow_run(where: { id: { _eq: "flow-run-id" } })': {
                    'states(where: { state: { _eq: "Scheduled" } })': {
                        "created",
                        "start_time",
                    },
                    "scheduled_start_time": True,
                }
            }
        }
    )


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

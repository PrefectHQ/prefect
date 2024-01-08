import uuid

import httpx
import pytest

from prefect import flow
from prefect.runner import (
    submit_to_runner,
)
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ENABLE_EXTRA_RUNNER_ENDPOINTS,
    PREFECT_RUNNER_SERVER_ENABLE,
    PREFECT_RUNNER_SERVER_ENABLE_BLOCKING_FAILOVER,
    temporary_settings,
)


@flow
def schleeb(whatever):
    return whatever


@flow(log_prints=True)
def independent():
    print("i don't need no stinkin' parameters")


@pytest.fixture(autouse=True)
def runner_settings():
    with temporary_settings(
        {
            PREFECT_RUNNER_SERVER_ENABLE: True,
            PREFECT_EXPERIMENTAL_ENABLE_EXTRA_RUNNER_ENDPOINTS: True,
        }
    ):
        yield


def test_submission_raises_if_extra_endpoints_not_enabled():
    with temporary_settings(
        {PREFECT_EXPERIMENTAL_ENABLE_EXTRA_RUNNER_ENDPOINTS: False}
    ):
        with pytest.raises(
            ValueError,
            match="`submit_to_runner` utility requires the `Runner` webserver",
        ):
            submit_to_runner(lambda: None)


async def test_submission_fails_over_if_webserver_is_not_running(
    caplog, prefect_client
):
    expected_text = "The `submit_to_runner` utility failed to connect to the `Runner` webserver, and blocking failover is enabled."  # noqa
    with caplog.at_level("WARNING", logger="prefect.webserver"), temporary_settings(
        {
            PREFECT_RUNNER_SERVER_ENABLE: False,
        }
    ):
        p = {"whatever": 42}
        flow_run_id = await submit_to_runner(schleeb, p)

        assert isinstance(flow_run_id, uuid.UUID)
        assert expected_text in caplog.text

        flow_run = await prefect_client.read_flow_run(flow_run_id)

        assert flow_run.state.is_completed()
        assert flow_run.parameters == p


async def test_submission_with_optional_parameters(prefect_client):
    flow_run_id = await submit_to_runner(independent)

    assert isinstance(flow_run_id, uuid.UUID)

    flow_run = await prefect_client.read_flow_run(flow_run_id)

    assert flow_run.state.is_completed()
    assert flow_run.parameters == {}


def test_submission_raises_if_webserver_not_running_and_no_failover():
    with temporary_settings(
        {
            PREFECT_RUNNER_SERVER_ENABLE: False,
            PREFECT_RUNNER_SERVER_ENABLE_BLOCKING_FAILOVER: False,
        }
    ):
        with pytest.raises((httpx.HTTPStatusError, RuntimeError)):
            submit_to_runner(schleeb, {"d": {"schleeb": 9001}})

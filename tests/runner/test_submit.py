import asyncio
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


def read_flow_run_sync(client, flow_run_id):
    async def _read_flow_run():
        return await client.read_flow_run(flow_run_id)

    return asyncio.run(_read_flow_run())


@flow
def identity(whatever):
    return whatever


@flow
async def async_identity(whatever):
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
            submit_to_runner(identity, {"whatever": 42})


@pytest.mark.parametrize("prefect_callable", [identity, async_identity])
def test_submit_to_runner_happy_path_sync_context(prefect_client, prefect_callable):
    flow_run_id = submit_to_runner(prefect_callable, {"whatever": 42})

    assert isinstance(flow_run_id, uuid.UUID)
    flow_run = read_flow_run_sync(prefect_client, flow_run_id)

    assert flow_run.state.is_completed()
    assert flow_run.parameters == {"whatever": 42}


@pytest.mark.parametrize("prefect_callable", [identity, async_identity])
async def test_submit_to_runner_happy_path_async_context(
    prefect_client, prefect_callable
):
    flow_run_id = await submit_to_runner(prefect_callable, {"whatever": 42})

    assert isinstance(flow_run_id, uuid.UUID)
    flow_run = await prefect_client.read_flow_run(flow_run_id)

    assert flow_run.state.is_completed()
    assert flow_run.parameters == {"whatever": 42}


async def test_submit_to_runner_raises_if_not_prefect_callable():
    with pytest.raises(
        TypeError,
        match=(
            "The `submit_to_runner` utility only supports submitting flows and tasks."
        ),
    ):
        await submit_to_runner(lambda: None)


async def test_submission_with_optional_parameters(prefect_client):
    flow_run_id = await submit_to_runner(independent)

    assert isinstance(flow_run_id, uuid.UUID)

    flow_run = await prefect_client.read_flow_run(flow_run_id)

    assert flow_run.state.is_completed()
    assert flow_run.parameters == {}


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
        flow_run_id = await submit_to_runner(identity, p)

        assert isinstance(flow_run_id, uuid.UUID)
        assert expected_text in caplog.text

        flow_run = await prefect_client.read_flow_run(flow_run_id)

        assert flow_run.state.is_completed()
        assert flow_run.parameters == p


def test_submission_raises_if_webserver_not_running_and_no_failover():
    with temporary_settings(
        {
            PREFECT_RUNNER_SERVER_ENABLE: False,
            PREFECT_RUNNER_SERVER_ENABLE_BLOCKING_FAILOVER: False,
        }
    ):
        with pytest.raises((httpx.HTTPStatusError, RuntimeError)):
            submit_to_runner(identity, {"d": {"schleeb": 9001}})

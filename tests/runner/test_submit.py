import asyncio
import uuid
from typing import Dict, List, Union
from unittest import mock

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


@flow
def super_schleeb(*args, **kwargs):
    return args, kwargs


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


@mock.patch(
    "prefect.runner.submit._run_prefect_callable_and_retrieve_run_id",
)
def test_failed_submission_gets_run_sync(run_callable_mock: mock.Mock, caplog):
    with mock.patch(
        "prefect.runner.submit._submit_flow_to_runner",
        side_effect=httpx.ConnectError(""),
    ):
        inputs = [{"schleeb": 1}, {"schleeb": 2}, {"schleeb": 3}]
        results = submit_to_runner(schleeb, inputs)

        assert run_callable_mock.call_count == len(inputs)
        assert run_callable_mock.call_args_list == [
            mock.call(schleeb, d) for d in inputs
        ]
        assert len(results) == len(inputs)
        assert (
            "The `submit_to_runner` utility failed to connect to the `Runner` webserver"
            in caplog.text
        )


@mock.patch(
    "prefect.runner.submit._run_prefect_callable_and_retrieve_run_id",
)
def test_intermittent_failed_submission_gets_run_sync(
    run_callable_mock: mock.Mock, caplog
):
    """
    Verify that failures interspersed between successful submissions are run sync
    """
    with mock.patch(
        "prefect.runner.submit._submit_flow_to_runner",
        side_effect=[uuid.uuid4(), httpx.ConnectError(""), uuid.uuid4()],
    ):
        inputs = [{"schleeb": 1}, {"schleeb": 2}, {"schleeb": 3}]
        results = submit_to_runner(schleeb, inputs)

        assert run_callable_mock.call_count == 1
        assert run_callable_mock.call_args_list == [mock.call(schleeb, {"schleeb": 2})]
        assert len(results) == len(inputs)
        assert (
            "The `submit_to_runner` utility failed to connect to the `Runner` webserver"
            in caplog.text
        )


def test_failed_submission_are_not_run_sync_if_configured(caplog):
    with temporary_settings(
        {
            PREFECT_RUNNER_SERVER_ENABLE: True,
            PREFECT_RUNNER_SERVER_ENABLE_BLOCKING_FAILOVER: False,
        }
    ), mock.patch(
        "prefect.runner.submit._submit_flow_to_runner",
        side_effect=httpx.ConnectError(""),
    ) as sub_flow_mock:
        with pytest.raises(RuntimeError):
            submit_to_runner(schleeb, {"schleeb": 1})

        assert sub_flow_mock.call_count == 1
        assert sub_flow_mock.call_args_list == [
            mock.call(schleeb, {"schleeb": 1}, True)
        ], sub_flow_mock.call_args_list
        assert (
            "The `submit_to_runner` utility failed to connect to the `Runner`"
            in caplog.text
        )


@pytest.mark.parametrize("input_", [[{"schleeb": 1}, {"schleeb": 2}], {"schleeb": 3}])
def test_return_for_submissions_matches_input(input_: Union[List[Dict], Dict]):
    def _uuid_generator(*_, **__):
        return uuid.uuid4()

    with mock.patch(
        "prefect.runner.submit._submit_flow_to_runner",
        side_effect=_uuid_generator,
    ):
        results = submit_to_runner(schleeb, input_)

        if isinstance(input_, dict):
            assert isinstance(results, uuid.UUID)
        else:
            assert len(results) == len(input_)
            assert all(isinstance(r, uuid.UUID) for r in results)


@pytest.mark.parametrize(
    "input_",
    [
        {
            "name": "Schleeb",
            "age": 99,
            "young": True,
            "metadata": [{"nested": "info"}],
            "data": [True, False, True],
            "info": {"nested": "info"},
        },
        [
            {
                "name": "Schleeb",
                "age": 99,
                "young": True,
                "metadata": [{"nested": "info"}],
                "data": [True, False, True],
                "info": {"nested": "info"},
            }
        ],
        [
            {
                "name": "Schleeb",
                "age": 99,
                "young": True,
                "metadata": [{"nested": "info"}],
                "data": [True, False, True],
                "info": {"nested": "info"},
            }
        ],
        [{"1": {2: {3: {4: None}}}}],
    ],
)
def test_types_in_submission(input_: Union[List[Dict], Dict]):
    results = submit_to_runner(super_schleeb, input_)

    if isinstance(input_, List):
        assert len(results) == len(input_)
        for r in results:
            assert isinstance(r, uuid.UUID)
    else:
        assert isinstance(results, uuid.UUID)

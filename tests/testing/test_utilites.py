import uuid
import warnings
from unittest.mock import MagicMock

import pytest

from prefect import flow, task
from prefect.client.orchestration import get_client
from prefect.server import schemas
from prefect.settings import (
    PREFECT_API_DATABASE_CONNECTION_URL,
    PREFECT_API_URL,
    PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS,
)
from prefect.testing.utilities import assert_does_not_warn, prefect_test_harness


def test_assert_does_not_warn_no_warning():
    with assert_does_not_warn():
        pass


def test_assert_does_not_warn_does_not_capture_exceptions():
    with pytest.raises(ValueError):
        with assert_does_not_warn():
            raise ValueError()


def test_assert_does_not_warn_raises_assertion_error():
    with pytest.raises(AssertionError, match="Warning was raised"):
        with assert_does_not_warn():
            warnings.warn("Test")


async def test_prefect_test_harness():
    # TODO: This test fails intermittently with a directory error in Windows
    # due to temporary directory differences
    very_specific_name = str(uuid.uuid4())

    @task
    def test_task():
        pass

    @flow(name=very_specific_name)
    def test_flow():
        test_task()
        return "foo"

    existing_db_url = PREFECT_API_DATABASE_CONNECTION_URL.value()
    existing_api_url = PREFECT_API_URL.value()

    with prefect_test_harness():
        async with get_client() as client:
            # should be able to run a flow
            assert test_flow() == "foo"

            # should be able to query for generated data
            flows = await client.read_flows(
                flow_filter=schemas.filters.FlowFilter(
                    name={"any_": [very_specific_name]}
                )
            )
            assert len(flows) == 1
            assert flows[0].name == very_specific_name

            assert PREFECT_API_URL.value() != existing_api_url

    # API URL should be reset
    assert PREFECT_API_URL.value() == existing_api_url

    # database connection should be reset
    assert PREFECT_API_DATABASE_CONNECTION_URL.value() == existing_db_url

    # outside the context, none of the test runs should not persist
    async with get_client() as client:
        flows = await client.read_flows(
            flow_filter=schemas.filters.FlowFilter(name={"any_": [very_specific_name]})
        )
        assert len(flows) == 0


def test_prefect_test_harness_timeout(monkeypatch):
    server = MagicMock()
    monkeypatch.setattr(
        "prefect.testing.utilities.SubprocessASGIServer",
        server,
    )
    server().api_url = "http://localhost:42000"

    with prefect_test_harness():
        server().start.assert_called_once_with(timeout=30)

    server().start.reset_mock()

    with prefect_test_harness(server_startup_timeout=120):
        server().start.assert_called_once_with(timeout=120)

    server().start.reset_mock()

    with prefect_test_harness(server_startup_timeout=None):
        server().start.assert_called_once_with(
            timeout=PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS.value()
        )

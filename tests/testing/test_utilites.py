import uuid
import warnings

import pytest

from prefect import flow, task
from prefect.client import get_client
from prefect.orion import schemas
from prefect.settings import PREFECT_API_URL, PREFECT_ORION_DATABASE_CONNECTION_URL
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
    very_specific_name = str(uuid.uuid4())

    @task
    def test_task():
        pass

    @flow(name=very_specific_name)
    def test_flow():
        test_task()
        return "foo"

    existing_db_url = PREFECT_ORION_DATABASE_CONNECTION_URL.value()

    with prefect_test_harness():
        # should be able to run a flow
        assert test_flow().result() == "foo"

        async with get_client() as client:
            # should be able to query for generated data
            flows = await client.read_flows(
                flow_filter=schemas.filters.FlowFilter(
                    name={"any_": [very_specific_name]}
                )
            )
            assert len(flows) == 1
            assert flows[0].name == very_specific_name

            # should be using an ephemeral client
            assert client._ephemeral_app is not None

            # should be connected to a different database
            assert PREFECT_ORION_DATABASE_CONNECTION_URL.value() != existing_db_url

    # outside the context, none of the test runs should not persist
    async with get_client() as client:
        flows = await client.read_flows(
            flow_filter=schemas.filters.FlowFilter(name={"any_": [very_specific_name]})
        )
        assert len(flows) == 0

    # database connection should be reset
    assert PREFECT_ORION_DATABASE_CONNECTION_URL.value() == existing_db_url

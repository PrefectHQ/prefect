from typing import Dict

import pytest

from prefect import flow
from prefect.blocks.core import Block
from prefect.client.orchestration import PrefectClient, get_client
from prefect.settings import (
    PREFECT_CLIENT_MAX_RETRIES,
    PREFECT_CLOUD_API_URL,
    temporary_settings,
)


@pytest.fixture
async def prefect_client(test_database_connection_url):
    async with get_client() as client:
        yield client


@pytest.fixture
async def cloud_client(prefect_client):
    async with PrefectClient(PREFECT_CLOUD_API_URL.value()) as cloud_client:
        yield cloud_client


@pytest.fixture(scope="session")
def flow_function():
    @flow(version="test", description="A test function")
    def client_test_flow(param=1):
        return param

    return client_test_flow


@pytest.fixture(scope="session")
def flow_function_dict_parameter():
    @flow(
        version="test", description="A test function with a dictionary as a parameter"
    )
    def client_test_flow_dict_parameter(dict_param: Dict[int, str]):
        return dict_param

    return client_test_flow_dict_parameter


@pytest.fixture(scope="session")
def test_block():
    class x(Block):
        _block_type_slug = "x-fixture"
        _logo_url = "https://en.wiktionary.org/wiki/File:LetterX.svg"
        _documentation_url = "https://en.wiktionary.org/wiki/X"
        foo: str

    return x


@pytest.fixture(autouse=True)
def enable_client_retries_if_marked(request):
    """
    Client retries are disabled during testing by default to reduce overhead.

    Test functions or classes can be marked with `@pytest.mark.enable_client_retries`
    to turn on client retries if they are testing retry functionality.
    """
    marker = request.node.get_closest_marker("enable_client_retries")
    if marker is not None:
        with temporary_settings(updates={PREFECT_CLIENT_MAX_RETRIES: 5}):
            yield True
    else:
        yield False

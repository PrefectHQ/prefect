from typing import AsyncGenerator, Dict, Generator

import pytest
from fastapi import FastAPI
from pydantic import HttpUrl

from prefect import flow
from prefect.blocks.core import Block
from prefect.client.orchestration import PrefectClient, SyncPrefectClient, get_client
from prefect.settings import PREFECT_CLOUD_API_URL


@pytest.fixture
async def prefect_client(
    test_database_connection_url: str,
) -> AsyncGenerator[PrefectClient, None]:
    async with get_client() as client:
        yield client


@pytest.fixture
async def in_memory_prefect_client(app: FastAPI) -> AsyncGenerator[PrefectClient, None]:
    """
    Yield a test client that communicates with an in-memory server
    """
    # This was created because we were getting test failures caused by the
    # hosted API fixture using a different DB than the bare DB operations
    # in tests.
    # TODO: Figure out how to use the `prefect_client` fixture instead for
    # tests/fixtures using this fixture.
    async with PrefectClient(api=app) as client:
        yield client


@pytest.fixture
def sync_prefect_client(
    test_database_connection_url: str,
) -> Generator[SyncPrefectClient, None, None]:
    yield get_client(sync_client=True)


@pytest.fixture
async def cloud_client(
    prefect_client: PrefectClient,
) -> AsyncGenerator[PrefectClient, None]:
    async with PrefectClient(PREFECT_CLOUD_API_URL.value()) as cloud_client:
        yield cloud_client


@pytest.fixture(scope="session")
def flow_function():
    @flow(version="test", description="A test function")
    def client_test_flow(param: int = 1) -> int:
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
        _logo_url = HttpUrl("https://en.wiktionary.org/wiki/File:LetterX.svg")
        _documentation_url = HttpUrl("https://en.wiktionary.org/wiki/X")
        foo: str

    return x

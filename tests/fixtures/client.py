import pytest

from prefect import flow
from prefect.blocks.core import Block
from prefect.client.orion import get_client


@pytest.fixture
async def orion_client(test_database_connection_url):
    async with get_client() as client:
        yield client


@pytest.fixture(scope="session")
def flow_function():
    @flow(version="test", description="A test function")
    def client_test_flow(param=1):
        return param

    return client_test_flow


@pytest.fixture(scope="module")
def test_block():
    class x(Block):
        _block_type_slug = "x-fixture"
        _logo_url = "https://en.wiktionary.org/wiki/File:LetterX.svg"
        _documentation_url = "https://en.wiktionary.org/wiki/X"
        foo: str

    return x

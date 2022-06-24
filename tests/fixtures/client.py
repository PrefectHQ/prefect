import pytest

from prefect import flow
from prefect.blocks.core import Block
from prefect.client import get_client


@pytest.fixture
async def orion_client(test_database_url):
    async with get_client() as client:
        yield client


@pytest.fixture(scope="module")
def flow_function():
    @flow
    def example_flow(param=1):
        return param

    return example_flow


@pytest.fixture(scope="module")
def test_block():
    class x(Block):
        _logo_url = "https://en.wiktionary.org/wiki/File:LetterX.svg"
        _documentation_url = "https://en.wiktionary.org/wiki/X"
        foo: str

    return x

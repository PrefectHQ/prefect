import pytest

from prefect import flow
from prefect.client import get_client


@pytest.fixture
async def orion_client():
    async with get_client() as client:
        yield client


@pytest.fixture(scope="module")
def flow_function():
    @flow
    def example_flow(param=1):
        return param

    return example_flow

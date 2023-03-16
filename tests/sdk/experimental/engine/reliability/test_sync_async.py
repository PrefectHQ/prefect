import pytest

from prefect import flow
from tests._assets import generic_tasks


@pytest.mark.xfail
def test_async_flow_from_sync_flow():
    @flow
    async def async_run():
        return generic_tasks.noop()

    @flow
    def run():
        async_run()

    run()

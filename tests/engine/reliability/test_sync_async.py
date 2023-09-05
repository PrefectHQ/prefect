from tests import generic_tasks

from prefect import flow


def test_async_flow_from_sync_flow():
    # Regression test for engine reliability work
    # Addressed in https://github.com/PrefectHQ/prefect/pull/8702

    @flow
    async def async_run():
        return generic_tasks.noop()

    @flow
    def run():
        async_run()

    run()

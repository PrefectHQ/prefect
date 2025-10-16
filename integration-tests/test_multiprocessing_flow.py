"""
Regression test for https://github.com/PrefectHQ/prefect/issues/9329#issuecomment-2423021074
"""

import asyncio
import multiprocessing as mp

from prefect import flow, get_client
from prefect.client.schemas.filters import DeploymentFilter, DeploymentFilterTags
from prefect.client.schemas.objects import FlowRun
from prefect.runner.runner import Runner


def read_flow_runs(tags: list[str]) -> list[FlowRun]:
    with get_client(sync_client=True) as client:
        return client.read_flow_runs(
            deployment_filter=DeploymentFilter(tags=DeploymentFilterTags(all_=tags))
        )


def _task(i: int) -> None:
    pass


@flow
def main():
    with mp.Pool(5) as pool:
        pool.map(_task, range(5))


def test_multiprocessing_flow():
    TAGS = ["unique", "integration"]

    runner = Runner()
    runner.add_flow(main, tags=TAGS)
    asyncio.run(runner.start(run_once=True))

    runs = read_flow_runs(TAGS)
    assert len(runs) >= 1
    assert [run.state.is_completed() for run in runs]

    print("Successfully ran a multiprocessing flow")

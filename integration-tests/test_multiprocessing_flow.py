"""
Regression test for https://github.com/PrefectHQ/prefect/issues/9329#issuecomment-2423021074
"""

import asyncio
import multiprocessing as mp
from uuid import UUID

from prefect import flow, get_client
from prefect.client.schemas.filters import DeploymentFilter, DeploymentFilterId
from prefect.client.schemas.objects import FlowRun
from prefect.runner.runner import Runner


def read_flow_runs(deployment_id: UUID) -> list[FlowRun]:
    with get_client(sync_client=True) as client:
        return client.read_flow_runs(
            deployment_filter=DeploymentFilter(
                id=DeploymentFilterId(any_=[deployment_id])
            )
        )


def _task(i: int) -> None:
    pass


@flow
def main():
    with mp.Pool(5) as pool:
        pool.map(_task, range(5))


def test_multiprocessing_flow():
    TAGS = ["unique", "integration"]

    with get_client(sync_client=True) as client:
        runner = Runner()
        deployment_id = runner.add_flow(main, tags=TAGS)
        client.create_flow_run_from_deployment(deployment_id)
        asyncio.run(runner.start(run_once=True))

        runs = client.read_flow_runs(
            deployment_filter=DeploymentFilter(
                id=DeploymentFilterId(any_=[deployment_id])
            )
        )
        assert len(runs) >= 1
        assert [run.state.is_completed() for run in runs]

        print("Successfully ran a multiprocessing flow")

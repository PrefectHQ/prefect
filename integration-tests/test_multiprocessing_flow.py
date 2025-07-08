"""
Regression test for https://github.com/PrefectHQ/prefect/issues/9329#issuecomment-2423021074
"""

import multiprocessing as mp
import signal
from datetime import timedelta

from prefect import flow, get_client
from prefect.client.schemas.filters import DeploymentFilter, DeploymentFilterTags
from prefect.settings import PREFECT_RUNNER_POLL_FREQUENCY, temporary_settings


def read_flow_runs(tags):
    with get_client(sync_client=True) as client:
        return client.read_flow_runs(
            deployment_filter=DeploymentFilter(tags=DeploymentFilterTags(all_=tags))
        )


def _task(i):
    pass


@flow
def main():
    with mp.Pool(5) as pool:
        pool.map(_task, range(5))


def _handler(signum, frame):
    raise KeyboardInterrupt("Simulating user interruption")


def test_multiprocessing_flow():
    TIMEOUT: int = 15
    INTERVAL_SECONDS: int = 3
    TAGS = ["unique", "integration"]

    signal.signal(signal.SIGALRM, _handler)
    signal.alarm(TIMEOUT)

    with temporary_settings({PREFECT_RUNNER_POLL_FREQUENCY: 1}):
        try:
            main.serve(
                name="mp-integration",
                interval=timedelta(seconds=INTERVAL_SECONDS),
                tags=TAGS,
            )
        except KeyboardInterrupt as e:
            print(str(e))
        finally:
            signal.alarm(0)

    runs = read_flow_runs(TAGS)
    assert len(runs) >= 1
    assert [run.state.is_completed() for run in runs]

    print("Successfully ran a multiprocessing flow")

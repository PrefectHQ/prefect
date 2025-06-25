"""
Regression test for https://github.com/PrefectHQ/prefect/issues/9329#issuecomment-2423021074
"""

import multiprocessing as mp
import signal
import time
from datetime import timedelta

from prefect import flow, get_client
from prefect.client.schemas.filters import DeploymentFilter, DeploymentFilterTags
from prefect.settings import PREFECT_RUNNER_POLL_FREQUENCY, temporary_settings


def read_flow_runs(tags):
    with get_client(sync_client=True) as client:
        return client.read_flow_runs(
            deployment_filter=DeploymentFilter(tags=DeploymentFilterTags(all_=tags))
        )


def _init_worker():
    """Initialize worker processes to ignore interrupts"""
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)


def _task(i):
    # Add a small delay to simulate work and avoid race conditions
    time.sleep(0.1)


@flow
def main():
    # Use context manager to ensure pool cleanup
    with mp.Pool(5, initializer=_init_worker) as pool:
        try:
            # Use map_async with timeout for better control
            result = pool.map_async(_task, range(5))
            result.get(timeout=10)  # 10 second timeout for the mapping
        except mp.TimeoutError:
            print("Pool operation timed out, terminating...")
            pool.terminate()
            raise
        except Exception:
            pool.terminate()
            raise
        finally:
            # Ensure pool is properly closed
            pool.close()
            pool.join(timeout=5)


def _handler(signum, frame):
    print(f"Received signal {signum}, shutting down gracefully...")
    raise KeyboardInterrupt("Simulating user interruption")


if __name__ == "__main__":
    TIMEOUT: int = 15
    INTERVAL_SECONDS: int = 3
    TAGS = ["unique", "integration"]

    # Store original handler to restore later
    old_handler = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(TIMEOUT)

    try:
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
                signal.signal(signal.SIGALRM, old_handler)

        runs = read_flow_runs(TAGS)
        assert len(runs) >= 1
        assert [run.state.is_completed() for run in runs]

        print("Successfully ran a multiprocessing flow")

    except Exception as e:
        print(f"Test failed with error: {e}")
        import sys

        sys.exit(1)

import time

from prefect import flow, task
from prefect.futures import wait


@task
def sleep_task(seconds):
    time.sleep(seconds)
    return 42


@flow
def flow():
    futures = sleep_task.map(range(10))
    done, not_done = wait(futures, timeout=5)
    print(f"Done: {len(done)}")
    print(f"Not Done: {len(not_done)}")


if __name__ == "__main__":
    flow()

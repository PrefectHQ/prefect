"""Flows run by the integration tests, baked into the image built from this directory."""

import time

from prefect import flow


@flow(log_prints=True)
def sleepy(n: int = 5) -> None:
    """Sleep for `n` seconds, one second at a time."""
    for i in range(n):
        print(f"Sleeping... {i + 1}/{n}")
        time.sleep(1)

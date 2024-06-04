import os

from prefect import flow, task
from prefect.logging import get_run_logger


@task
def say_hello(name: str):
    get_run_logger().info(f"Hello {name}!")


@flow
def hello(name: str = "world", count: int = 1):
    futures = say_hello.map(f"{name}-{i}" for i in range(count))
    for future in futures:
        future.wait()


if __name__ == "__main__":
    if os.getenv("SERVER_VERSION") == "2.19":
        raise NotImplementedError("This example does not work against 2.19")
    hello(count=3)

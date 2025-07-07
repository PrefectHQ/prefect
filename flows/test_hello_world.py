from prefect import flow
from prefect.logging import get_run_logger


@flow
def hello(name: str = "world"):
    get_run_logger().info(f"Hello {name}!")


def test_hello_world():
    hello()

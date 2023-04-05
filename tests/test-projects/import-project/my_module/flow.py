from prefect import flow

from .utils import get_output


@flow(name="test")
def test_flow():
    return get_output()


@flow(name="test")
def prod_flow():
    return get_output()

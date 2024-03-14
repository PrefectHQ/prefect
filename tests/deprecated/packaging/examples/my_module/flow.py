from prefect import flow

from .utils import get_output


@flow
def test_flow():
    return get_output()

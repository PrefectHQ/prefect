import prefect

from .utils import get_output


@prefect.flow(name="test")
def test_flow():
    return get_output()


@prefect.flow(name="test")
def prod_flow():
    return get_output()

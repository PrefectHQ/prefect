import pytest
from prefect.flow import Flow


def test_create_flow():

    # name is required
    with pytest.raises(TypeError) as e:
        Flow()
    err = "__init__() missing 1 required positional argument: 'name'"
    assert err in str(e)

    # name must be a string
    with pytest.raises(TypeError) as e:
        f = Flow(name=1)
    assert 'Name must be a string' in str(e)

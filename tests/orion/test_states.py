import pytest

from prefect.orion.schemas.states import Completed
from prefect.orion.states import is_state, is_state_iterable


def test_is_state():
    assert is_state(Completed())


def test_is_not_state():
    assert not is_state(None)
    assert not is_state("test")


def test_is_state_requires_instance():
    assert not is_state(Completed)


@pytest.mark.parametrize("iterable_type", [set, list, tuple])
def test_is_state_iterable(iterable_type):
    assert is_state_iterable(iterable_type([Completed(), Completed()]))


def test_is_not_state_iterable_if_unsupported_iterable_type():
    assert not is_state_iterable({Completed(): i for i in range(3)})


@pytest.mark.parametrize("iterable_type", [set, list, tuple])
def test_is_not_state_iterable_if_empty(iterable_type):
    assert not is_state_iterable(iterable_type())

import datetime

import pytest

import prefect
from prefect.context import (
    Annotations,
    Context,
    apply_context_annotations,
    call_with_context_annotations
)

AS_OF_DT = datetime.datetime(2016, 12, 31)
RUN_DT = datetime.datetime(2017, 1, 1)


@pytest.fixture()
def context_dict():
    return dict(
        x=1,
        y=2,
        run_dt=RUN_DT,
        as_of_dt=AS_OF_DT,)


def test_context_as_context_manager():
    """
    Tests that the Context context manager properly sets and removes variables
    """
    with pytest.raises(AttributeError):
        Context.a
    with Context(a=10):
        assert Context.a == 10
    with pytest.raises(AttributeError):
        Context.a


def test_context(context_dict):
    """
    Test accessing Context varaibles
    """
    with Context(context_dict):
        assert Context.x == 1


def test_call_fn_with_context(context_dict):
    """
    Test calling a function inside a context
    """

    def test_fn(x, y):
        return Context.run_dt

    with pytest.raises(AttributeError):
        test_fn(1, 2)

    with Context(context_dict):
        assert test_fn(1, 2) == RUN_DT


def test_call_with_context_annotations(context_dict):
    """
    Test calling function with inserted annotations
    """

    def test_fn(x, y, run_dt: Annotations.run_dt):
        return run_dt

    # annotated variable is missing
    with pytest.raises(TypeError):
        call_with_context_annotations(test_fn, 1, 2)

    # annotated variable is user-supplied
    run_dt_plus1 = RUN_DT + datetime.timedelta(days=1)
    assert call_with_context_annotations(
        test_fn, 1, 2, run_dt_plus1) == run_dt_plus1

    # annotated variable is Context-supplied
    with Context(context_dict):
        assert call_with_context_annotations(test_fn, 1, 2) == RUN_DT

    # annotated variable is in the context but overridden
    with Context(context_dict):
        assert call_with_context_annotations(
            test_fn, 1, 2, run_dt_plus1) == run_dt_plus1


def test_apply_context_annotations(context_dict):
    """
    Test function decorator that inserts annotations at runtime
    """

    @apply_context_annotations
    def test_fn(x, y, run_dt: Annotations.run_dt):
        return run_dt

    # annotated variable is missing
    with pytest.raises(TypeError):
        test_fn(1, 2)

    # annotated variable is user-supplied
    run_dt_plus1 = RUN_DT + datetime.timedelta(days=1)
    assert test_fn(1, 2, run_dt_plus1) == run_dt_plus1

    # annotated variable is Context-supplied
    with Context(context_dict):
        assert test_fn(1, 2) == RUN_DT

    # annotated variable is in the context but overridden
    with Context(context_dict):
        assert test_fn(1, 2, run_dt_plus1) == run_dt_plus1

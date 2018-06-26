
import pytest

from prefect import context
from typing import Any


def test_context_sets_variables_inside_context_manager():
    """
    Tests that the context context manager properly sets and removes variables
    """
    with pytest.raises(AttributeError):
        context.a
    with context(a=10):
        assert context.a == 10
    with pytest.raises(AttributeError):
        context.a


def test_setting_context_with_keywords():
    """
    Test accessing context varaibles
    """
    with context(x=1):
        assert context.x == 1


def test_setting_context_with_dict():
    """
    Test accessing context varaibles
    """
    with context(dict(x=1)):
        assert context.x == 1


def test_call_function_inside_context_can_access_context():
    """
    Test calling a function inside a context
    """

    def test_fn() -> Any:
        return context.x

    with pytest.raises(AttributeError):
        test_fn()

    with context(x=1):
        assert test_fn() == 1


def test_nested_contexts_properly_restore_parent_context_when_closed():
    # issue https://gitlab.com/prefect/prefect/issues/16
    with context(a=1):
        assert context.a == 1
        with context(a=2):
            assert context.a == 2
        assert context.a == 1


def test_context_setdefault_method():
    assert "a" not in context
    assert context.setdefault("a", 5) == 5
    assert "a" in context
    assert context.setdefault("a", 10) == 5

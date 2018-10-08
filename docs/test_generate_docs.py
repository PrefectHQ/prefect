import pytest
from functools import wraps
from toolz import curry

from generate_docs import create_absolute_path, format_signature, format_subheader
from prefect import task
from prefect.engine.state import State


def no_args():
    pass


def one_arg(x):
    pass


def one_string_kwarg(k="key"):
    pass


def standard_sig(x, y, k="key", q=None, b=True):
    pass


def varargs_no_default(*args, iso, **kwargs):
    pass


def varargs_with_default(*args, iso=None, **kwargs):
    pass


class A:
    """
    A class called "A".

    Args:
        - attr (str): meaningless
        - keep (bool, optional): whatever, defaults to `True`

    Raises:
        - TypeError: if you don't provide `attr`
    """

    def __init__(self, attr, keep=True):
        pass

    def run(self, *args, b=True, **kwargs):
        pass

    def y(self, *args, b, **kwargs):
        pass


@pytest.mark.parametrize(
    "obj,exp",
    [
        (no_args, ""),
        (one_arg, "x"),
        (one_string_kwarg, 'k="key"'),
        (standard_sig, 'x, y, k="key", q=None, b=True'),
        (varargs_with_default, "*args, iso=None, **kwargs"),
        (varargs_no_default, "*args, iso, **kwargs"),
        (A, "attr, keep=True"),
        (A.run, "*args, b=True, **kwargs"),
        (A.y, "*args, b, **kwargs"),
    ],
)
def test_format_signature(obj, exp):
    assert format_signature(obj) == exp


@pytest.mark.parametrize(
    "obj,exp",
    [
        (no_args, ""),
        (one_arg, "x"),
        (one_string_kwarg, 'k="key"'),
        (standard_sig, 'x, y, k="key", q=None, b=True'),
        (varargs_with_default, "*args, iso=None, **kwargs"),
        (varargs_no_default, "*args, iso, **kwargs"),
        (A.run, "*args, b=True, **kwargs"),
        (A.y, "*args, b, **kwargs"),
    ],
)
def test_format_signature_with_curry(obj, exp):
    assert format_signature(curry(obj)) == exp


@pytest.mark.parametrize(
    "obj,exp",
    [
        (no_args, ""),
        (one_arg, "x"),
        (one_string_kwarg, 'k="key"'),
        (standard_sig, 'x, y, k="key", q=None, b=True'),
        (varargs_with_default, "*args, iso=None, **kwargs"),
        (varargs_no_default, "*args, iso, **kwargs"),
        (A.run, "*args, b=True, **kwargs"),
        (A.y, "*args, b, **kwargs"),
    ],
)
def test_format_signature_with_wraps(obj, exp):
    @wraps(obj)
    def new_func(*args, **kwargs):
        return obj(*args, **kwargs)

    assert format_signature(new_func) == exp


@pytest.mark.parametrize(
    "obj,exp",
    [(task, "prefect.utilities.tasks.task"), (State, "prefect.engine.state.State")],
)
def test_create_absolute_path_on_prefect_object(obj, exp):
    path = create_absolute_path(obj)
    assert path == exp


@pytest.mark.parametrize("obj,exp", [(A, "A"), (A.run, "A.run"), (no_args, "no_args")])
def test_create_absolute_path_on_nonprefect_object(obj, exp):
    path = create_absolute_path(obj)
    assert path == exp

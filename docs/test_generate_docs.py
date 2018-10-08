import pytest
from functools import partial, wraps
from toolz import curry

from generate_docs import (
    create_absolute_path,
    format_doc,
    format_lists,
    format_signature,
    format_subheader,
    get_source,
)
from prefect import task
from prefect.engine.state import State
from prefect.utilities.json import dumps, loads


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
    [(one_string_kwarg, "k=42"), (standard_sig, "x, y, k=42, q=None, b=True")],
)
def test_format_signature_with_partial(obj, exp):
    new_func = partial(obj, k=42)
    assert format_signature(new_func) == exp


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


@pytest.mark.parametrize("obj", [dumps, loads])
def test_format_subheader_doesnt_raise_on_json_utils(obj):
    doc = format_subheader(obj)


def test_format_subheader_on_class():
    doc = format_subheader(A)
    assert doc == (
        "  <div class='sig' style='padding-left:3.5em;text-indent:-3.5em;'>"
        '<em><b>class </b></em><b>A</b>(attr, keep=True)<span style="text-align:right;'
        ' float:right; font-size:0.8em; width: 50%; max-width: 6em; display: inline-block;">[source]</span></div>\n\n'
    )


def test_format_list_on_normal_doc():
    doc = """
    Does a thing.

    Args:
        - x (bool): it's x
        - y (bool): it's y

    Returns:
        - whatever you want

    Raises:
        - NotImplementedError: because it doesnt exist
    """
    formatted_doc = format_lists(doc)
    assert formatted_doc == (
        "\n    Does a thing.\n\n    Args:\n        "
        "<ul style='padding-left:3.5em;text-indent:-3.5em;'>"
        "<li style='padding-left:3.5em;text-indent:-3.5em;'>"
        "`x (bool)`: it's x\n        </li>"
        "<li style='padding-left:3.5em;text-indent:-3.5em;'>"
        "`y (bool)`: it's y</li></ul>    "
        "Returns:\n        <ul style='padding-left:3.5em;text-indent:-3.5em;'>"
        "<li style='padding-left:3.5em;text-indent:-3.5em;'>whatever you want</li></ul>"
        "\n\n    Raises:\n        <ul style='padding-left:3.5em;text-indent:-3.5em;'>"
        "<li style='padding-left:3.5em;text-indent:-3.5em;'>`NotImplementedError`: because it doesnt exist\n    </li></ul>"
    )


def test_format_doc_on_simple_doc():
    def my_fun():
        """
        Indicates that a task should not run and wait for manual execution.

        Args:
            - message (Any, optional): Defaults to `None`. A message about the signal.
        """
        pass

    formatted = format_doc(my_fun)
    assert formatted == (
        "Indicates that a task should not run and wait for manual execution.\n\n"
        "**Args**:\n<ul style='padding-left:3.5em;text-indent:-3.5em;'>"
        "<li style='padding-left:3.5em;text-indent:-3.5em;'>"
        "`message (Any, optional)`: Defaults to `None`. A message about the signal.</li></ul>"
    )

import pytest
import sys

pytest.mark.skipif(sys.version_info < (3, 6))

from functools import partial, wraps
from toolz import curry

from generate_docs import (
    create_absolute_path,
    format_doc,
    format_lists,
    format_signature,
    format_subheader,
    get_call_signature,
    get_class_methods,
    get_source,
    OUTLINE,
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

    @classmethod
    def from_nothing(cls, stuff=None):
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
        (A.from_nothing, "stuff=None"),
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


@pytest.mark.parametrize(
    "fn", [fn for page in OUTLINE for fn in page.get("functions", [])]
)
def test_consistency_of_function_docs(fn):
    standalone, varargs, kwonly, kwargs, varkwargs = get_call_signature(fn)
    doc = format_doc(fn)
    try:
        arg_list_index = doc.index("**Args**:")
        end = doc[arg_list_index:].find("</ul")
        arg_doc = doc[arg_list_index : (arg_list_index + end)]
        num_args = arg_doc.count("<li")
    except ValueError:
        num_args = 0

    assert num_args == len(standalone) + len(varargs) + len(kwonly) + len(kwargs) + len(
        varkwargs
    ), "{fn.__name__} has undocumented arguments.".format(fn=fn)


@pytest.mark.parametrize(
    "obj,fn",
    [
        (obj, fn)
        for page in OUTLINE
        for obj in page.get("classes", [])
        for fn in get_class_methods(obj)
    ],
)  # parametrized like this for easy reading of tests
def test_consistency_of_class_method_docs(obj, fn):
    standalone, varargs, kwonly, kwargs, varkwargs = get_call_signature(fn)
    doc = format_doc(fn)
    try:
        arg_list_index = doc.index("**Args**:")
        end = doc[arg_list_index:].find("</ul")
        arg_doc = doc[arg_list_index : (arg_list_index + end)]
        num_args = arg_doc.count("<li")
    except ValueError:
        num_args = 0

    assert num_args == len(standalone) + len(varargs) + len(kwonly) + len(kwargs) + len(
        varkwargs
    ), "{obj.__module__}.{obj.__name__}.{fn.__name__} has undocumented arguments.".format(
        obj=obj, fn=fn
    )


def test_format_doc_removes_unnecessary_newlines_when_appropriate_in_tables():
    def doc_fun():
        """
        I am a
        poorly formatte
        d doc string.

        Args:
            - x (optional): actually not
                really here

        I talk too much.

        Raises:
            - TypeError: why not

        Example:
            ```python
            ## TODO:
            ## put some
            ## code here
            ```
        """
        pass

    res = format_doc(doc_fun, in_table=True)
    sub_string = "<sub>I am a poorly formatte d doc string.<br><br>**Args**:"
    assert sub_string in res
    assert "<br>**Raises**:" in res


def test_format_doc_correctly_handles_code_blocks_outside_of_tables():
    def doc_fun():
        """
        A `dict` that also supports attribute ("dot") access. Think of this as an extension
        to the standard python `dict` object.

        Args:
            - init_dict (dict, optional): dictionary to initialize the `DotDict`
            with
            - **kwargs (optional): key, value pairs with which to initialize the
            `DotDict`

        **Example**:
            ```python
            dotdict = DotDict({'a': 34}, b=56, c=set())
            dotdict.a # 34
            dotdict['b'] # 56
            dotdict.c # set()
            ```
        """
        pass

    res = format_doc(doc_fun)
    sub_string = (
        "**Example**:     \n```python\n    dotdict = DotDict({'a': 34},"
        " b=56, c=set())\n    dotdict.a # 34\n    dotdict['b'] # 56\n    dotdict.c # set()\n\n```"
    )
    assert sub_string in res


@pytest.mark.parametrize(
    "fn", [fn for page in OUTLINE for fn in page.get("functions", [])]
)
def test_sections_have_formatted_headers_for_function_docs(fn):
    doc = format_doc(fn)
    for section in ["Args", "Returns", "Raises", "Example"]:
        option1 = ">**{}**:".format(section)
        option2 = "\n**{}**:".format(section)
        assert (section in doc) is any(
            [(o in doc) for o in (option1, option2)]
        ), "{fn.__name__} has a poorly formatted {sec} header.".format(
            fn=fn, sec=section
        )


@pytest.mark.parametrize(
    "obj,fn",
    [
        (obj, fn)
        for page in OUTLINE
        for obj in page.get("classes", [])
        for fn in get_class_methods(obj)
    ],
)  # parametrized like this for easy reading of tests
def test_consistency_of_class_method_docs(obj, fn):
    doc = format_doc(fn)
    for section in ["Args", "Returns", "Raises", "Example"]:
        option1 = ">**{}**:".format(section)
        option2 = "\n**{}**:".format(section)
        assert (section in doc) is any(
            [(o in doc) for o in (option1, option2)]
        ), "{obj.__module__}.{obj.__name__}.{fn.__name__} has a poorly formatted {sec} header.".format(
            obj=obj, fn=fn, sec=section
        )

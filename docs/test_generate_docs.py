import glob
import inspect
import os
import re
import sys
import textwrap
from functools import partial, wraps
from unittest.mock import MagicMock

import pytest
from toolz import curry

from prefect import Task, task
from prefect.engine.state import State
from prefect.utilities.tasks import defaults_from_attrs

try:
    from generate_docs import (
        load_outline,
        create_absolute_path,
        format_code,
        format_doc,
        format_lists,
        format_signature,
        format_subheader,
        get_call_signature,
        get_class_methods,
        patch_imports,
        build_example,
        VALID_DOCSTRING_SECTIONS,
    )

    with patch_imports():
        OUTLINE = load_outline()
except ImportError:
    pytestmark = pytest.skip(
        "Documentation requirements not installed.", allow_module_level=True
    )


pytest.mark.skipif(sys.version_info < (3, 6))

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def consistency_check(obj, obj_name):
    patt = re.compile(r"(?<=>`)(.*?)(?=[\(|`:])")
    doc = format_doc(obj)
    try:
        arg_list_index = doc.index("**Args**:")
        end = doc[arg_list_index:].find("</ul")
        arg_doc = doc[arg_list_index : (arg_list_index + end)]
        doc_args = {arg.strip() for arg in patt.findall(arg_doc)}
    except ValueError:
        doc_args = set()

    items = get_call_signature(obj)
    actual_args = {(a if isinstance(a, str) else a[0]) for a in items}

    undocumented = actual_args.difference(doc_args)
    # If the sig contains **kwargs, any keyword is valid
    if any(k.startswith("**") for k in actual_args):
        non_existent = {}
    else:
        non_existent = doc_args.difference(actual_args)

    if undocumented:
        undoc_args = ", ".join(undocumented)
        raise ValueError(
            f"{obj_name} has arguments without documentation: {undoc_args}"
        )
    elif non_existent:
        undoc_args = ", ".join(non_existent)
        raise ValueError(
            f"{obj_name} has documentation for arguments that aren't real: {undoc_args}"
        )


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


class CustomException(Exception):
    """
    Docstring.

    Args:
        - x (Any, optional): Just a placeholder
    """

    def __init__(self, x):
        self.x = x
        super().__init__()


class NamedException(Exception):
    """
    Just a name, nothing more.
    """


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


class MyTask(Task):
    @defaults_from_attrs("y", "z")
    def run(self, x, y=None, z=None):
        return x, y, z


code = """
from prefect import task, Task, Flow
import random

@task
def random_number():
    return random.randint(0, 100)

@task
def plus_one(x):
    return x + 1

with Flow('My Functional Flow') as flow:
    r = random_number()
    y = plus_one(x=r)
"""


def test_tokenizer():
    tokenized = format_code(code)
    assert '<span class="token decorator">@task</span>' in tokenized


@pytest.mark.parametrize(
    "obj,exp",
    [
        (no_args, ""),
        (one_arg, "x"),
        (one_string_kwarg, "k=&quot;key&quot;"),
        (standard_sig, "x, y, k=&quot;key&quot;, q=None, b=True"),
        (varargs_with_default, "*args, iso=None, **kwargs"),
        (varargs_no_default, "*args, iso, **kwargs"),
        (A, "attr, keep=True"),
        (A.run, "*args, b=True, **kwargs"),
        (A.y, "*args, b, **kwargs"),
        (A.from_nothing, "stuff=None"),
        (CustomException, "x"),
        (NamedException, "*args, **kwargs"),
        (MyTask.run, "x, y=None, z=None"),
    ],
)
def test_format_signature(obj, exp):
    assert format_signature(obj) == exp


@pytest.mark.parametrize(
    "obj,exp",
    [
        (no_args, ""),
        (one_arg, "x"),
        (one_string_kwarg, "k=&quot;key&quot;"),
        (standard_sig, "x, y, k=&quot;key&quot;, q=None, b=True"),
        (varargs_with_default, "*args, iso=None, **kwargs"),
        (varargs_no_default, "*args, iso, **kwargs"),
        (A.run, "*args, b=True, **kwargs"),
        (A.y, "*args, b, **kwargs"),
        (MyTask.run, "x, y=None, z=None"),
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
        (one_string_kwarg, "k=&quot;key&quot;"),
        (standard_sig, "x, y, k=&quot;key&quot;, q=None, b=True"),
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


def test_format_subheader_on_class():
    doc = format_subheader(A)
    assert doc == (
        " ## A\n"
        " <div class='class-sig' id='a'>"
        '<p class="prefect-sig">class </p><p class="prefect-class">A</p>(attr, keep=True)<span class="source">[source]</span></div>\n\n'
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

    References:
        - Example: https://example.com
    """
    formatted_doc = format_lists(doc)
    assert formatted_doc == (
        "\n    Does a thing.\n\n    Args:\n        "
        '<ul class="args">'
        '<li class="args">'
        "`x (bool)`: it's x\n        </li>"
        '<li class="args">'
        "`y (bool)`: it's y</li></ul>\n    "
        'Returns:\n        <ul class="args">'
        '<li class="args">whatever you want</li></ul>'
        '\n\n    Raises:\n        <ul class="args">'
        '<li class="args">`NotImplementedError`: because it doesnt exist</li></ul>\n    '
        'References:\n        <ul class="args">'
        '<li class="args">`Example`: https://example.com\n    </li></ul>'
        ""
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
        '**Args**:     <ul class="args">'
        '<li class="args">'
        "`message (Any, optional)`: Defaults to `None`. A message about the signal.</li></ul>"
    )


def test_format_doc_on_subclass_with_doc_but_inherited_init():
    class Parent:
        """
        This is the parent doc

        Args:
            - x (int): a number
        """

        def __init__(self, x: int):
            pass

        def fn(self):
            pass

    class Child(Parent):
        """
        This is the child doc
        """

        def fn(self):
            pass

    doc = format_doc(Child)
    expected = textwrap.dedent(
        """
        This is the child doc
        """
    ).strip()

    assert doc == expected


def test_format_doc_on_raw_exception():
    formatted = format_doc(NamedException)
    expected = textwrap.dedent(
        """
        Just a name, nothing more.
        """
    ).strip()
    assert formatted == expected


@pytest.mark.parametrize(
    "fn", [fn for page in OUTLINE for fn in page.get("functions", [])]
)
def test_consistency_of_function_docs(fn):
    consistency_check(fn, f"{fn.__name__}")


@pytest.mark.parametrize(
    "obj", [obj for page in OUTLINE for obj, _ in page.get("classes", [])]
)
def test_consistency_of_class_docs(obj):
    if isinstance(obj, MagicMock):
        pytest.skip("Mocked classes from optional requirements cannot be checked")
    consistency_check(obj, f"{obj.__module__}.{obj.__name__}")


@pytest.mark.parametrize(
    "obj,fn",
    [
        (obj, fn)
        for page in OUTLINE
        for obj, methods in page.get("classes", [])
        for fn in get_class_methods(obj, methods)
    ],
)  # parametrized like this for easy reading of tests
def test_consistency_of_class_method_docs(obj, fn):
    consistency_check(fn, f"{obj.__module__}.{obj.__name__}.{fn.__name__}")


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
    sub_string = (
        '<p class="methods">I am a poorly formatte d doc string.<br><br>**Args**:'
    )
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


def test_format_doc_escapes_asteriks_inside_tables():
    def my_doc():
        """
        See:
            ```python
            my_doc(**kwargs)
            ```
        """
        pass

    res = format_doc(my_doc, in_table=True)
    assert res.count(r">\*<") == 2


all_objects = []
for page in OUTLINE:
    all_objects.extend(page.get("functions", []))
    for cls, methods in page.get("classes"):
        all_objects.append(cls)
        all_objects.extend(get_class_methods(cls, methods))


@pytest.mark.parametrize("obj", all_objects)
def test_section_headers_are_properly_formatted(obj):
    doc = inspect.getdoc(obj)
    if not doc:
        return
    for section in VALID_DOCSTRING_SECTIONS:
        if re.search(f"^\\s*{section}\\s*$", doc, flags=re.M):
            assert (
                False
            ), f"{obj.__module__}.{obj.__qualname__} has a poorly formatted '{section}' header"


@pytest.mark.parametrize("path", glob.glob(os.path.join(ROOT, "examples", "*.py")))
def test_example(path):
    build_example(path)

"""
Functionality for auto-generating markdown documentation.

Each entry in `OUTLINE` is a dictionary with the following key/value pairs:
    - "page" -> (str): relative path to the markdown file this page represents
    - "classes" -> (list, optional): list of classes to document
    - "functions" -> (list, optional): list of standalone functions to document
    - "title" -> (str, optional): title of page
    - "top-level-doc" -> (object, optional): module object which contains the
        docstring which will be displayed at the top of the generated page

On a development installation of Prefect, simply run `python generate_docs.py` from inside the `docs/` folder.
"""
import builtins
import importlib
import inspect
import os
import re
import shutil
import subprocess
import textwrap
import warnings
from contextlib import contextmanager
from functools import partial
from unittest.mock import MagicMock

import pendulum
import toml
import toolz
from slugify import slugify

import prefect
from tokenizer import format_code

OUTLINE_PATH = os.path.join(os.path.dirname(__file__), "outline.toml")
outline_config = toml.load(OUTLINE_PATH)


@contextmanager
def patch_imports():
    try:

        def patched_import(*args, **kwargs):
            try:
                return real_import(*args, **kwargs)
            except Exception:
                return MagicMock(name=args[0])

        # swap
        real_import, builtins.__import__ = builtins.__import__, patched_import
        yield
    finally:
        builtins.__import__ = real_import


def load_outline(
    outline=outline_config["pages"],
    ext=outline_config.get("extension", ".md"),
    prefix=None,
):
    OUTLINE = []
    for name, data in outline.items():
        fname = os.path.join(prefix or "", name)
        if "module" in data:
            page = {}
            page.update(
                page=f"{fname}{ext}",
                title=data.get("title", ""),
                classes=[],
                functions=[],
            )
            module = importlib.import_module(data["module"])
            page["top-level-doc"] = module
            for fun in data.get("functions", []):
                page["functions"].append(getattr(module, fun))
            for clss in data.get("classes", []):
                page["classes"].append(getattr(module, clss))
            OUTLINE.append(page)
        else:
            OUTLINE.extend(load_outline(data, prefix=fname))
    return OUTLINE


@toolz.curry
def preprocess(f, remove_partial=True):
    def wrapped(*args, **kwargs):
        new_obj = getattr(args[0], "__wrapped__", args[0])
        if not isinstance(new_obj, partial):
            new_obj = getattr(new_obj, "func", new_obj)
        elif isinstance(new_obj, partial) and remove_partial:
            # because partial sets kwargs in the signature, we dont always
            # want that stripped for call signature inspection but we _do_
            # for doc inspection
            new_obj = getattr(new_obj, "func", new_obj)
        new_args = list(args)
        new_args[0] = new_obj
        if getattr(new_obj, "__wrapped__", None):
            return wrapped(*new_args, **kwargs)
        return f(*new_args, **kwargs)

    return wrapped


def clean_line(line):
    line = (
        line.replace("Args:", "**Args**:")
        .replace("Returns:", "**Returns**:")
        .replace("Raises:", "**Raises**:")
        .replace("Example:", "**Example**:")
        .replace(".**", ".\n\n**")
    )
    return line.lstrip()


def format_lists(doc):
    "Convenience function for converting markdown lists to HTML for within-table lists"
    lists = re.findall(
        r"(Args\:|Returns\:|Raises\:)(.*?)\s+(-.*?)(\n\n|$)", doc, re.DOTALL
    )  # find formatted lists
    ul_tag = '<ul class="args">'
    li_tag = '<li class="args">'
    for section, _, items, ending in lists:
        if section.startswith(("Returns:", "Raises:")) and ":" not in items:
            doc = doc.replace(
                items, f"{ul_tag}{li_tag}" + items.lstrip("- ") + "</li></ul>", 1
            )
            continue
        args = re.split(r"-\s+(.*?)\:(?![^{]*\})", items)  # collect all list items
        if not args:
            continue
        block = ""
        list_items = zip(args[1::2], args[2::2])
        for item, descr in list_items:
            block += f"{li_tag}`{item}`:{descr}</li>"
        list_block = f"{ul_tag}{block}</ul>"
        doc = doc.replace(items + "\n\n", list_block, 1).replace(items, list_block, 1)
    return doc.replace("\n\nRaises:", "Raises:")


@preprocess
def format_doc(obj, in_table=False):
    doc = inspect.getdoc(obj)
    body = doc or ""
    code_blocks = re.findall(r"```(.*?)```", body, re.DOTALL)
    for num, block in enumerate(code_blocks):
        body = body.replace(block, f"$CODEBLOCK{num}", 1)
    body = re.sub(
        "(?<!\n)\n{1}(?!\n)", " ", format_lists(body)
    )  # removes poorly placed newlines
    body = body.replace("```", "\n```")
    lines = body.split("\n")
    cleaned = "\n".join([clean_line(line) for line in lines])
    if in_table:
        cleaned = cleaned.replace("\n", "<br>").replace("```", "")
    for num, block in enumerate(code_blocks):
        if in_table:
            block = block[block.startswith("python") and 6 :].lstrip("\n")
            block = (
                '<pre class="language-python"><code class="language-python">'
                + format_code(block).replace("\n", "<br>").replace("*", r"\*")
                + "</code></pre>"
            )
        cleaned = cleaned.replace(f"$CODEBLOCK{num}", block.rstrip(" "))
    if in_table:
        return f'<p class="methods">{cleaned}</p>'
    else:
        return cleaned


def create_methods_table(members, title):
    table = ""
    if members:
        table = f"|{title} " + "&nbsp;" * 150 + "|\n"
        table += "|:----|\n"
    for method in members:
        table += format_subheader(method, level=2, in_table=True).replace("\n\n", "\n")
        table += format_doc(method, in_table=True)
        table += "|\n"
    return table


@preprocess(remove_partial=False)
def get_call_signature(obj):
    assert callable(obj), f"{obj} is not callable, cannot format signature."
    # collect data
    try:
        sig = inspect.getfullargspec(obj)
    except TypeError:  # if obj is exception
        sig = inspect.getfullargspec(obj.__init__)
    args, defaults = sig.args, sig.defaults or []
    kwonly, kwonlydefaults = sig.kwonlyargs or [], sig.kwonlydefaults or {}
    varargs, varkwargs = sig.varargs, sig.varkw

    if args == []:
        standalone, kwargs = [], []
    else:
        if args[0] in ["cls", "self"]:
            args = args[1:]  # remove cls or self from displayed signature

        standalone = args[: -len(defaults)] if defaults else args  # true args
        kwargs = list(zip(args[-len(defaults) :], defaults))  # true kwargs

    varargs = [f"*{varargs}"] if varargs else []
    varkwargs = [f"**{varkwargs}"] if varkwargs else []
    if kwonly:
        kwargs.extend([(kw, default) for kw, default in kwonlydefaults.items()])
        kwonly = [k for k in kwonly if k not in kwonlydefaults]

    return standalone, varargs, kwonly, kwargs, varkwargs


@preprocess(remove_partial=False)
def format_signature(obj):
    standalone, varargs, kwonly, kwargs, varkwargs = get_call_signature(obj)
    add_quotes = lambda s: f'"{s}"' if isinstance(s, str) else s
    psig = ", ".join(
        standalone
        + varargs
        + kwonly
        + [f"{name}={add_quotes(val)}" for name, val in kwargs]
        + varkwargs
    )
    return psig


@preprocess
def create_absolute_path(obj):
    dir_struct = inspect.getfile(obj).split("/")
    if ("prefect" not in dir_struct) or ("test_generate_docs.py" in dir_struct):
        return obj.__qualname__
    first_dir, offset = ("src", 1) if "src" in dir_struct else ("prefect", 0)
    begins_at = dir_struct.index(first_dir) + offset
    filename = dir_struct.pop(-1)
    dir_struct.append(filename[:-3] if filename.endswith(".py") else filename)
    path = ".".join([d for d in dir_struct[begins_at:]])
    return f"{path}.{obj.__qualname__}"


@preprocess
def get_source(obj):
    commit = os.getenv("GIT_SHA", "master")
    base_url = "https://github.com/PrefectHQ/prefect/blob/{}/src/prefect/".format(
        commit
    )
    dir_struct = inspect.getfile(obj).split("/")
    if "src" not in dir_struct:
        link = "[source]"  # dead-link
    else:
        begins_at = dir_struct.index("src") + 2
        line_no = inspect.getsourcelines(obj)[1]
        url_ending = "/".join(dir_struct[begins_at:]) + f"#L{line_no}"
        link = f'<a href="{base_url}{url_ending}">[source]</a>'
    source_tag = f'<span class="source">{link}</span>'
    return source_tag


@preprocess(remove_partial=False)
def format_subheader(obj, level=1, in_table=False):
    class_sig = format_signature(obj)
    if inspect.isclass(obj):
        header = "## {}\n".format(obj.__name__)
    elif not in_table:
        header = "##" + "#" * level
    else:
        header = "|"
    is_class = '<p class="prefect-sig">class </p>' if inspect.isclass(obj) else ""
    class_name = f'<p class="prefect-class">{create_absolute_path(obj)}</p>'
    div_class = "class-sig" if is_class else "method-sig"
    div_tag = f"<div class='{div_class}' id='{slugify(create_absolute_path(obj))}'>"

    call_sig = f" {header} {div_tag}{is_class}{class_name}({class_sig}){get_source(obj)}</div>\n\n"
    return call_sig


def get_class_methods(obj):
    members = inspect.getmembers(
        obj, predicate=lambda x: inspect.isroutine(x) and obj.__name__ in x.__qualname__
    )
    public_members = [method for (name, method) in members if not name.startswith("_")]
    return public_members


def create_tutorial_notebooks(tutorial):
    """
    Utility which automagically creates an .ipynb notebook file from a markdown file consisting
    of all python code blocks contained within the markdown file.

    Args:
        - tutorial (str): path to tutorial markdown file

    Will save the resulting notebook in tutorials/notebooks under the same name as the .md file provided.
    """
    assert (
        os.path.basename(os.getcwd()) == "docs"
    ), "Only run this utility from inside the docs/ directory!"

    import nbformat as nbf

    os.makedirs(".vuepress/public/notebooks", exist_ok=True)
    text = open(tutorial, "r").read()
    code_blocks = re.findall(r"```(.*?)```", text, re.DOTALL)
    nb = nbf.v4.new_notebook()
    nb["cells"] = []
    for code in code_blocks:
        if not code.startswith("python"):
            continue
        code = code[7:]
        nb["cells"].append(nbf.v4.new_code_cell(code))
    fname = os.path.basename(tutorial).split(".md")[0] + ".ipynb"
    nbf.write(nb, f".vuepress/public/notebooks/{fname}")


if __name__ == "__main__":

    with patch_imports():
        OUTLINE = load_outline()
        assert (
            os.path.basename(os.getcwd()) == "docs"
        ), "Only run this script from inside the docs/ directory!"

        GIT_SHA = os.getenv("GIT_SHA", "n/a")
        SHORT_SHA = GIT_SHA[:7]
        auto_generated_footer = (
            '<p class="auto-gen">This documentation was auto-generated from commit '
            "<a href='https://github.com/PrefectHQ/prefect/commit/{git_sha}'>{short_sha}</a> "
            "</br>by Prefect {version} on {timestamp}</p>".format(
                short_sha=SHORT_SHA,
                git_sha=GIT_SHA,
                version=prefect.__version__,
                timestamp=pendulum.now("utc").format("MMMM D, YYYY [at] HH:mm [UTC]"),
            )
        )

        front_matter = textwrap.dedent(
            """
            ---
            sidebarDepth: 2
            editLink: false
            ---
            """
        ).lstrip()

        shutil.rmtree("api/unreleased", ignore_errors=True)
        os.makedirs("api/unreleased", exist_ok=True)

        ## write link to hosted coverage reports
        with open("api/unreleased/coverage.md", "w+") as f:
            f.write(
                textwrap.dedent(
                    """
                ---
                title: Test Coverage
                ---

                # Unit test coverage report

                To view test coverage reports, <a href="https://codecov.io/gh/PrefectHQ/prefect">click here</a>.
                """
                ).lstrip()
            )

        ## UPDATE README
        with open("api/unreleased/README.md", "w+") as f:
            f.write(
                textwrap.dedent(
                    """
                ---
                sidebarDepth: 0
                editLink: false
                ---
                """
                ).lstrip()
            )

            api_reference_section = textwrap.dedent(
                """

                <div align="center" style="margin-bottom:40px;">
                <img src="/assets/wordmark-color-horizontal.svg"  width=600 >
                </div>

                # API Reference

                This API reference is automatically generated from Prefect's source code and unit-tested to ensure it's up to date.

                """
            )

            with open("../README.md", "r") as g:
                readme = g.read()
                index = readme.index("## Hello, world!")
                readme = "\n".join([api_reference_section, readme[index:]])
                f.write(readme)
                f.write(auto_generated_footer)

        ## UPDATE CHANGELOG
        with open("api/unreleased/changelog.md", "w+") as f:
            f.write(
                textwrap.dedent(
                    """
                ---
                sidebarDepth: 1
                editLink: false
                ---
                """
                ).lstrip()
            )
            with open("../CHANGELOG.md", "r") as g:
                changelog = g.read()
                f.write(changelog)
                f.write(auto_generated_footer)

        for page in OUTLINE:
            # collect what to document
            fname, classes, fns = (
                page["page"],
                page.get("classes", []),
                page.get("functions", []),
            )
            fname = f"api/unreleased/{fname}"
            directory = os.path.dirname(fname)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(fname, "w") as f:
                # PAGE TITLE / SETUP
                f.write(front_matter)
                title = page.get("title")
                if title:  # this would be a good place to have assignments
                    f.write(f"# {title}\n---\n")

                top_doc_obj = page.get("top-level-doc")
                if top_doc_obj is not None:
                    top_doc = inspect.getdoc(top_doc_obj)
                    if top_doc is not None:
                        f.write(top_doc + "\n")
                for obj in classes:
                    f.write(format_subheader(obj))

                    f.write(format_doc(obj) + "\n\n")
                    if type(obj) == toolz.functoolz.curry:
                        f.write("\n")
                        continue

                    public_members = get_class_methods(obj)
                    f.write(create_methods_table(public_members, title="methods:"))
                    f.write("\n---\n<br>\n\n")

                if fns:
                    f.write("\n## Functions\n")
                f.write(create_methods_table(fns, title="top-level functions:"))
                f.write("\n")
                f.write(auto_generated_footer)

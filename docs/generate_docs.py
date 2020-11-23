"""
Functionality for auto-generating markdown documentation.

Each entry in `OUTLINE` is a dictionary with the following key/value pairs:
    - "page" -> (str): relative path to the markdown file this page represents
    - "classes" -> (list, optional): list of classes to document
    - "functions" -> (list, optional): list of standalone functions to document
    - "title" -> (str, optional): title of page
    - "top-level-doc" -> (object, optional): module object that contains the
        docstring that will be displayed at the top of the generated page
    - "experimental" -> (bool = False, optional): whether or not to display the "Experimental" flag at the top of the page

On a development installation of Prefect, run `python generate_docs.py` from inside the `docs/` folder.
"""
import builtins
import importlib
import inspect
import os
import re
import shutil
import textwrap
from contextlib import contextmanager
from functools import partial
from unittest.mock import MagicMock

import pendulum
import toml
import toolz
from slugify import slugify

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
                commands=[],
                experimental=data.get("experimental", False),
            )
            module = importlib.import_module(data["module"])
            page["top-level-doc"] = module

            # extract documented function objects
            # note that if one is listed as an attribute of a submodule
            # we attempt to import the submodule and extract the function there
            for fun in data.get("functions", []):
                if "." in fun:
                    parts = fun.split(".")
                    submod = ".".join([module.__name__, parts[0]])
                    module = importlib.import_module(submod)
                    obj = getattr(module, parts[1])
                else:
                    obj = getattr(module, fun)
                page["functions"].append(obj)

            # extract documented classes
            # note that if one is listed as an attribute of a submodule
            # we attempt to import the submodule and extract the class there
            for clss in data.get("classes", []):
                if "." in clss:
                    parts = clss.split(".")
                    submod = ".".join([module.__name__, parts[0]])
                    module = importlib.import_module(submod)
                    obj = getattr(module, parts[1])
                else:
                    obj = getattr(module, clss)
                page["classes"].append(obj)

            for cmd in data.get("commands", []):
                obj = getattr(module, cmd)
                page["commands"].append(obj)
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


VALID_DOCSTRING_SECTIONS = [
    "Args",
    "Returns",
    "Raises",
    "Example",
    "Examples",
    "References",
]


def clean_line(line):
    for header in VALID_DOCSTRING_SECTIONS:
        line = line.replace(f"{header}:", f"**{header}**:")
    line = line.replace(".**", ".\n\n**")
    return line.lstrip()


def format_lists(doc):
    "Convenience function for converting markdown lists to HTML for within-table lists"
    lists = re.findall(
        r"(Args\:|Returns\:|Raises\:|References\:)(.*?)\s+(-.*?)(\n\n|$)",
        doc,
        re.DOTALL,
    )  # find formatted lists
    ul_tag = '<ul class="args">'
    li_tag = '<li class="args">'
    for section, _, items, ending in lists:
        if (
            section.startswith(("Returns:", "Raises:", "References:"))
            and ":" not in items
        ):
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
        doc = doc.replace(items + "\n", list_block, 1).replace(items, list_block, 1)
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


def create_commands_table(commands):
    import click

    full_commands = []
    for cmd in commands:
        full_commands.append((cmd.name, cmd))
        if hasattr(cmd, "commands"):
            for subcommand in sorted(cmd.commands):
                full_commands.append(
                    (f"{cmd.name} {subcommand}", cmd.commands[subcommand])
                )

    table = ""
    for name, cmd in full_commands:
        with click.Context(cmd) as ctx:
            table += format_command_doc(name, ctx, cmd)
    return table


def format_command_doc(name, ctx, cmd):
    table = f"<h3>{name}</h3>\n"
    help_text = cmd.get_help(ctx).split("\n", 2)[2]

    options = help_text.split("Options:")
    arguments = options[0].split("Arguments:")
    if len(arguments) > 1:
        table += arguments[0]

        block = (
            "<pre><code>"
            + "Arguments:"
            + arguments[1].replace("\n", "<br>").replace("*", r"\*")
            + "</code></pre>"
        )
        table += block
    else:
        table += options[0]

    if len(options) > 1:
        block = (
            "<pre><code>"
            + "Options:"
            + options[1].replace("\n", "<br>").replace("*", r"\*")
            + "</code></pre>"
        )
        table += block
    return table


@preprocess(remove_partial=False)
def get_call_signature(obj):
    assert callable(obj), f"{obj} is not callable, cannot format signature."
    try:
        sig = inspect.signature(obj)
    except Exception:
        sig = inspect.signature(obj.__init__)
    items = []
    for n, p in enumerate(sig.parameters.values()):
        # drop self or cls from methods
        if n == 0 and p.name in ("self", "cls"):
            continue
        if p.kind == inspect.Parameter.VAR_POSITIONAL:
            items.append(f"*{p.name}")
        elif p.kind == inspect.Parameter.VAR_KEYWORD:
            items.append(f"**{p.name}")
        elif p.default is not inspect.Parameter.empty:
            default = p.default
            if isinstance(default, MagicMock):
                mock = default
                default = mock._mock_name
                while mock._mock_parent:
                    default = f"{mock._mock_parent._mock_name}.{default}"
                    mock = mock._mock_parent
            elif isinstance(default, str):
                # force double quotes
                default = f'"{default}"'
            else:
                default = repr(default)
            items.append((p.name, default))
        else:
            items.append(p.name)
    return items


def format_signature(obj):
    items = get_call_signature(obj)
    return ", ".join(a if isinstance(a, str) else f"{a[0]}={a[1]}" for a in items)


@preprocess
def create_absolute_path(obj):
    dir_struct = inspect.getfile(obj).split(os.sep)
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
    dir_struct = inspect.getfile(obj).split(os.sep)
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
    Utility that automagically creates an .ipynb notebook file from a markdown file consisting
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
            "</br>on {timestamp}</p>".format(
                short_sha=SHORT_SHA,
                git_sha=GIT_SHA,
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

        shutil.rmtree("api/latest", ignore_errors=True)
        os.makedirs("api/latest", exist_ok=True)

        # UPDATE README
        with open("api/latest/README.md", "w+") as f:
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
                <img src="/assets/prefect-logo-full-gradient.svg"  width=500 >
                </div>

                # API Reference

                This API reference is automatically generated from Prefect's source code
                and unit-tested to ensure it's up to date.

                """
            )

            with open("../README.md", "r") as g:
                readme = g.read()
                index = readme.index("## Hello, world!")
                readme = "\n".join([api_reference_section, readme[index:]])
                f.write(readme)
                f.write(auto_generated_footer)

        # UPDATE CHANGELOG
        with open("api/latest/changelog.md", "w+") as f:
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
            fname, classes, fns, cmds = (
                page["page"],
                page.get("classes", []),
                page.get("functions", []),
                page.get("commands", []),
            )
            fname = f"api/latest/{fname}"
            directory = os.path.dirname(fname)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(fname, "w") as f:
                # PAGE TITLE / SETUP
                f.write(front_matter)
                title = page.get("title")
                if title:  # this would be a good place to have assignments
                    experimental = page.get("experimental")
                    if experimental:
                        f.write(
                            f"""# {title}\n
::: warning Experimental
<div class="experimental-warning">
<svg
    aria-hidden="true"
    focusable="false"
    role="img"
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 448 512"
    >
<path
fill="#e90"
d="M437.2 403.5L320 215V64h8c13.3 0 24-10.7 24-24V24c0-13.3-10.7-24-24-24H120c-13.3 0-24 10.7-24 24v16c0 13.3 10.7 24 24 24h8v151L10.8 403.5C-18.5 450.6 15.3 512 70.9 512h306.2c55.7 0 89.4-61.5 60.1-108.5zM137.9 320l48.2-77.6c3.7-5.2 5.8-11.6 5.8-18.4V64h64v160c0 6.9 2.2 13.2 5.8 18.4l48.2 77.6h-172z"
>
</path>
</svg>

<div>
The functionality here is experimental, and may change between versions without notice. Use at your own risk.
</div>
</div>
:::

---\n
"""
                        )
                    else:
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
                f.write(create_commands_table(cmds))
                f.write("\n")
                f.write(auto_generated_footer)

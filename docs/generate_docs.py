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
import inspect
import os
import re
import shutil
import subprocess
import textwrap
import warnings

import toolz
from functools import partial

import prefect
from prefect.utilities.airflow_utils import AirFlow
from prefect.utilities.bokeh_runner import BokehRunner
from prefect.utilities.tests import raise_on_exception

from tokenizer import format_code


OUTLINE = [
    {
        "page": "environments.md",
        "classes": [
            prefect.environments.Environment,
            prefect.environments.ContainerEnvironment,
            prefect.environments.LocalEnvironment,
        ],
        "title": "Environments",
        "top-level-doc": prefect.environments,
    },
    {
        "page": "triggers.md",
        "functions": [
            prefect.triggers.all_finished,
            prefect.triggers.manual_only,
            prefect.triggers.always_run,
            prefect.triggers.all_successful,
            prefect.triggers.all_failed,
            prefect.triggers.any_successful,
            prefect.triggers.any_failed,
        ],
        "title": "Triggers",
        "top-level-doc": prefect.triggers,
    },
    {"page": "client.md", "classes": [prefect.client.Secret], "title": "Client"},
    {
        "page": "schedules.md",
        "classes": [
            prefect.schedules.Schedule,
            prefect.schedules.NoSchedule,
            prefect.schedules.IntervalSchedule,
            prefect.schedules.CronSchedule,
            prefect.schedules.DateSchedule,
        ],
        "title": "Schedules",
    },
    {
        "page": "serializers.md",
        "classes": [prefect.serializers.Serializer, prefect.serializers.JSONSerializer],
        "title": "Serializers",
        "top-level-doc": prefect.serializers,
    },
    {"page": "core/edge.md", "classes": [prefect.core.edge.Edge], "title": "Edge"},
    {"page": "core/flow.md", "classes": [prefect.core.flow.Flow], "title": "Flow"},
    {
        "page": "core/task.md",
        "classes": [prefect.core.task.Task, prefect.core.task.Parameter],
        "title": "Task",
    },
    {
        "page": "core/registry.md",
        "functions": [
            prefect.core.registry.register_flow,
            prefect.core.registry.build_flows,
            prefect.core.registry.load_flow,
            prefect.core.registry.serialize_registry,
            prefect.core.registry.load_serialized_registry,
            prefect.core.registry.load_serialized_registry_from_path,
        ],
        "title": "Registry",
    },
    {
        "page": "engine/cache_validators.md",
        "functions": [
            prefect.engine.cache_validators.never_use,
            prefect.engine.cache_validators.duration_only,
            prefect.engine.cache_validators.all_inputs,
            prefect.engine.cache_validators.all_parameters,
            prefect.engine.cache_validators.partial_parameters_only,
            prefect.engine.cache_validators.partial_inputs_only,
        ],
        "title": "Cache Validators",
        "top-level-doc": prefect.engine.cache_validators,
    },
    {
        "page": "engine/state.md",
        "classes": [
            prefect.engine.state.State,
            prefect.engine.state.Pending,
            prefect.engine.state.Paused,
            prefect.engine.state.CachedState,
            prefect.engine.state.Scheduled,
            prefect.engine.state.Retrying,
            prefect.engine.state.Running,
            prefect.engine.state.Finished,
            prefect.engine.state.Success,
            prefect.engine.state.Failed,
            prefect.engine.state.TriggerFailed,
            prefect.engine.state.Skipped,
        ],
        "title": "State",
        "top-level-doc": prefect.engine.state,
    },
    {
        "page": "engine/signals.md",
        "classes": [
            prefect.engine.signals.FAIL,
            prefect.engine.signals.TRIGGERFAIL,
            prefect.engine.signals.SUCCESS,
            prefect.engine.signals.RETRY,
            prefect.engine.signals.SKIP,
            prefect.engine.signals.PAUSE,
        ],
        "title": "Signals",
        "top-level-doc": prefect.engine.signals,
    },
    {
        "page": "engine/flow_runner.md",
        "classes": [prefect.engine.flow_runner.FlowRunner],
        "title": "FlowRunner",
    },
    {
        "page": "engine/task_runner.md",
        "classes": [prefect.engine.task_runner.TaskRunner],
        "title": "TaskRunner",
    },
    {
        "page": "engine/executors.md",
        "classes": [
            prefect.engine.executors.base.Executor,
            prefect.engine.executors.dask.DaskExecutor,
            prefect.engine.executors.local.LocalExecutor,
            prefect.engine.executors.sync.SynchronousExecutor,
        ],
        "title": "Executors",
        "top-level-doc": prefect.engine.executors,
    },
    {
        "page": "tasks/control_flow.md",
        "functions": [
            prefect.tasks.control_flow.switch,
            prefect.tasks.control_flow.ifelse,
        ],
        "title": "Control Flow",
    },
    {
        "page": "tasks/function.md",
        "classes": [prefect.tasks.core.function.FunctionTask],
        "title": "FunctionTask",
    },
    {
        "page": "tasks/shell.md",
        "classes": [prefect.tasks.shell.ShellTask],
        "title": "ShellTask",
    },
    {
        "page": "tasks/strings.md",
        "classes": [
            prefect.tasks.templates.StringFormatterTask,
            prefect.tasks.templates.JinjaTemplateTask,
        ],
        "title": "String Templating Tasks",
    },
    {
        "page": "utilities/bokeh.md",
        "classes": [BokehRunner],
        "title": "BokehRunner",
        "top-level-doc": prefect.utilities.bokeh_runner,
    },
    {
        "page": "utilities/collections.md",
        "classes": [prefect.utilities.collections.DotDict],
        "functions": [
            prefect.utilities.collections.merge_dicts,
            prefect.utilities.collections.to_dotdict,
            prefect.utilities.collections.dict_to_flatdict,
            prefect.utilities.collections.flatdict_to_dict,
        ],
        "title": "Collections",
    },
    {
        "page": "utilities/json.md",
        "classes": [
            prefect.utilities.json.JSONCodec,
            prefect.utilities.json.Serializable,
        ],
        "functions": [prefect.utilities.json.register_json_codec],
        "title": "JSON",
    },
    {
        "page": "utilities/executors.md",
        "functions": [
            prefect.utilities.executors.main_thread_timeout,
            prefect.utilities.executors.multiprocessing_timeout,
        ],
        "title": "Executors",
    },
    {
        "page": "utilities/notifications.md",
        "functions": [
            prefect.utilities.notifications.slack_notifier,
            prefect.utilities.notifications.gmail_notifier,
        ],
        "title": "Notifications and Callback Tools",
        "top-level-doc": prefect.utilities.notifications,
    },
    {
        "page": "utilities/tasks.md",
        "functions": [
            prefect.utilities.tasks.tags,
            prefect.utilities.tasks.as_task,
            prefect.utilities.tasks.pause_task,
            prefect.utilities.tasks.task,
            prefect.utilities.tasks.unmapped,
        ],
        "title": "Tasks",
    },
    {"page": "utilities/tests.md", "functions": [raise_on_exception], "title": "Tests"},
    {
        "page": "utilities/airflow.md",
        "classes": [AirFlow],
        "title": "Airflow Conversion Tools",
        "top-level-doc": prefect.utilities.airflow_utils,
    },
]


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
    ul_tag = "<ul style='padding-left:3.5em;text-indent:-3.5em;'>"
    li_tag = "<li style='padding-left:3.5em;text-indent:-3.5em;'>"
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
                + format_code(block).replace("\n", "<br>")
                + "</code></pre>"
            )
        cleaned = cleaned.replace(f"$CODEBLOCK{num}", block.rstrip(" "))
    if in_table:
        return f"<sub>{cleaned}</sub><br>"
    else:
        return cleaned


def create_methods_table(members, title):
    table = ""
    if members:
        table = f"|{title} " + "&nbsp;" * 150 + "|\n"
        table += "|:----|\n"
    for method in members:
        table += format_subheader(method, level=2, in_table=True).replace(
            "\n\n", "<br>"
        )
        table += format_doc(method, in_table=True)
        table += "|\n"
    return table


@preprocess(remove_partial=False)
def get_call_signature(obj):
    assert callable(obj), f"{obj} is not callable, cannot format signature."
    # collect data
    sig = inspect.getfullargspec(obj)
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
    source_tag = f'<span style="text-align:right; float:right; font-size:0.8em; width: 50%; max-width: 6em; display: inline-block;">{link}</span>'
    return source_tag


@preprocess(remove_partial=False)
def format_subheader(obj, level=1, in_table=False):
    class_sig = format_signature(obj)
    if inspect.isclass(obj):
        header = ""
    elif not in_table:
        header = "##" + "#" * level
    else:
        header = "|"
    is_class = "<em><b>class </b></em>" if inspect.isclass(obj) else ""
    class_name = f"<b>{create_absolute_path(obj)}</b>"
    div_tag = f"<div class='sig' style='padding-left:3.5em;text-indent:-3.5em;'>"

    call_sig = f" {header} {div_tag}{is_class}{class_name}({class_sig}){get_source(obj)}</div>\n\n"
    return call_sig


def generate_coverage():
    """
    Generates a coverage report in a subprocess; if one already exists,
    will _not_ recreate for the sake of efficiency
    """
    if os.path.exists(".vuepress/public/prefect-coverage"):
        return

    try:
        tests = subprocess.check_output(
            "cd .. && coverage run `which pytest` && coverage html --directory=docs/.vuepress/public/prefect-coverage/",
            shell=True,
        )
        if "failed" in tests.decode():
            warnings.warn("Some tests failed.")
    except subprocess.CalledProcessError as exc:
        warnings.warn(f"Coverage report was not generated: {exc.output}")


def get_class_methods(obj):
    members = inspect.getmembers(
        obj, predicate=lambda x: inspect.isroutine(x) and obj.__name__ in x.__qualname__
    )
    public_members = [method for (name, method) in members if not name.startswith("_")]
    return public_members


if __name__ == "__main__":

    assert (
        os.path.basename(os.getcwd()) == "docs"
    ), "Only run this script from inside the docs/ directory!"

    GIT_SHA = os.getenv("GIT_SHA", "0000000")
    SHORT_SHA = GIT_SHA[:7]
    auto_generated_footer = (
        "<hr>\n\n<p><small><i>This documentation was auto-generated from "
        "<a href='https://github.com/PrefectHQ/prefect/commit/{git_sha}'>{short_sha}</a>"
        "</i></small></p>".format(short_sha=SHORT_SHA, git_sha=GIT_SHA)
    )

    front_matter = textwrap.dedent(
        """
        ---
        sidebarDepth: 1
        editLink: false
        ---
        """
    ).lstrip()

    shutil.rmtree("api", ignore_errors=True)
    os.makedirs("api", exist_ok=True)
    generate_coverage()

    ## UPDATE README
    with open("api/README.md", "w+") as f:
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
        f.write("# API Reference\n")
        f.write(
            "*This documentation was auto-generated from "
            "[{short_sha}](https://github.com/PrefectHQ/prefect/commit/{git_sha})*".format(
                short_sha=SHORT_SHA, git_sha=GIT_SHA
            )
        )
        f.write(
            "\n\n"
            "*Click <a href='/prefect-coverage/index.html'>here</a> for a complete test coverage report.*"
        )

        with open("../README.md", "r") as g:
            readme = g.read()
            f.write("\n" + readme[readme.index("# Prefect") :])
            f.write(auto_generated_footer)

    ## UPDATE CHANGELOG
    with open("changelog.md", "w+") as f:
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
        fname = f"api/{fname}"
        directory = os.path.dirname(fname)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(fname, "w") as f:
            # PAGE TITLE / SETUP
            f.write(front_matter)
            title = page.get("title")
            if title:  # this would be a good place to have assignments
                f.write(f"# {title}\n---\n")

            top_doc = page.get("top-level-doc")
            if top_doc is not None:
                f.write(inspect.getdoc(top_doc))
                f.write("\n<hr>\n<br>\n\n")
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
                f.write("## Functions\n")
            f.write(create_methods_table(fns, title="top-level functions:"))
            f.write("\n")
            f.write(auto_generated_footer)

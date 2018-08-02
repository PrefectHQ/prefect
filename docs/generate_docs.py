"""Functionality for auto-generating markdown documentation.

Simply run `python generate_docs.py` from inside the `docs/` folder.
"""
import inspect
import os
import prefect


OUTLINE = [
    {
        "page": "environments.md",
        "module": prefect.environments,
        "title": "Environments",
    },
    {"page": "triggers.md", "module": prefect.triggers, "title": "Triggers"},
    {"page": "client.md", "module": prefect.client},
    {"page": "schedules.md", "module": prefect.schedules},
    {"page": "serializers.md", "module": prefect.serializers},
    {"page": "core/edge.md", "module": prefect.core.edge},
    {"page": "core/flow.md", "module": prefect.core.flow},
    {"page": "core/task.md", "module": prefect.core.task},
    {"page": "engine/cache_validators.md", "module": prefect.engine.cache_validators, "title": "Cache Validators"},
    {"page": "engine/state.md", "module": prefect.engine.state, "title": "State"},
    {"page": "engine/signals.md", "module": prefect.engine.signals, "title": "Signals"},
    {"page": "engine/flow_runner.md", "module": prefect.engine.flow_runner, "title": "FlowRunner"},
    {"page": "engine/task_runner.md", "module": prefect.engine.task_runner, "title": "TaskRunner"},
    {"page": "engine/executors/base.md", "module": prefect.engine.executors.base},
    {"page": "engine/executors/local.md", "module": prefect.engine.executors.local},
]


def preprocess(f):
    def wrapped(*args, **kwargs):
        new_obj = getattr(args[0], "__wrapped__", getattr(args[0], 'func', args[0]))
        new_args = list(args)
        new_args[0] = new_obj
        return f(*new_args, **kwargs)

    return wrapped


def format_doc(doc):
    lines = (doc or "").split("\n")
    pre, arg_lines, return_lines, post = [], [], [], []
    currently_on = pre

    for line in lines:
        if line == '':
            currently_on.append(line)
            continue

        if line.startswith('Args'):
            currently_on = arg_lines
        elif line.startswith('Returns'):
            currently_on = return_lines
        elif line.startswith('   '):
            pass
        else:
            if arg_lines:
                currently_on = post
        currently_on.append(line)

    arg_lines = [l.replace('Args:', '**Args**:\n\n').lstrip('    ') for l in arg_lines]
    return_lines = [l.replace('Returns:', '**Returns**:\n').lstrip('    ') for l in return_lines]

    return '\n'.join(pre + arg_lines + return_lines + post) + '\n\n'


@preprocess
def get_call_signature(obj):
    assert callable(obj), f"{obj} is not callable, cannot format signature."
    # collect data
    sig = inspect.getfullargspec(obj)
    args, defaults = sig.args, sig.defaults or []
    varargs, varkwargs = sig.varargs, sig.varkw

    if args == []:
        standalone, kwargs = [], dict()
    else:
        if args[0] == "self":
            args = args[1:]  # remove self from displayed signature

        standalone = args[: -len(defaults)] if defaults else args  # true args
        kwargs = list(zip(args[-len(defaults) :], defaults))  # true kwargs

    varargs = [f"*{varargs}"] if varargs else []
    varkwargs = [f"*{varkwargs}"] if varkwargs else []

    return standalone, varargs, kwargs, varkwargs


@preprocess
def format_signature(obj):
    standalone, varargs, kwargs, varkwargs = get_call_signature(obj)
    # NOTE: I assume the call signature is f(x, y, ..., *args, z=1, ...,
    # **kwargs) and NOT f(*args, x, y, ...)
    psig = ", ".join(
        standalone + varargs + [f"{name}={val}" for name, val in kwargs] + varkwargs
    )
    return psig


@preprocess
def create_absolute_path(obj):
    dir_struct = inspect.getfile(obj).split("/")
    begins_at = dir_struct.index("src") + 1
    return ".".join([d.rstrip(".py") for d in dir_struct[begins_at:]])


@preprocess
def get_source(obj):
    base_url = "https://github.com/PrefectHQ/prefect/tree/master/src/prefect/"
    dir_struct = inspect.getfile(obj).split("/")
    begins_at = dir_struct.index("src") + 2
    line_no = inspect.getsourcelines(obj)[1]
    url_ending = "/".join(dir_struct[begins_at:]) + f"#L{line_no}"
    source_tag = f'<span style="float:right;">[[Source]]({base_url}{url_ending})</span>'
    return source_tag


@preprocess
def format_subheader(obj, level=1):
    class_sig = format_signature(obj)
    if level == 1:
        header = f"## {obj.__name__}\n\n###"
    else:
        header = "##" + "#" * level
    is_class = '<span style="background-color:rgba(27,31,35,0.05);font-size:0.85em;">class</span>' if inspect.isclass(obj) else ""
    class_name = f"{create_absolute_path(obj)}.{obj.__qualname__}"
    call_sig = (
        f" {header} {is_class} ```{class_name}({class_sig})```{get_source(obj)}\n"
    )
    return call_sig


def collect_items(page):
    "Collects all objects to document; currently only supports __all__"
    fname = page["page"]
    module = page["module"]
    assert hasattr(
        module, "__all__"
    ), "Cannot document a module without specifying __all__"
    items = [getattr(module, obj) for obj in module.__all__]
    return fname, items


if __name__ == "__main__":
    assert (
        os.path.basename(os.getcwd()) == "docs"
    ), "Only run this script from inside the docs/ directory!"

    for page in OUTLINE:
        # collect what to document
        fname, items = collect_items(page)
        fname = f"api/{fname}"
        directory = os.path.dirname(fname)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(fname, "w") as f:
            # PAGE TITLE / SETUP
            f.write("---\nsidebarDepth: 1\n---\n\n")
            title = page.get("title")
            if title:  # this would be a good place to have assignments
                f.write(f"# {title}\n---\n")

            for obj in items:
                f.write(format_subheader(obj))
                f.write(format_doc(inspect.getdoc(obj)))

                # document methods
                for name, method in inspect.getmembers(
                    obj,
                    predicate=lambda x: inspect.isroutine(x)
                    and obj.__name__ in x.__qualname__,
                ):
                    if not name.startswith("_"):
                        f.write(format_subheader(method, level=2))
                        f.write(format_doc(inspect.getdoc(method)))

                f.write("\n")

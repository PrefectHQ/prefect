"""Functionality for auto-generating markdown documentation.

Simply run `python dump.py` from inside the `docs/` folder.
"""
import inspect
import os
import prefect


OUTLINE = [
    {"page": "core/edges.md", "module": prefect.core.edge},
    {"page": "core/flows.md", "module": prefect.core.flow},
    {"page": "core/tasks.md", "module": prefect.core.task},
    {"page": "triggers.md", "module": prefect.triggers},
    {"page": "engine/state.md", "module": prefect.engine.state},
    {"page": "engine/signals.md", "module": prefect.engine.signals},
    {"page": "engine/flow_runner.md", "module": prefect.engine.flow_runner},
    {"page": "engine/task_runner.md", "module": prefect.engine.task_runner},
    {"page": "environments.md", "module": prefect.environments},
]


def preprocess(f):
    def wrapped(*args, **kwargs):
        new_obj = getattr(args[0], "__wrapped__", args[0])
        new_args = list(args)
        new_args[0] = new_obj
        return f(*new_args, **kwargs)

    return wrapped


@preprocess
def format_signature(obj):
    assert callable(obj), f"{obj} is not callable, cannot format signature."
    sig = inspect.getfullargspec(obj)
    args, defaults = sig.args, sig.defaults or []
    if args[0] == "self":
        args = args[1:]  # remove self from displayed signature
    standalone = args[: -len(defaults)]  # true args
    kwargs = zip(args[-len(defaults) :], defaults)
    psig = ", ".join(standalone)
    psig += ", ".join([f"{name}={val}" for name, val in kwargs])
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
def format_header(obj, level=1):
    class_sig = format_signature(obj)
    header = "#" * level
    is_class = "_class_" if inspect.isclass(obj) else ""
    class_name = f"**```{create_absolute_path(obj)}.{obj.__qualname__}```**"
    call_sig = (
        f" {header} {is_class} {class_name}```({class_sig})```{get_source(obj)}\n"
    )
    return call_sig


def format_doc(doc):
    pdoc = doc or ""
    return pdoc + "\n\n"


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
        directory = os.path.dirname(fname)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(fname, "w") as f:
            for obj in items:
                f.write(format_header(obj))
                f.write(format_doc(inspect.getdoc(obj)))

                # document methods
                for name, method in inspect.getmembers(
                    obj,
                    predicate=lambda x: inspect.isroutine(x)
                    and obj.__name__ in x.__qualname__,
                ):
                    if not name.startswith("_"):
                        f.write(format_header(method, level=2))
                        f.write(format_doc(inspect.getdoc(method)))

                f.write("\n")

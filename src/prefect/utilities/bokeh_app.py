import cloudpickle
import os
import random
import sys

from bokeh.events import ButtonClick
from bokeh.io import curdoc
from bokeh.layouts import column, row
from bokeh.plotting import figure, ColumnDataSource
from bokeh.models import (
    Arrow,
    CustomJS,
    NormalHead,
    LabelSet,
    HoverTool,
)
from bokeh.models.widgets import Button

from collections import defaultdict

from prefect.engine import state


def color_map(task, task_states, not_run=False):
    s = task_states.get(task) or state.Pending()
    if not_run:
        return "grey"
    if isinstance(s, state.Retrying):
        return "blue"
    elif isinstance(s, state.CachedState):
        return "orange"
    elif isinstance(s, state.Pending):
        return "yellow"
    elif isinstance(s, state.Skipped):
        return "grey"
    elif isinstance(s, state.Success):
        return "green"
    elif isinstance(s, state.Failed):
        return "red"
    else:
        return "black"


def get_state_name(task, task_states):
    s = task_states.get(task)
    if s is not None:
        return s.__class__.__name__
    else:
        return "Pending"


def get_state_msg(task, task_states):
    s = task_states.get(task)
    if s is not None:
        words = str(s.message).split()
        cleaned = "<br>".join([" ".join(words[:5]), " ".join(words[5:])])
        return cleaned
    else:
        return "None"


def is_finished(state):
    if state is None:
        return False
    else:
        return state.is_finished()


## load data
data_dir = os.environ.get("BOKEH_RUNNER")

with open(data_dir, "rb") as g:
    runner = cloudpickle.load(g)

depths = runner.compute_depths()
max_depth = max([depth for depth in depths.values()])
widths = {
    x: sum([1 for task, depth in depths.items() if depth == x])
    for x in range(max_depth + 1)
}
inits, depth_counts = {}, {x: 0 for x in widths}
for task, depth in depths.items():
    width = widths[depth]
    depth_count = depth_counts[depth]
    inits[task] = (
        1 - (depth_count + 1) * 2 / (width + 1),
        1 - (depth + 1) * 2 / (max_depth + 2),
    )
    depth_counts[depth] += 1

graph_layout = inits
xnoise, ynoise = (
    [random.random() / 25 for _ in runner.flow.tasks],
    [random.random() / 5 for _ in runner.flow.tasks],
)


def compile_data(runner):
    plot_data = defaultdict(list)

    not_run = runner.flow.tasks.difference(
        set(runner.flow.sorted_tasks(runner.start_tasks))
    )
    for task in runner.flow.sorted_tasks():
        plot_data["name"].append(task.name)
        plot_data["color"].append(
            color_map(task, runner.task_states, not_run=(task in not_run))
        )
        plot_data["state"].append(get_state_name(task, runner.task_states))
        plot_data["message"].append(get_state_msg(task, runner.task_states))
        plot_data["x"].append(graph_layout[task][0])
        plot_data["y"].append(graph_layout[task][1])

    plot_data["x"] = [x + n for x, n in zip(plot_data["x"], xnoise)]
    plot_data["y"] = [y + n for y, n in zip(plot_data["y"], ynoise)]

    return plot_data


source = ColumnDataSource(data=compile_data(runner))

## configure Plot + tools
plot = figure(
    title="Prefect Flow Interactive Demonstration: {}".format(runner.flow.name),
    x_range=(-1.0, 1.0),
    y_range=(-1.0, 1.0),
    tools="",
    toolbar_location=None,
)

plot.circle("x", "y", size=25, source=source, fill_color="color", alpha=0.5)

for edge in list(runner.flow.edges):
    a, b = edge.upstream_task, edge.downstream_task
    a_index = source.data["name"].index(a.name)
    b_index = source.data["name"].index(b.name)
    plot.add_layout(
        Arrow(
            end=NormalHead(fill_color="grey", size=7, fill_alpha=0.5),
            x_start=source.data["x"][a_index],
            y_start=source.data["y"][a_index],
            x_end=source.data["x"][b_index],
            y_end=source.data["y"][b_index],
            line_alpha=0.5,
        )
    )

labels = LabelSet(
    x="x",
    y="y",
    text="name",
    source=source,
    x_offset=10,
    y_offset=10,
    render_mode="canvas",
    text_font_size="8pt",
)
plot.renderers.append(labels)
hover = HoverTool(
    tooltips=[("Name:", "@name"), ("State:", "@state"), ("Message:", "@message{safe}")]
)
plot.add_tools(hover)


not_run = runner.flow.tasks.difference(
    set(runner.flow.sorted_tasks(runner.start_tasks))
)
on_depth = {
    "depth": min(
        [depths[t] for t in runner.flow.sorted_tasks(runner.start_tasks)], default=0
    )
}


def update(*args):
    to_compute = [t for t, depth in depths.items() if depth == on_depth["depth"]]

    while to_compute:
        task = to_compute.pop(0)
        runner.task_states.update({task: runner.flow_state.result.get(task)})
    new_data = compile_data(runner)
    source.data = new_data
    on_depth["depth"] += 1


def quit_app(*args):
    sys.exit()


butt = Button(label="Run Next Tasks", button_type="success")
butt.on_event(ButtonClick, update)
quit = Button(
    label="Exit", button_type="danger", callback=CustomJS(code="window.close()")
)
quit.on_event(ButtonClick, quit_app)

curdoc().add_root(row(plot, column(butt, quit), width=1500))

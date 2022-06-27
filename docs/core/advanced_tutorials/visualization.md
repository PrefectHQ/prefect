---
sidebarDepth: 0
---

## Flow Visualization

It is a common mantra that the first thing data professionals should do when trying to understand a dataset is to _visualize_ it; similarly, when designing workflows it is always a good idea to visually inspect what you've created.

Prefect provides multiple tools for building, inspecting and testing your flows locally. In this tutorial we will cover some ways you can _visualize_ your flow and its execution. Everything we discuss will require Prefect to be installed with either the `"viz"` or `"dev"` extras:

```
pip install "prefect[dev]" # OR
pip install "prefect[viz]"
```

## Static Flow visualization

The `Flow` class comes with a builtin `visualize` method for inspecting the underlying Directed Acyclic Graph (DAG). Let's setup a basic example:

```python
from prefect import Flow, Parameter

with Flow("math") as f:
    x, y = Parameter("x"), Parameter("y")
    a = x + y

f.visualize()
```

!!! tip Python in tasks
    Prefect tasks support basic Python operations such as addition, subtraction, and comparisons.

![underlying flow graph](/output_1_0.svg){.viz-xs .viz-padded}

Here we see a nice static representation of the underlying flow graph: the nodes correspond to tasks (labeled with the task name) and the edges to dependencies (labeled with the underlying argument name if data is being passed). This can be helpful with understanding task dependencies, and possibly debugging your logic without having to execute your tasks.

Let's now create a more complicated dependency chain.

```python
from prefect import task
from prefect.tasks.control_flow import switch

@task
def handle_zero():
    return float('nan')

with Flow("math") as f:
    x, y = Parameter("x"), Parameter("y")
    a = x + y
    switch(a, cases={0: handle_zero(),
                     1: 6 / a})

# if running in an Jupyter notebook, 
# visualize will render in-line, otherwise
# a new window will open
f.visualize()
```

![output switch condition fail](/output_5_0.svg){.viz-md .viz-padded}

From this visualization we can learn a lot about how Prefect is operating under the hood:
- Constant inputs to Prefect tasks (e.g., `6` above) are not represented as tasks; instead they are stored on the flow object under the `constants` attribute; this attribute contains a dictionary relating tasks to which constant values they rely on
- Some of Prefect's utility tasks (such as `switch` above) create multiple tasks under the hood; in this case `switch` created a new `CompareValue` task for each case we provided
- Every type of operation on a task is itself represented by another task; above we can see that division resulted in a new `Div` task. This highlights a principle to remember when building your workflows: all runtime logic should be represented by a task
- Some types of task dependencies rely on data (represented by labeled edges in the visualization) whereas others represent pure state dependencies (represented by unlabeled edges in the visualization)

### Static Flow Visualization - Post Run

In addition to viewing the structure of our DAG, Prefect allows you to easily visualize the post-run states of your tasks as well. Using our flow from above, suppose we were curious about how states would propagate if we set `x=1` and `y=2` (a condition not handled by the `switch`). In this case, we can first execute the flow, and then provide all the task states to the `flow.visualize` method to see how the states propagated!

!!! tip State colors
    The colors of all states, along with their inheritance relationships can be found in [the API reference for states](/api/latest/engine/state.html).
:::

```python
flow_state = f.run(x=1, y=2)
f.visualize(flow_state=flow_state)
```

![flow with colored post-run task states](/flow_visualize_colors.svg){.viz-md .viz-padded}

We can see that both branches of the `switch` were skipped in this case.

!!! tip Live Updating Visualizations
    All of the visualizations are static visualizations that can only be inspected before or after a run is complete.  For live updating views, check out Schematics in the [Prefect Cloud UI](../../orchestration/ui/flow-run.html#schematic).
:::

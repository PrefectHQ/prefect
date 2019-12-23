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

::: tip
Prefect tasks support basic python operations such as addition, subtraction, and comparisons.
:::

![underlying flow graph](/output_1_0.svg){.viz-xs .viz-padded}

Here we see a nice static representation of the underlying flow graph: the nodes correspond to tasks (labeled with the task name) and the edges to dependencies (labeled with the underlying argument name if data is being passed). This can be helpful with understanding task dependencies, and possibly debugging your logic without having to execute your tasks.

To see how this might be helpful, let's create a more complicated dependency chain.

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
##    PrefectWarning: One of the tasks passed to the switch condition
##    has upstream dependencies: <Task: Div>.
##    Those upstream tasks could run even if the switch condition fails,
##    which might cause unexpected results.
```

Hmmm - we received a warning which tells us that the `Div` Task has an upstream dependency that may run even if the switch condition fails... what does that mean exactly? Let's visualize the flow to find out:

```python
f.visualize()
```

![output switch condition fail](/output_5_0.svg){.viz-md .viz-padded}

We can now see what the warning was telling us: the `Div` task has an upstream dependency of "6" which exists outside of the switch condition. Morever, this "6" task has no upstream dependencies so it is considered a "root" task:

::: tip Everything is a task
Internally, Prefect represents _everything_ as a task. In this case, Prefect creates a task called "6" that returns the integer 6 when it runs.
:::

```python
f.root_tasks()
# {<Parameter: x>, <Parameter: y>, <Task: 6>}
```

These are the tasks the flow will execute first; consequently, the task "6" will be run _regardless_ of whether the `Div` task is skipped by the switch condition. If, instead of merely returning the number 6, this task performed a lot of computation, we might want it executed _only if_ the switch condition passes; in this case we would need to rearrange our flow.

::: tip Note
Notice that we have identified this situation and possibly remediated it _all without executing our code_!
:::

### Static Flow Visualization - Post Run

In addition to viewing the structure of our DAG, Prefect allows you to easily visualize the post-run states of your tasks as well. Using our flow from above, suppose we were curious about how states would propagate if we set `x=1` and `y=1` (a condition not handled by the `switch`). In this case, we can first execute the flow, and then provide all the task states to the `flow.visualize` method to see how the states propagated!

::: tip State colors
The colors of all states, along with their inheritance relationships can be found in [the API reference for states](/api/unreleased/engine/state.html).
:::

```python
flow_state = f.run(x=1, y=2)
f.visualize(flow_state=flow_state)
```

![flow with colored post-run task states](/flow_visualize_colors.svg){.viz-md .viz-padded}

We can see that the `6` task was still executed (as we suspected), and both branches of the `switch` were skipped.

::: tip Visualization is a useful debug tool
Fully understanding why our flow failed might have been trickier without the visualization aids that Prefect provides.
:::

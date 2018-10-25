---
sidebarDepth: 0
---

## Flow Visualization

It is a common mantra that the first thing data professionals should do when trying to understand a dataset is to _visualize_ it; similarly, when designing workflows it is always a good idea to visually inspect what you've created.

Prefect provides multiple tools for building, inspecting and testing your flows locally.  In this tutorial we will cover some ways you can _visualize_ your flow and its execution.  Everything we discuss will require Prefect to be installed with either the `"viz"` or `"dev"` extras:
```
# assuming your current directory is the prefect repo
pip install ".[dev]" # OR
pip install ".[viz]"
```

## Static Flow visualization

The `Flow` class comes with a builtin `visualize` method for inspecting the underlying Directed Acyclic Graph (DAG).  Let's setup a basic example:


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

![](/output_1_0.svg) {style="text-align: center;"}

Here we see a nice static representation of the underlying flow graph: the nodes correspond to tasks (labeled with the task name) and the edges to dependencies (labeled with the underlying argument name if data is being passed).  This can be helpful with understanding task dependencies, and possibly debugging your logic without having to execute your tasks.

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

Hmmm - we received a warning which tells us that the `Div` Task has an upstream dependency that may run even if the switch condition fails... what does that mean exactly?  Let's visualize the flow to find out:


```python
f.visualize()
```

![](/output_5_0.svg) {style="text-align: center;"}

We can now see what the warning was telling us: the `Div` task has an upstream dependency of "6" which exists outside of the switch condition. Morever, this "6" task has no upstream dependencies so it is considered a "root" task:

::: tip Everything is a task
Internally, Prefect represents _everything_ as a task.  In this case, Prefect creates a task called "6" that simply returns the integer 6 when it runs.
:::

```python
f.root_tasks()
# {<Parameter: x>, <Parameter: y>, <Task: 6>}
```

These are the tasks the flow will execute first (by default); consequently, the task "6" will be run _regardless_ of whether the `Div` task is skipped by the switch condition.  If, instead of merely returning the number 6, this task performed a lot of computation, we might want it executed _only if_ the switch condition passes; in this case we would need to rearrange our flow.  

::: tip Note
Notice that we have identified this situation and possibly remediated it _all without executing our code_!
:::

### Static Flow Visualization - Post Run

In addition to viewing the structure of our DAG, Prefect allows you to easily visualize the post-run states of your tasks as well. Using our flow from above, suppose we were curious about how states would propagate if we set `x=1` and `y=1` (a condition not handled by the `switch`).  In this case, we can first execute the flow, and then provide all the task states to the `flow.visualize` method to see how the states propagated!
```python
flow_state = f.run(return_tasks=f.tasks) # ask for all tasks to be returned
f.visualize(flow_state=flow_state)
```

![](/flow_visualize_colors.svg) {style="text-align: center;"}

We can see that the `6` task was still executed (as we suspected), and both branches of the `switch` were skipped.

## Dynamic Flow visualization with `BokehRunner`

`Flow.visualize()` is great for static analysis, but for understanding the underlying _execution_ model, Prefect's `BokehRunner` is a more powerful tool.  

::: warning
The `BokehRunner` tool is not a replacement for a UI, nor is it meant to be used in production; it is merely a tool for better understanding Prefect's execution model and helping users debug their flows locally.
:::

`BokehRunner` is a subclass of `FlowRunner`, which is the class responsible for setting up the execution of flows.  The `BokehRunner` will _first_ perform a full execution of the flow, and then, using the stored states from the execution, run a [Bokeh webapp](https://bokeh.pydata.org/en/latest/) that allows for step-by-step _simulated_ execution that cleanly displays how states are propagated through the flow until the final flow state is reached.

Using our flow `f` from above, we run the `BokehRunner` as follows (this will open up a new tab / window with the Bokeh application):


```python
from prefect.utilities.bokeh_runner import BokehRunner

BokehRunner(flow=f).run(parameters=dict(x=1, y=5))
```

The web app should look something like this (the layout may change slightly from run to run):

![](/bokeh1.png) {style="text-align: center;"}


Similar to `f.visualize()`, we have a node for every task and an edge for every dependency.  The biggest difference is that now we have information regarding the current _state_ of each task and of the overall flow.  In the actual web app you can use your mouse to hover over each node and see more information about its state.

We can run the first set of tasks by clicking "Run Next Tasks"; this will execute the first set of non-dependent tasks (the root tasks in this case): 

![](/bokeh2.png) {style="text-align: center;"}


Now we see what the warning was telling us even more clearly - the "6" task is run on the first pass.  Continuing this exercise, we ultimately reach the final state: 

![](/bokeh3.png) {style="text-align: center;"}


Let's see what would happen if we explicitly tell the flow to start at the "x" and "y" tasks, and trigger the divide switch:


```python
BokehRunner(flow=f).run(parameters=dict(x=1, y=0),
                        start_tasks=[x, y])
```

![](/bokeh4.png) {style="text-align: center;"}


We find that our final state is `Failed` because the "6" task wasn't run, so this pattern of running our flow is not going to be very robust.  
::: tip 
Fully understanding why our flow failed might have been trickier without the visualization aids that Prefect provides.
:::

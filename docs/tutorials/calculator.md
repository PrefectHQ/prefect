---
sidebarDepth: 0
---

# Using Prefect as a Calculator

Prefect is a heavy-duty data workflow system, but it handles lightweight realtime applications just as well.

To illustrate that, let's build a simple calculator.

## Setup

Let's write a simple function to make retrieving our calculation results a little easier. This function just passes parameters to our flow and retrieves the result of its terminal task:

```python
def run(flow, **parameters):
    """
    Convenience function that figures out a flow's terminal task, then
    runs the flow with the provided parameters and returns that task's result.
    """
    task = list(flow.terminal_tasks())[0]
    state = flow.run(parameters=parameters, return_tasks=[task])
    return state.result[task].result
```

## Adding One

What could be easier than adding 1 to a number?

```python
from prefect import Flow, Parameter

with Flow('Add one') as flow:
    result = Parameter('x') + 1
```

::: tip Behind the scenes
Prefect added three tasks to this flow:

- One that we created explicitly to return our parameter `x`
- One that was automatically generated to return a constant `1`
- One that was automatically generated to add the previous two together.

`Parameters` are just like any other task, except that they take their values from user input.
:::

Let's test it out:
```python
assert run(flow, x=1) == 2
assert run(flow, x=2) == 3
assert run(flow, x=-100) == -99
```


## Adding two numbers

Let's kick this up a notch -- why have one input when you could have two?

```python
with Flow('Add x and y') as flow:
    result = Parameter('x') + Parameter('y')
```

::: tip Multiple Parameters
A flow can have as many parameters as you want, as long as they have unique names.
:::

Our new calculator works like a charm:
```python
assert run(flow, x=1, y=1) == 2
assert run(flow, x=40, y=2) == 42
```

## Arithmetic

Addition's all very well, but let's give our users some choices. We can combine a new `op` parameter with a `switch` to let users choose the calculation they want done:

```python
from prefect.tasks.control_flow import switch, merge

with Flow('Arithmetic') as flow:
    x, y = Parameter('x'), Parameter('y')
    operations = {
        '+': x + y,
        '-': x - y,
        '*': x * y,
        '/': x / y
    }
    switch(condition=Parameter('op'), cases=operations)
    result = merge(*operations.values())
```

::: tip Conditional Branches
Prefect has a few ways to run tasks conditionally, including the `switch` function used here and the simpler `ifelse`.

In this case, the `switch` checks for the value of the `op` parameter, and then executes the task corresponding to the appropriate computation. A `merge` function is used to combine all the branches back in to a single result.
:::

Now when we run our flow, we provide the desired operation:

```python
assert run(flow, x=1, op='+', y=2) == 3
assert run(flow, x=1, op='-', y=2) == -1
assert run(flow, x=1, op='*', y=2) == 2
assert run(flow, x=1, op='/', y=2) == 0.5
```

## Parsing input

Our arithmatic calculator works, but it's a bit cumbersome to run. Let's write a quick custom task to take a string expression and parse it into our `x`, `y`, and `op`; the rest of the code is just the same as before:

```python
from prefect import task
from prefect.tasks.control_flow import switch, merge

@task
def parse_input(i):
    x, op, y = i.split(' ')
    return dict(x=float(x), op=op, y=float(y))

with Flow('Arithmetic') as flow:
    inputs = parse_input(Parameter('expression'))
    x, y = inputs['x'], inputs['y']
    operations = {
        '+': x + y,
        '-': x - y,
        '*': x * y,
        '/': x / y
    }
    switch(condition=inputs['op'], cases=operations)
    result = merge(*operations.values())
```
::: tip The @task decorator
The `@task` decorator is a simple way to turn any function into a task.
:::
::: tip Indexing a task
Just as we've shown that tasks can be added (or subtracted, or multipled, or divided), they can be indexed as well. Here, we index the result of the `inputs` task to get `x`, `y`, and `op`. Like every other Prefect operation, the indexing itself is recorded in the computational graph, but the execution is deferred until the flow is run and the indexed result is actually available.
:::

And now we can run our calculator on string expressions :tada::
```python
assert run(flow, expression='1 + 2') == 3
assert run(flow, expression='1 - 2') == -1
assert run(flow, expression='1 * 2') == 2
assert run(flow, expression='1 / 2') == 0.5
```

For the curious and/or brave, here's a visualization of the computational graph Prefect automatically tracked and generated:
```python
flow.visualize()
```
![](/calculator.png)

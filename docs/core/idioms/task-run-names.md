# Naming task runs based on inputs

Tasks in Prefect provide a way for dynamically naming task runs based on the inputs provided to them from
upstream tasks. This is accomplished by providing a callable to the `task_run_name` kwarg on the task.
The callable has the option to use values from not only task inputs but also everything available in
[context](/api/latest/utilities/context.html) during the run. This mechanism operates in a similar
fashion to how
[result targets are templated](/core/concepts/persistence.html#output-caching-based-on-a-file-target).
Providing a callable task run name is a great way to help identify errors that may occur in a flow, for
example, easily showing which mapped task failed based on the input it received.

::: warning Backend Only
This feature only works when running in the context of an [API backend](/orchestration/) run using
something like the [Prefect Server](/orchestration/server/overview.html) or
[Prefect Cloud](https://cloud.prefect.io).
:::

In the example snippet below we have a flow that maps over a set of data returned from an upstream task
and (for demonstration purposes) it raises an error when it receives the `demo` string as an input.

:::: tabs
::: tab "Functional API"
```python
from prefect import task, Flow

@task
def get_values():
    return ["value", "test", "demo"]

@task
def compute(val):
    if val == "demo":
        raise ValueError("Nope!")

with Flow("task_run_names") as flow:
    vals = get_values()
    compute.map(vals)
```
:::

::: tab "Imperative API"
```python
from prefect import Task, Flow

class GetValues(Task):
    def run(self):
        return ["value", "test", "demo"]

class Compute(Task):
    def run(self, val):
        if val == "demo":
            raise ValueError("Nope!")

flow = Flow("task_run_names")

vals = GetValues()
compute = Compute()

compute.set_upstream(vals, flow=flow, key="val", mapped=True)
```
:::
::::

![task runs no names](/idioms/task_runs_no_names.png)

In the image above we can identify that one of our mapped children tasks failed however we are unable to
identify exactly which task failed based on this information alone. This is where providing a callable to
the task's `task_run_name` kwarg comes in handy.

```python
task_run_name=lambda **kwargs: f"{kwargs['val']}"
```

This callable will template the task run's name based on the `val` input it receives:

:::: tabs
::: tab "Functional API"
```python{7}
from prefect import task, Flow

@task
def get_values():
    return ["value", "test", "demo"]

@task(task_run_name=lambda **kwargs: f"{kwargs['val']}")
def compute(val):
    if val == "demo":
        raise ValueError("Nope!")

with Flow("task_run_names") as flow:
    vals = get_values()
    compute.map(vals)
```
:::

::: tab "Imperative API"
```python{15}
from prefect import Task, Flow

class GetValues(Task):
    def run(self):
        return ["value", "test", "demo"]

class Compute(Task):
    def run(self, val):
        if val == "demo":
            raise ValueError("Nope!")

flow = Flow("task_run_names")

vals = GetValues()
compute = Compute(task_run_name=lambda **kwargs: f"{kwargs['val']}")

compute.set_upstream(vals, flow=flow, key="val", mapped=True)
```
:::
::::

![task runs with names](/idioms/task_runs_names.png)

Now we can identify that the task with the `demo` input is the one that failed!

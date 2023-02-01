# Accessing task results locally

<div style="border: 2px solid #27b1ff; border-radius: 10px; padding: 1em;">
Looking for the latest <a href="https://docs.prefect.io/">Prefect 2</a> release? Prefect 2 and <a href="https://app.prefect.cloud">Prefect Cloud 2</a> have been released for General Availability. See <a href="https://docs.prefect.io/">https://docs.prefect.io/</a> for details.
</div>

When working on your flows locally Prefect makes it easy to retrieve the [results](/core/concepts/results.html) from your individual tasks in the flow. This is done by grabbing the `.result` attribute from [states](/core/concepts/states.html). Calling `flow.run` returns the flow's final state which can be used to retrieve results from all of the tasks in the flow.

::: warning Local Only
This currently does not cover retrieving result values when running in the context of an [API backend](/orchestration/) run using Prefect Core's server or Prefect Cloud.
:::

:::: tabs
::: tab Functional API
```python
from prefect import task, Flow

@task
def get_value():
    return 10

@task
def add_value(v):
    return v + 10

@task
def print_value(v):
    print(v)

with Flow("task-results") as flow:
    v = get_value()
    v_added = add_value(v)
    p = print_value(v_added)

state = flow.run()

assert state.result[v].result == 10
assert state.result[v_added].result == 20
assert state.result[p].result == None     # task does not return a result
```
:::

::: tab Imperative API
```python
from prefect import Task, Flow

class GetValue(Task):
    def run(self):
        return 10

class AddValue(Task):
    def run(self, v):
        return v + 10

class PrintValue(Task):
    def run(self, v):
        print(v)

flow = Flow("task-results")

get_value = GetValue()
add_value = AddValue()
print_value = PrintValue()

get_value.set_downstream(add_value, key="v", flow=flow)
add_value.set_downstream(print_value, key="v", flow=flow)

state = flow.run()

assert state.result[get_value].result == 10
assert state.result[add_value].result == 20
assert state.result[print_value].result == None
```
:::
::::
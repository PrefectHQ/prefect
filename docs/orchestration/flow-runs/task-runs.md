# Task runs

A task run is created for each task in your flow during a flow run. Like flow runs, task runs have a backend generated unique `id` and their `state` is updated as they are executed.

!!! tip Results
    Prefect does not store the _results_ of your task runs. The data that your task returns is stored safely on your own infrastructure unless explicitly sent to Prefect's backend. 
:::

## Inspecting task runs

### Python

The Prefect Core library provides an object for inspecting task runs without writing queries at `prefect.backend.TaskRunView`.

#### Creating a `TaskRunView`

!!! tip 
    You should typically access task runs from a `FlowRunView` object. This will cache `TaskRunView` objects for finished tasks and pass the `flow_run_id` for you. Read the [flow run inspection documentation](./inspection#prefect-library) to get started.
:::

A `TaskRunView` is created by querying the backend for task run data. You can use the task `slug` or the task run `id` to look up the data for a `TaskRunView`.

Task slug:

When using a task slug, the `flow_run_id` is needed because the task may have been run in multiple flow runs.
```python
from prefect.backend import TaskRunView

task_run = TaskRunView.from_task_slug("say_hello-1", flow_run_id="8e445d74-9ca6-425b-98e5-72754b7ea174")
# TaskRunView(
#   task_run_id='c8751f34-9d5e-4ea7-aead-8b50978dabb7', 
#   task_id='34b0dd2d-582e-4f0a-923d-63daf1e38fe5', 
#   task_slug='say_hello-1',
#   state=<Success: "Task run succeeded.">, 
#   result=<not loaded>
# )
```

Task run id:

```python
from prefect.backend import TaskRunView

task_run = TaskRunView.from_task_run_id("c8751f34-9d5e-4ea7-aead-8b50978dabb7")
# TaskRunView(
#   task_run_id='c8751f34-9d5e-4ea7-aead-8b50978dabb7', 
#   task_id='34b0dd2d-582e-4f0a-923d-63daf1e38fe5', 
#   task_slug='say_hello-1',
#   state=<Success: "Task run succeeded.">, 
#   result=<not loaded>
# )
```


#### Task run results

Results from task runs are persisted to the location you've specified in the task's `result` attribute. The `Result` type allows you to store task results in many locations on your own infrastructure. See the [results documentation](/core/concepts/results.md) for more details on configuring results.

`TaskRunView` provides a `get_result` method which will load and cache the return value of your task from the result location. 

```python
# Presume we have a flow with the following task
@task
def foo():
  return "foobar!"

task_run = TaskRunView.from_task_slug("foo-1", flow_run_id="<id>")
task_run.get_result()  # "foobar!"
```

##### Mapped task results

The `get_result` method of a _child_ of a mapped task will return the single result for that task run. For the _parent_ task, an additional query will be run to get the result locations all of the children and a list will be returned populated with all of the child results.

For example, with the following flow:
```python
from prefect import task, Flow

@task
def inc(x):
  return x + 1

with Flow("example-mapped") as flow:
  inc.map([0, 1, 2, 3, 4, 5])
```

You can retrieve all of the mapped results or a single result:
```python
from prefect.backend import TaskRunView

inc_parent = TaskRunView.from_task_slug("inc-1", flow_run_id="<id>")
inc_parent.get_result()  # [1, 2, 3, 4, 5, 6]

inc_child = TaskRunView.from_task_slug("inc-1", flow_run_id="<id>", map_index=2)
inc_child.get_result()  # 3
```

If your mapped task has many children, you can iterate through the children one at a time:
```python
from prefect.backend import TaskRunView

inc_parent = TaskRunView.from_task_slug("inc-1", flow_run_id="<id>")
for child_task_run in inc_parent.iter_mapped():
    print(child_task_run.get_result())
# 1
# 2
# 3
# 4
# 5
# 6
```

### Task

For composing flows, the Prefect task library provides a task to retrieve the result of a task run from another flow run. This uses the `TaskRunView.get_result()` method under the hood, it may be helpful to [get familiar with how that works](#task-run-results) first.


Given a very simple 'child' flow

```python
from prefect import Flow, task


@task
def create_some_data():
    return list(range(5))


with Flow("child") as child_flow:
    data = create_some_data()
```

We can create a 'parent' flow that runs the 'child' flow and retrieves the results

```python
from prefect import Flow
from prefect.tasks.prefect import create_flow_run, get_task_run_result

with Flow("parent") as parent_flow:
    child_run_id = create_flow_run(flow_name="child")

    child_data = get_task_run_result(child_run_id, "create_some_data-1")
    # At runtime, `child_data` will be `[0, 1, 2, 3, 4]`
```

For more details on creating child flow runs, see the [`create_flow_run` task documentation](./creation.md#task)

!!! warning Results require completion
    Task run results will not be retrieved until the flow run with the task run is finished. This is because the flow run may make changes to the task run before completion. This means that if your 'create_some_data' task run finishes but the 'child' flow run continues to do some other work, 'get_task_run_result' will block until all the tasks in the 'child' flow run are finished.
:::

### GraphQL

#### Querying for task runs in a flow run

Here we query for all of the task runs in a run of the `prefect.hello_world` flow

```graphql
query {
  task_run(where: {flow_run_id: {_eq: "8e445d74-9ca6-425b-98e5-72754b7ea174"}}) {
    id
    state
    start_time
    task {
      slug
    }
  }
}
```

Example response

```json
{
  "data": {
    "task_run": [
      {
        "id": "c8751f34-9d5e-4ea7-aead-8b50978dabb7",
        "state": "Success",
        "start_time": "2021-05-12T18:00:01.696849+00:00",
        "task": {
          "slug": "say_hello-1"
        }
      },
      {
        "id": "f5f422f6-4f56-45d2-bd55-5ea048070d84",
        "state": "Success",
        "start_time": "2021-05-12T18:00:00.229202+00:00",
        "task": {
          "slug": "capitalize-1"
        }
      },
      {
        "id": "7cc167d3-737d-4187-85d8-d5e5a75fbd93",
        "state": "Success",
        "start_time": "2021-05-12T17:59:58.33804+00:00",
        "task": {
          "slug": "name"
        }
      }
    ]
  }
}
```

### UI

For monitoring task runs from the UI, see the [UI documentation on task runs](/orchestration/ui/task-run.md).

### CLI

The CLI does not currently support looking up task run information. Would this be useful to you? Chime in [on GitHub](https://github.com/PrefectHQ/prefect/issues/4493).

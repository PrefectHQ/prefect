# Inspecting flow runs

For monitoring flow runs from the UI, see the [UI documentation on flow runs](../ui/flow-run.md).

## Python

The Prefect Core library provides an object for inspecting flow runs without writing queries at `prefect.backend.FlowRunView`.

### Creating a `FlowRunView`

A `FlowRunView` can be created using the `from_flow_run_id` class method. This methods will query for flow run information and populate a `FlowRunView` instance.

```python
from prefect.backend import FlowRunView

flow_run = FlowRunView.from_flow_run_id("4c0101af-c6bb-4b96-8661-63a5bbfb5596")
```

!!! warning Immutability
    `FlowRunView` objects are views of the backend `Flow Run` at the time of the view's creation.
    They will not retrieve the newest information each time you access their properties.
    To get the newest data for a flow run, use `flow_run = flow_run.get_latest()` which will return a new `FlowRunView` instance.


### Getting flow run states

The state of the flow run is accessible using the `.state` property
```python
flow_run.state
#  <Success: "All reference tasks succeeded.">
```

This state object is deserialized into the Prefect Core `State` type, which provides some helpful utilities
```python
flow_run.state.is_finished()
# True

flow_run.state.is_running()
# False

flow_run.state.message
# 'All reference tasks succeeded.'
```

### Getting flow run logs

Get a List of `FlowRunLog` from the flow run using `.get_logs()`:

```python
flow_run.get_logs()
# [
#   FlowRunLog(timestamp=DateTime(1978, 03, 08, 22, 30, 00, 000000, tzinfo=Timezone('+00:00')), level=20, message='Submitted for execution: Task XXXXXXX'),
#   FlowRunLog(timestamp=DateTime(1978, 03, 08, 22, 30, 01, 123456, tzinfo=Timezone('+00:00')), level=20, message="Beginning Flow run for 'radio_show'"),
#   FlowRunLog(timestamp=DateTime(1978, 03, 08, 22, 30, 02, 234567, tzinfo=Timezone('+00:00')), level=20, message="Task 'series_one': Starting task run..."),
#   FlowRunLog(timestamp=DateTime(1978, 03, 08, 22, 42, 42, 424242, tzinfo=Timezone('+00:00')), level=20, message='It feels like I just had my brains smashed out by a slice of lemon wrapped round a large gold brick.'),
#   FlowRunLog(timestamp=DateTime(1978, 04, 12, 22, 59, 59, 987654, tzinfo=Timezone('+00:00')), level=20, message="Task 'series_one': Finished task run for task with final state: 'Success'"),
#   FlowRunLog(timestamp=DateTime(1978, 04, 12, 23, 00, 00, 000000, tzinfo=Timezone('+00:00')), level=20, message='Flow run SUCCESS: all reference tasks succeeded')
# ]
```

Each `FlowRunLog` in the list contains a log message, along with the log level and timestamp.

### Getting flow metadata

Metadata about the flow that the flow run was created for is accessible using `.get_flow_metadata()`

```python
flow_run.get_flow_metadata()
# FlowView(
#   flow_id='8bdcf5b5-7598-49d1-a885-61612ca550de', 
#   name='hello-world', 
#   project_name='default', 
#   storage_type=Module
# )
```

This object contains the metadata that the Prefect backend stores about your flow at registration time. See [the reference documentation](/api/latest/backend/flow.md) for more details.

!!! tip Flow metadata caching
    Flow metadata is lazily loaded by request then _cached_ in the `FlowRunView` for later access.
    This means the first call requires network IO but future calls are instant.
    If you want to force the `FlowView` to be reloaded, pass `no_cache=True`.


### Getting flow task runs

The `FlowRunView` allows you to access task runs from the flow run by `task_run_id` or `slug`.
This will run a query to retrieve the task run of interest and store the result in a `TaskRunView`.

```python
task_run = flow_run.get_task_run(task_slug='say_hello-1')
# TaskRunView(
#   task_run_id='c8751f34-9d5e-4ea7-aead-8b50978dabb7', 
#   task_id='34b0dd2d-582e-4f0a-923d-63daf1e38fe5', 
#   task_slug='say_hello-1', 
#   state=<Success: "Task run succeeded.">, 
#   result=<not loaded>
# )
```

!!! tip Task run caching
    When a task run is retrieved, if it is in a finished state, it will be cached in the `FlowRunView`.
    This reduces the number of calls to the backend API. 
    When you use `flow_run.get_latest()`, these cached tasks are preserved.


!!! tip Listing task run ids
    All of the task run ids for a flow run can be retrieved using the `.task_run_ids` property.
    This will run a query against the backend.


```python
flow_run.task_run_ids
# ['c8751f34-9d5e-4ea7-aead-8b50978dabb7',
# 'f5f422f6-4f56-45d2-bd55-5ea048070d84',
# '7cc167d3-737d-4187-85d8-d5e5a75fbd93']
```


For more details on the `TaskRunView`, see [the task runs documentation](./task-runs.md).

## GraphQL

### Querying for a single flow run

You can query for a flow run by any of its properties. Here's a query using the flow run name

```graphql
query {
  flow_run(where: {name: {_eq: "woodoo-leopard"}}) {
    id
    state
    start_time
  }
}
```

Example response

```json
{
  "data": {
    "flow_run": [
      {
        "id": "8e445d74-9ca6-425b-98e5-72754b7ea174",
        "state": "Success",
        "start_time": "2021-05-12T17:59:56.383629+00:00"
      }
    ]
  }
}
```

Note that the response returns a `list` in the `flow_run` section because your query could return multiple results if the name is not unique.

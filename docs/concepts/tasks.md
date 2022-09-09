---
description: Prefect tasks represents a discrete unit of work in a Prefect workflow.
tags:
    - tasks
    - task runs
    - functions
    - retries
    - caching
    - cache keys
    - cache key functions
    - tags
    - results
    - async
    - asynchronous execution
    - map
    - concurrency
    - concurrency limits
    - task concurrency
---

# Tasks

A task is a function that represents a discrete unit of work in a Prefect workflow. Tasks are not required &mdash; you may define Prefect workflows that consist only of flows, using regular Python statements and functions. Tasks enable you to encapsulate elements of your workflow logic in observable units that can be reused across flows and subflows. 

## Tasks overview

Tasks are functions: they can take inputs, perform work, and return an output. A Prefect task can do almost anything a Python function can do.  

Tasks are special because they receive metadata about upstream dependencies and the state of those dependencies before they run, even if they don't receive any explicit data inputs from them. This gives you the opportunity to, for example, have a task wait on the completion of another task before executing.

Tasks also take advantage of automatic Prefect [logging](/concepts/logs) to capture details about task runs such as runtime, tags, and final state. 

You can define your tasks within the same file as your flow definition, or you can define tasks within modules and import them for use in your flow definitions. All tasks must be called from within a flow. Tasks may not be called from other tasks.

**Calling a task from a flow**

Use the `@task` decorator to designate a function as a task. Calling the task from within a flow function creates a new task run:

```python hl_lines="3-5"
from prefect import flow, task

@task
def my_task():
    print("Hello, I'm a task")

@flow
def my_flow():
    my_task()
```

Tasks are uniquely identified by a task key, which is a hash composed of the task name, the fully-qualified name of the function, and any tags. If the task does not have a name specified, the name is derived from the task function.

!!! note "How big should a task be?"
    Prefect encourages "small tasks" &mdash; each one should represent a single logical step of your workflow. This allows Prefect to better contain task failures.

    To be clear, there's nothing stopping you from putting all of your code in a single task &mdash; Prefect will happily run it! However, if any line of code fails, the entire task will fail and must be retried from the beginning. This can be avoided by splitting the code into multiple dependent tasks.

!!! warning "Calling a task's function from another task"

    Prefect does not allow triggering task runs from other tasks. If you want to call your task's function directly, you can use `task.fn()`. 

    ```python hl_lines="9"
    from prefect import flow, task

    @task
    def my_first_task(msg):
        print(f"Hello, {msg}")

    @task
    def my_second_task(msg):
        my_first_task.fn(msg)

    @flow
    def my_flow():
        my_second_task("Trillian")

    ```

    Note that in the example above you are only calling the task's function without actually generating a task run. Prefect won't track task execution in your Prefect backend if you call the task function this way. You also won't be able to use features such as retries with this function call.

## Task arguments

Tasks allow a great deal of customization via arguments. Examples include retry behavior, names, tags, caching, and more. Tasks accept the following optional arguments.

| Argument | Description |
| --- | --- |
| name | An optional name for the task. If not provided, the name will be inferred from the function name. |
| description | An optional string description for the task. If not provided, the description will be pulled from the docstring for the decorated function. |
| tags | An optional set of tags to be associated with runs of this task. These tags are combined with any tags defined by a `prefect.tags` context at task runtime. |
| cache_key_fn | An optional callable that, given the task run context and call parameters, generates a string key. If the key matches a previous completed state, that state result will be restored instead of running the task again. |
| cache_expiration | An optional amount of time indicating how long cached states for this task should be restorable; if not provided, cached states will never expire. |
| retries | An optional number of times to retry on task run failure. |
| retry_delay_seconds | An optional number of seconds to wait before retrying the task after failure. This is only applicable if `retries` is nonzero. |
| version | An optional string specifying the version of this task definition. |

For example, you can provide a `name` value for the task. Here we've used the optional `description` argument as well.

```python hl_lines="1"
@task(name="hello-task", 
      description="This task says hello.")
def my_task():
    print("Hello, I'm a task")
```

## Task results

Task results are cached in memory during execution of your flow run.

Currently, task results are persisted to the location specified by the `PREFECT_LOCAL_STORAGE_PATH` setting. 

!!! note "Task results, retries, and caching"
    Since task results are both cached in memory and peristed to `PREFECT_LOCAL_STORAGE_PATH`, results are available within the context of of flow run and task retries use these results.
    
    However, [task caching](#caching) between flow runs is currently limited to flow runs with access to that local storage path.

## Tags

Tags are optional string labels that enable you to identify and group tasks other than by name or flow. Tags are useful for:

- Filtering task runs by tag in the UI and via the [Orion REST API](/api-ref/rest-api/#filtering).
- Setting [concurrency limits](#task-run-concurrency-limits) on task runs by tag.

Tags may be specified as a keyword argument on the [task decorator](/api-ref/prefect/tasks/#prefect.tasks.task).

```python hl_lines="1"
@task(name="hello-task", tags=["test"])
def my_task():
    print("Hello, I'm a task")
```

You can also provide tags as an argument with a [`tags` context manager](/api-ref/prefect/context/#prefect.context.tags), specifying tags when the task is called rather than in its definition.

```python hl_lines="10"
from prefect import flow, task
from prefect import tags

@task
def my_task():
    print("Hello, I'm a task")

@flow
def my_flow():
    with tags("test"):
        my_task()
```

## Retries

Prefect tasks can automatically retry on failure. To enable retries, pass `retries` and `retry_delay_seconds` parameters to your task:

```python hl_lines="3"
import requests
# this task will retry up to 3 times, waiting 1 minute between each retry
@task(retries=3, retry_delay_seconds=60)
def get_page(url):
    page = requests.get(url)
```

!!! note "Retries don't create new task runs"
    A new task run is not created when a task is retried. A new state is added to the state history of the original task run.

## Caching

Caching refers to the ability of a task run to reflect a finished state without actually running the code that defines the task. This allows you to efficiently reuse results of tasks that may be expensive to run with every flow run, or reuse cached results if the inputs to a task have not changed.

To determine whether a task run should retrieve a cached state, we use "cache keys". A cache key is a string value that indicates if one run should be considered identical to another. When a task run with a cache key finishes, we attach that cache key to the state. When each task run starts, Prefect checks for states with a matching cache key. If a state with an identical key is found, Prefect will use the cached state instead of running the task again.

To enable caching, specify a `cache_key_fn` &mdash; a function that returns a cache key &mdash; on your task. You may optionally provide a `cache_expiration` timedelta indicating when the cache expires. If you do not specify a `cache_expiration`, the cache key does not expire.

You can define a task that is cached based on its inputs by using the Prefect `task_input_hash`. This is a task cache key implementation that hashes all inputs to the task using a JSON or cloudpickle serializer. If the task inputs do not change, the cached results are used rather than running the task until the cache expires.

Note that, if any arguments are not JSON serializable, the pickle serializer is used as a fallback. If cloudpickle fails, `task_input_hash` returns a null key indicating that a cache key could not be generated for the given inputs.

In this example, until the `cache_expiration` time ends, as long as the input to `hello_task()` remains the same when it is called, the cached return value is returned. In this situation the task is not rerun. However, if the input argument value changes, `hello_task()` runs using the new input.

```python hl_lines="3 5"
from datetime import timedelta
from prefect import flow, task
from prefect.tasks import task_input_hash

@task(cache_key_fn=task_input_hash, cache_expiration=timedelta(days=1))
def hello_task(name_input):
    # Doing some work
    print("Saying hello")
    return "hello " + name_input

@flow
def hello_flow(name_input):
    hello_task(name_input)
```

Alternatively, you can provide your own function or other callable that returns a string cache key. A generic `cache_key_fn` is a function that accepts two positional arguments: 

- The first argument corresponds to the `TaskRunContext`, which stores task run metadata in the attributes `task_run_id`, `flow_run_id`, and `task`.
- The second argument corresponds to a dictionary of input values to the task. For example, if your task is defined with signature `fn(x, y, z)` then the dictionary will have keys `"x"`, `"y"`, and `"z"` with corresponding values that can be used to compute your cache key.

Note that the `cache_key_fn` is _not_ defined as a `@task`. 

```python hl_lines="3-5 7"
from prefect import task, flow

def static_cache_key(context, parameters):
    # return a constant
    return "static cache key"

@task(cache_key_fn=static_cache_key)
def cached_task():
    print('running an expensive operation')
    return 42

@flow
def test_caching():
    cached_task()
    cached_task()
    cached_task()
```

In this case, there's no expiration for the cache key, and no logic to change the cache key, so `cached_task()` only runs once.

<div class="terminal">
```bash hl_lines="2"
>>> test_caching()
running an expensive operation
>>> test_caching()
>>> test_caching()
```
</div>

When each task run requested to enter a `Running` state, it provided its cache key computed from the `cache_key_fn`.  The Orion backend identified that there was a COMPLETED state associated with this key and instructed the run to immediately enter the same COMPLETED state, including the same return values.  

A real-world example might include the flow run ID from the context in the cache key so only repeated calls in the same flow run are cached.

```python
def cache_within_flow_run(context, parameters):
    return f"{context.flow_run_id}-{task_input_hash(context, parameters)}"

@task(cache_key_fn=cache_within_flow_run)
def cached_task():
    print('running an expensive operation')
    return 42
```

!!! note "Task results, retries, and caching"
    Task results are cached in memory during a flow run and peristed to the location specified by the `PREFECT_LOCAL_STORAGE_PATH` setting. As a result, task caching between flow runs is currently limited to flow runs with access to that local storage path.

## Task results

Depending on how you call tasks, they can return different types of results and optionally engage the use of a [task runner](/concepts/task-runners/).

Any task can return:

- Data , such as `int`, `str`, `dict`, `list`, and so on &mdash;  this is the default behavior any time you call `your_task()`.
- [`PrefectFuture`](/api-ref/prefect/futures/#prefect.futures.PrefectFuture) &mdash;  this is achieved by calling [`your_task.submit()`](/concepts/task-runners/#using-a-task-runner). A `PrefectFuture` contains both _data_ and _State_
- Prefect [`State`](/api-ref/orion/schemas/states/)  &mdash; anytime you call your task or flow with the argument `return_state=True`, it will directly return a state you can use to build custom behavior based on a state change you care about, such as task or flow failing or retrying.

To run your task with a [task runner](/concepts/task-runners/), you must call the task with `.submit()`.

See [state returned values](/concepts/task-runners/#using-results-from-submitted-tasks) for examples.

!!! tip "Task runners are optional"
    If you just need the result from a task, you can simply call the task from your flow. For most workflows, the default behavior of calling a task directly and receiving a result is all you'll need.

## Map

Prefect provides a `.map()` implementation that automatically creates a task run for each element of its input data. Mapped tasks represent the computations of many individual children tasks.

The simplest Prefect map takes a tasks and applies it to each element of its inputs.

```python
from prefect import flow, task

@task
def print_nums(n):
    for n in nums:
        print(n)

@task
def square_num(num):
    return num**2

@flow
def map_flow(nums):
    print_nums(nums)
    squared_nums = square_num.map(nums) 
    print_nums(squared_nums)

map_flow([1,2,3,5,8,13])
```

Prefect also supports `unmapped` arguments, allowing you to pass static values that don't get mapped over.

```python
from prefect import flow, task

@task
def add_together(x, y):
    return x + y

@flow
def sum_it(numbers, static_value):
    futures = add_together.map(numbers, static_value)
    return futures

sum_it([1, 2, 3], 5)
```

If your static argument is an iterable, you'll need to wrap it with `unmapped` to tell Prefect that it should be treated as a static value.

```python
from prefect import flow, task, unmapped

@task
def sum_plus(x, static_iterable):
    return x + sum(static_iterable)

@flow
def sum_it(numbers, static_iterable):
    futures = sum_plus.map(numbers, static_iterable)
    return futures

sum_it([4, 5, 6], unmapped([1, 2, 3]))
```

## Async tasks

Prefect also supports asynchronous task and flow definitions by default. All of [the standard rules of async](https://docs.python.org/3/library/asyncio-task.html) apply:

```python
import asyncio

from prefect import task, flow

@task
async def print_values(values):
    for value in values:
        await asyncio.sleep(1) # yield
        print(value, end=" ")

@flow
async def async_flow():
    await print_values([1, 2])  # runs immediately
    coros = [print_values("abcd"), print_values("6789")]

    # asynchronously gather the tasks
    await asyncio.gather(*coros)

asyncio.run(async_flow())
```

Note, if you are not using `asyncio.gather`, calling [`.submit()`](/concepts/task-runners/#using-a-task-runner) is required for asynchronous execution on the `ConcurrentTaskRunner`.

## Task run concurrency limits

There are situations in which you want to actively prevent too many tasks from running simultaneously. For example, if many tasks across multiple flows are designed to interact with a database that only allows 10 connections, you want to make sure that no more than 10 tasks that connect to this database are running at any given time.

Prefect has built-in functionality for achieving this: task concurrency limits.

Task concurrency limits use [task tags](#tags). You can specify an optional concurrency limit as the maximum number of concurrent task runs in a `Running` state for tasks with a given tag. The specified concurrency limit applies to any task to which the tag is applied.

If a task has multiple tags, it will run only if _all_ tags have available concurrency. 

Tags without explicit limits are considered to have unlimited concurrency.

!!! note "0 concurrency limit aborts task runs"
    Currently, if the concurrency limit is set to 0 for a tag, any attempt to run a task with that tag will be aborted instead of delayed.

### Execution behavior

Task tag limits are checked whenever a task run attempts to enter a [`Running` state](/concepts/states). 

If there are no concurrency slots available for any one of your task's tags, the transition to a `Running` state will be delayed and the client is instructed to try entering a `Running` state again in 30 seconds. 

!!! warning "Concurrency limits in subflows"
    Using concurrency limits on task runs in subflows can cause deadlocks. As a best practice, configure your tags and concurrency limits to avoid setting limits on task runs in subflows.

### Configuring concurrency limits

You can set concurrency limits on as few or as many tags as you wish. You can set limits through the CLI or via API by using the `OrionClient`.

#### CLI

You can create, list, and remove concurrency limits by using Prefect CLI `concurrency-limit` commands.

```bash
$ prefect concurrency-limit [command] [arguments]
```

| Command | Description |
| --- | --- |
| create | Create a concurrency limit by specifying a tag and limit. |
| delete | Delete the concurrency limit set on the specified tag. |
| ls     | View all defined concurrency limits. |
| read   | View details about a concurrency limit. `active_slots` shows a list of IDs for task runs that are currently using a concurrency slot. |

For example, to set a concurrency limit of 10 on the 'small_instance' tag:

```bash
$ prefect concurrency-limit create small_instance 10
```

To delete the concurrency limit on the 'small_instance' tag:

```bash
$ prefect concurrency-limit delete small_instance
```

#### Python client

To update your tag concurrency limits programmatically, use [`OrionClient.create_concurrency_limit`](/api-ref/prefect/client/#prefect.client.OrionClient.create_concurrency_limit). 

`create_concurrency_limit` takes two arguments:

- `tag` specifies the task tag on which you're setting a limit.
- `concurrency_limit` specifies the maximum number of concurrent task runs for that tag.

For example, to set a concurrency limit of 10 on the 'small_instance' tag:

```python
from prefect.client import get_client

async with get_client() as client:
    # set a concurrency limit of 10 on the 'small_instance' tag
    limit_id = await client.create_concurrency_limit(
        tag="small_instance", 
        concurrency_limit=10
        )
```

To remove all concurrency limits on a tag, use [`OrionClient.delete_concurrency_limit_by_tag`](/api-ref/prefect/client/#prefect.client.OrionClient.delete_concurrency_limit_by_tag), passing the tag:

```python
async with get_client() as client:
    # remove a concurrency limit on the 'small_instance' tag
    await client.delete_concurrency_limit_by_tag(tag="small_instance")
```

If you wish to query for the currently set limit on a tag, use [`OrionClient.read_concurrency_limit_by_tag`](/api-ref/prefect/client/#prefect.client.OrionClient.read_concurrency_limit_by_tag), passing the tag:

To see _all_ of your limits across all of your tags, use [`OrionClient.read_concurrency_limits`](/api-ref/prefect/client/#prefect.client.OrionClient.read_concurrency_limits).

```python
async with get_client() as client:
    # query the concurrency limit on the 'small_instance' tag
    limit = await client.read_concurrency_limit_by_tag(tag="small_instance")
```

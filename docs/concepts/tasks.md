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

Tasks also take advantage of automatic Prefect [logging](/concepts/logs/) to capture details about task runs such as runtime, tags, and final state. 

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
| `name` | An optional name for the task. If not provided, the name will be inferred from the function name. |
| `description` | An optional string description for the task. If not provided, the description will be pulled from the docstring for the decorated function. |
| `tags` | An optional set of tags to be associated with runs of this task. These tags are combined with any tags defined by a `prefect.tags` context at task runtime. |
| `cache_key_fn` | An optional callable that, given the task run context and call parameters, generates a string key. If the key matches a previous completed state, that state result will be restored instead of running the task again. |
| `cache_expiration` | An optional amount of time indicating how long cached states for this task should be restorable; if not provided, cached states will never expire. |
| `task_run_name` | An optional name to distinguish runs of this task; this name can be provided as a string template with the task's keyword arguments as variables. |
| `retries` | An optional number of times to retry on task run failure. |
| `retry_delay_seconds` | An optional number of seconds to wait before retrying the task after failure. This is only applicable if `retries` is nonzero. |
| `version` | An optional string specifying the version of this task definition. |

For example, you can provide a `name` value for the task. Here we've used the optional `description` argument as well.

```python hl_lines="1"
@task(name="hello-task", 
      description="This task says hello.")
def my_task():
    print("Hello, I'm a task")
```

You can distinguish runs of this task by providing a `task_run_name`; this setting accepts a string that can optionally contain templated references to the keyword arguments of your task. The name will be formatted using Python's standard string formatting syntax as can be seen here:

```python
import datetime
from prefect import flow, task

@task(name="My Example Task", 
      description="An example task for a tutorial.",
      task_run_name="hello-{name}-on-{date:%A}")
def my_task(name, date):
    pass

@flow
def my_flow():
    # creates a run with a name like "hello-marvin-on-Thursday"
    my_task(name="marvin", date=datetime.datetime.utcnow())
```

## Tags

Tags are optional string labels that enable you to identify and group tasks other than by name or flow. Tags are useful for:

- Filtering task runs by tag in the UI and via the [Prefect REST API](/api-ref/rest-api/#filtering).
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

Prefect tasks can automatically retry on failure. To enable retries, pass `retries` and `retry_delay_seconds` parameters to your task. This task will retry up to 3 times, waiting 60 seconds between each retry:

```python hl_lines="4"
import requests
from prefect import task, flow

@task(retries=3, retry_delay_seconds=60)
def get_page(url):
    page = requests.get(url)
```

When configuring task retries, you can configure a specific delay for each retry. The `retry_delay_seconds` option accepts a list of delays for custom retry behavior. The following task will wait for successively increasing intervals of 1, 10, and 100 seconds, respectively, before the next attempt starts:

```python
from prefect import task, flow

@task(retries=3, retry_delay_seconds=[1, 10, 100])
```

Additionally, you can pass a callable that accepts the number of retries as an argument and returns a list. Prefect includes an [`exponential_backoff`](/api-ref/prefect/tasks/#prefect.tasks.exponential_backoff) utility that will automatically generate a list of retry delays that correspond to an exponential backoff retry strategy. The following flow will wait for 10, 20, then 40 seconds before each retry.

```python
from prefect import task, flow
from prefect.tasks import exponential_backoff

@task(retries=3, retry_delay_seconds=exponential_backoff(backoff_factor=10))
```

While using exponential backoff you may also want to jitter the delay times to prevent "thundering herd" scenarios, where many tasks all retry at exactly the same time, causing cascading failures. The `retry_jitter_factor` option can be used to add variance to the base delay. For example, a retry delay of 10 seconds with a `retry_jitter_factor` of 0.5 will be allowed to delay up to 15 seconds. Large values of `retry_jitter_factor` provide more protection against "thundering herds", while keeping the average retry delay time constant. For example, the following task adds jitter to its exponential backoff so the retry delays will vary up to a maximum delay time of 20, 40, and 80 seconds respectively.

```python
from prefect import task, flow
from prefect.tasks import exponential_backoff

@task(
    retries=3,
    retry_delay_seconds=exponential_backoff(backoff_factor=10),
    retry_jitter_factor=1,
)
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

!!! note "Task cache keys"
    By default, a task cache key is limited to 2000 characters, specified by the `PREFECT_API_TASK_CACHE_KEY_MAX_LENGTH` setting.

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

When each task run requested to enter a `Running` state, it provided its cache key computed from the `cache_key_fn`.  The Prefect backend identified that there was a COMPLETED state associated with this key and instructed the run to immediately enter the same COMPLETED state, including the same return values.  

A real-world example might include the flow run ID from the context in the cache key so only repeated calls in the same flow run are cached.

```python
def cache_within_flow_run(context, parameters):
    return f"{context.task_run.flow_run_id}-{task_input_hash(context, parameters)}"

@task(cache_key_fn=cache_within_flow_run)
def cached_task():
    print('running an expensive operation')
    return 42
```

!!! note "Task results, retries, and caching"
    Task results are cached in memory during a flow run and persisted to the location specified by the `PREFECT_LOCAL_STORAGE_PATH` setting. As a result, task caching between flow runs is currently limited to flow runs with access to that local storage path.

### Refreshing the cache

Sometimes, you want a task to update the data associated with its cache key instead of using the cache. This is a cache "refresh".

The `refresh_cache` option can be used to enable this behavior for a specific task:

```python
import random


def static_cache_key(context, parameters):
    # return a constant
    return "static cache key"


@task(cache_key_fn=static_cache_key, refresh_cache=True)
def caching_task():
    return random.random()
```

When this task runs, it will _always_ update the cache key instead of using the cached value. This is particularly useful when you have a flow that is responsible for updating the cache.

If you want to refresh the cache for all tasks, you can use the `PREFECT_TASKS_REFRESH_CACHE` setting. Setting `PREFECT_TASKS_REFRESH_CACHE=true` will change the default behavior of all tasks to refresh. This is particularly useful if you want to rerun a flow without cached results.

If you have tasks that should not refresh when this setting is enabled, you may explicitly set `refresh_cache` to `False`. These tasks will never refresh the cache &mdash; if a cache key exists it will be read, not updated. Note that, if a cache key does _not_ exist yet, these tasks can still write to the cache.

```python
@task(cache_key_fn=static_cache_key, refresh_cache=False)
def caching_task():
    return random.random()
```

## Timeouts

Task timeouts are used to prevent unintentional long-running tasks. When the duration of execution for a task exceeds the duration specified in the timeout, a timeout exception will be raised and the task will be marked as failed. In the UI, the task will be visibly designated as `TimedOut`. From the perspective of the flow, the timed-out task will be treated like any other failed task. 

Timeout durations are specified using the `timeout_seconds` keyword argument. 

```python
from prefect import task, get_run_logger
import time

@task(timeout_seconds=1)
def show_timeouts():
    logger = get_run_logger()
    logger.info("I will execute")
    time.sleep(5)
    logger.info("I will not execute")
```

## Task results

Depending on how you call tasks, they can return different types of results and optionally engage the use of a [task runner](/concepts/task-runners/).

Any task can return:

- Data , such as `int`, `str`, `dict`, `list`, and so on &mdash;  this is the default behavior any time you call `your_task()`.
- [`PrefectFuture`](/api-ref/prefect/futures/#prefect.futures.PrefectFuture) &mdash;  this is achieved by calling [`your_task.submit()`](/concepts/task-runners/#using-a-task-runner). A `PrefectFuture` contains both _data_ and _State_
- Prefect [`State`](/api-ref/server/schemas/states/)  &mdash; anytime you call your task or flow with the argument `return_state=True`, it will directly return a state you can use to build custom behavior based on a state change you care about, such as task or flow failing or retrying.

To run your task with a [task runner](/concepts/task-runners/), you must call the task with `.submit()`.

See [state returned values](/concepts/task-runners/#using-results-from-submitted-tasks) for examples.

!!! tip "Task runners are optional"
    If you just need the result from a task, you can simply call the task from your flow. For most workflows, the default behavior of calling a task directly and receiving a result is all you'll need.

## Wait for
To create a dependency between two tasks that do not exchange data, but one needs to wait for the other to finish, use the special [`wait_for`](/api-ref/prefect/tasks/#prefect.tasks.Task.submit) keyword argument:

```python
@task
def task_1():
    pass

@task
def task_2():
    pass

@flow
def my_flow():
    x = task_1()

    # task 2 will wait for task_1 to complete
    y = task_2(wait_for=[x])
```

## Map

Prefect provides a `.map()` implementation that automatically creates a task run for each element of its input data. Mapped tasks represent the computations of many individual children tasks.

The simplest Prefect map takes a tasks and applies it to each element of its inputs.

```python
from prefect import flow, task

@task
def print_nums(nums):
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

Task tag limits are checked whenever a task run attempts to enter a [`Running` state](/concepts/states/). 

If there are no concurrency slots available for any one of your task's tags, the transition to a `Running` state will be delayed and the client is instructed to try entering a `Running` state again in 30 seconds. 

!!! warning "Concurrency limits in subflows"
    Using concurrency limits on task runs in subflows can cause deadlocks. As a best practice, configure your tags and concurrency limits to avoid setting limits on task runs in subflows.

### Configuring concurrency limits

You can set concurrency limits on as few or as many tags as you wish. You can set limits through:

- Prefect [CLI](#cli)
- Prefect API by using `PrefectClient` [Python client](#python-client)
- [Prefect server UI](/ui/task-concurrency/) or Prefect Cloud

#### CLI

You can create, list, and remove concurrency limits by using Prefect CLI `concurrency-limit` commands.

```bash
$ prefect concurrency-limit [command] [arguments]
```

| Command | Description |
| --- | --- |
| create | Create a concurrency limit by specifying a tag and limit. |
| delete | Delete the concurrency limit set on the specified tag. |
| inspect | View details about a concurrency limit set on the specified tag. |
| ls     | View all defined concurrency limits. |

For example, to set a concurrency limit of 10 on the 'small_instance' tag:

```bash
$ prefect concurrency-limit create small_instance 10
```

To delete the concurrency limit on the 'small_instance' tag:

```bash
$ prefect concurrency-limit delete small_instance
```

To view details about the concurrency limit on the 'small_instance' tag:

```bash
$ prefect concurrency-limit inspect small_instance
```

#### Python client

To update your tag concurrency limits programmatically, use [`PrefectClient.create_concurrency_limit`](/api-ref/prefect/client/#prefect.client.PrefectClient.create_concurrency_limit). 

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

To remove all concurrency limits on a tag, use [`PrefectClient.delete_concurrency_limit_by_tag`](/api-ref/prefect/client/#prefect.client.PrefectClient.delete_concurrency_limit_by_tag), passing the tag:

```python
async with get_client() as client:
    # remove a concurrency limit on the 'small_instance' tag
    await client.delete_concurrency_limit_by_tag(tag="small_instance")
```

If you wish to query for the currently set limit on a tag, use [`PrefectClient.read_concurrency_limit_by_tag`](/api-ref/prefect/client/#prefect.client.PrefectClient.read_concurrency_limit_by_tag), passing the tag:

To see _all_ of your limits across all of your tags, use [`PrefectClient.read_concurrency_limits`](/api-ref/prefect/client/#prefect.client.PrefectClient.read_concurrency_limits).

```python
async with get_client() as client:
    # query the concurrency limit on the 'small_instance' tag
    limit = await client.read_concurrency_limit_by_tag(tag="small_instance")
```

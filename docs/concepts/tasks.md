# Tasks

A task is a function that represents a discrete unit of work in a Prefect workflow. Tasks are not required &mdash; you may define Prefect workflows that consist only of flows &mdash; but tasks enable you to encapsulate elements of your workflow logic that can be reused across flows and subflows. 

## Tasks overview

Tasks are functions: they can take inputs, perform work, and return an output. A Prefect task can do almost a Python function can do.  

Tasks are special because they receive metadata about upstream dependencies and the state of those dependencies before they run, even if they don't receive any explicit data inputs from them. This gives you the opportunity to, for example, have a task wait on the completion of another task before executing.

Tasks also take advantage of automatic Prefect [logging](/concepts/logs.md) to capture details about task runs such as runtime and final state. 

Tasks may call other tasks, but all task runs occur within the context of a flow run.

That said, you can define your tasks within the same file as your flow definition, or you can define tasks within modules and import them for use in your flow definitions. 

For most use cases, we recommend using the `@task` decorator to designate a function as a task. Calling the task from within a flow function creates a new task run:

```python hl_lines="3"
from prefect import flow, task

@task
def my_task():
    print("Hello, I'm a task")

@flow
def my_flow():
    my_task()
```

!!! note "How big should a task be?"
    People often wonder how much code to put in each task.

    Prefect encourages "small tasks" &mdash; each one should represent a single logical step of your workflow. This allows Prefect to better contain task failures.

    To be clear, there's nothing stopping you from putting all of your code in a single task &mdash; Prefect will happily run it! However, if any line of code fails, the entire task will fail and must be retried from the beginning. This can be trivially avoided by splitting the code into multiple dependent tasks.
:::

## Task arguments

Tasks allow a great deal of customization via arguments. Examples include retry behavior, names, tags, caching, and more. Tasks accept the following optional arguments.

| Argument | Description |
| --- | --- |
| name | An optional name for the task. If not provided, the name will be inferred from the function name. |
| description | An optional string description for the task. |
| tags | An optional set of tags to be associated with runs of this task. These tags are combined with any tags defined by a `prefect.tags` context at task runtime. |
| cache_key_fn | An optional callable that, given the task run context and call parameters, generates a string key. If the key matches a previous completed state, that state result will be restored instead of running the task again. |
| cache_expiration | An optional amount of time indicating how long cached states for this task should be restorable; if not provided, cached states will never expire. |
| retries | An optional number of times to retry on task run failure. |
| retry_delay_seconds | An optional number of seconds to wait before retrying the task after failure. This is only applicable if `retries` is nonzero. |

For example, tasks can be uniquely identified by name. You can provide a `name` value for the task, but if not provided, the function name is used. Here we've used the optional `description` argument as well.

```python hl_lines="1"
@task(name="hello-task", description="This task says hello.")
def my_task():
    print("Hello, I'm a task")
```

## Tags

Sometimes, it is useful to group tasks in ways other than by name or flow context. Prefect provides tags for this purpose. 

Tags may be specified as an optional keyword argument on the task decorator.

```python hl_lines="1"
@task(name="hello-task", tags=["test"])
def my_task():
    print("Hello, I'm a task")
```

You can also provide tags as an argument with a context manager, specifying tags when the task is called rather than in its definition.

```python
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

A key capability of Prefect tasks is the ability to automatically retry on failure. To enable retries, pass `retries` and `retry_delay_seconds` parameters to your task:

```python
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

You must specify a `cache_key_fn` that returns a cache key. You may optionally provide a `cache_expiration` timedelta indicating when the cache expires. If you do not specify a `cache_expiration`, the cache key does not expire.

You can define a task that is cached based on its inputs by using the Prefect `task_input_hash`. This is a task cache key implementation that hashes all inputs to the task using a JSON or cloudpickle serializer. If the task inputs do not change, the cached results are used rather than running the task until the cache expires.

Note that, if any arguments are not JSON serializable, the pickle serializer is used as a fallback. If cloudpickle fails, `task_input_hash` returns a null key indicating that a cache key could not be generated for the given inputs.

In this example, until the `cache_expiration` time ends, as long as the input to `hello_task()` remains the same when it is called, it runs only once, but the cached return value will be returned. However, if the input argument value changes, `hello_task()` runs using that input.

```python
from prefect.tasks import task_input_hash
from datetime import timedelta

@task(cache_key_fn=task_input_hash, cache_expiration=timedelta(days=1))
def hello_task(name_input):
    # Doing some work
    print("Saying hello")
    return "hello " + name_input

@flow
def hello_flow():
    hello_task(name_input)
```

You can also provide your own function or other callable that returns a string cache key.

```python
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

<div class="termy">
```
>>> test_caching()
running an expensive operation
>>> test_caching()
>>> test_caching()
```
</div>

Whenever each task run requested to enter a `Running` state, it provided its cache key computed from the `cache_key_fn`.  The Orion backend identified that there was a COMPLETED state associated with this key and instructed the run to immediately enter the same state, including the same return values.  

Caching can be configured further in the following ways:

A generic `cache_key_fn` is a function that accepts two positional arguments: 

- The first argument corresponds to the `TaskRunContext`, which is a basic object with attributes `task_run_id`, `flow_run_id`, and `task`.
- The second argument corresponds to a dictionary of input values to the task. For example, if your task is defined with signature `fn(x, y, z)` then the dictionary will have keys `"x"`, `"y"`, and `"z"` with corresponding values that can be used to compute your cache key.




            Wait for a task to finish

            >>> @flow
            >>> def my_flow():
            >>>     my_task().wait()

            Use the result from a task in a flow

            >>> @flow
            >>> def my_flow():
            >>>     print(my_task().wait().result)
            >>>
            >>> my_flow()
            hello

            Run an async task in an async flow

            >>> @task
            >>> async def my_async_task():
            >>>     pass
            >>>
            >>> @flow
            >>> async def my_flow():
            >>>     await my_async_task()

            Run a sync task in an async flow

            >>> @flow
            >>> async def my_flow():
            >>>     my_task()

            Enforce ordering between tasks that do not exchange data
            >>> @task
            >>> def task_1():
            >>>     pass
            >>>
            >>> @task
            >>> def task_2():
            >>>     pass
            >>>
            >>> @flow
            >>> def my_flow():
            >>>     x = task_1()
            >>>
            >>>     # task 2 will wait for task_1 to complete
            >>>     y = task_2(wait_for=[x])








## Constants

If a non-`Task` input is provided to a task, it is automatically converted to a `Constant`.

```python
from prefect import Flow, task

@task
def add(x, y):
    return x + y

with Flow('Flow With Constant') as flow:
    add(1, 2)

assert len(flow.tasks) == 1
assert len(flow.constants) == 2
```

Prefect will attempt to automatically turn Python objects into `Constants`, including collections (like `lists`, `tuples`, `sets`, and `dicts`). If the resulting constant is used directly as the input to a task, it is optimized out of the task graph and stored in the `flow.constants` dict. However, if the constant is mapped over, then it remains in the dependency graph.


## Collections

When using the [functional API](flows.html#functional-api), Prefect tasks can automatically be used in collections. For example:

```python
import random
from prefect import Flow, task

@task
def a_number():
    return random.randint(0, 100)

@task
def get_sum(x):
    return sum(x)

with Flow('Using Collections') as flow:
    a = a_number()
    b = a_number()
    s = get_sum([a, b])
```

In this case, a `List` task will automatically be created to take the results of `a` and `b` and put them in a list. That automatically-created task becomes the sole upstream dependency of `s`.

Prefect will perform automatic collection extraction for lists, tuples, sets, and dictionaries.

## Indexing

When using the [functional API](flows.html#functional-api), Prefect tasks can be indexed to retrieve specific results.

```python
from prefect import Flow, task

@task
def fn():
    return {'a': 1, 'b': 2}


with Flow('Indexing Flow') as flow:
    x = fn()
    y = x['a']
```

This will automatically add a `GetItem` task to the flow that receives `x` as its input and attempts to perform `x['a']`. The result of that task (`1`) is stored as `y`.

::: warning Key validation
Because Prefect flows are not executed at runtime, Prefect can not validate that the indexed key is available ahead of time. Therefore, Prefect will allow you to index any task by any value. If the key does not exist when the flow is actually run, a runtime error will be raised.
:::

## Multiple Return Values

Sometimes your task may have multiple return values that you want to deal with
separately. By default Prefect tasks aren't iterable, so the standard Python
pattern will error:

```python
from prefect import Flow, task

@task
def inc_and_dec(x):
    return x + 1, x - 1

with Flow("This Errors") as flow:
    # This raises a TypeError, since Prefect doesn't know how many values
    # `inc_and_dec` returns
    inc, dec = inc_and_dec(1)
```

To make this work, you need to let Prefect know how many return values your
task has. You can do this by either:

- Passing in `nout` to the `@task` decorator or the `Task` constructor when defining your task.
- Providing a return type annotation for your task (in a class-based task, this
  would go on the `run` method).

For example:

```python
# Passing in `nout` explicitly
@task(nout=2)
def inc_and_dec(x):
    return x + 1, x - 1

# Using a return type annotation
from typing import Tuple

@task
def double_and_triple(x: int) -> Tuple[int, int]:
    return x * 2, x * 3

with Flow("This works") as flow:
    inc, dec = inc_and_dec(1)
    double, triple = double_and_triple(inc)
```

Note that multiple return values can also be used by explicitly indexing tasks
(as described above). Providing `nout` or a return type annotation only adds
the convenience of tuple unpacking.

## Mapping

_For more detail, see the [mapping concept docs](mapping.html)._

Generally speaking, Prefect's [functional API](flows.html#functional-api) allows you to call a task like a function.

In addition, you can call `Task.map()` to automatically map a task over its inputs. Prefect will generate a dynamic copy of the task for each element of the input. If you don't want an input to be treated as iterable (for example, you want to provide it to every dynamic copy), just wrap it with Prefect's `unmapped()` annotation.

```python
from prefect import task, unmapped

@task
def add(x, y):
    return x + y

add.map(x=[1, 2, 3], y=unmapped(1))
```

Maps can be composed, allowing the creation of powerful dynamic pipelines:

```python
z1 = add.map(x=[1, 2, 3], y=unmapped(1))
z2 = add.map(x=z1, y=unmapped(100))
```

In addition, if the result of a mapped task is passed to an un-mapped task (or used as the `unmapped` input to a mapped task), then its results will be collected in a list. This allows transparent but totally flexible map/reduce functionality.

## Flattening

_For more detail, see the [mapping concept docs](mapping.html)._

To "un-nest" a task that returns a list of lists, use Prefect's `flatten()` annotation. This is most useful when a task in a mapped pipeline returns a sequence.







### Retrieving tasks

While identifying attributes are most useful when querying for tasks in Prefect Cloud and applying some advanced tag-based features, they can be used locally with a flow's `get_tasks()` function. This will return any tasks that match all of the provided arguments. For example:

```python
flow.get_tasks(name='my-task')
flow.get_tasks(tags=['red'])
```

## State handlers

State handlers allow users to provide custom logic that fires whenever a task changes state. For example, you could send a Slack notification if the task failed -- we actually think that's so useful we included it [here](/api/latest/utilities/notifications.html#functions)!

State handlers must have the following signature:

```python
state_handler(task: Task, old_state: State, new_state: State) -> State
```

The handler is called anytime the task's state changes, and receives the task itself, the old state, and the new state. The state that the handler returns is used as the task's new state.

If multiple handlers are provided, they are called in sequence. Each one will receive the "true" `old_state` and the `new_state` generated by the previous handler.

Handlers can also be associated with the `Flow`, `TaskRunner`, and `FlowRunner` classes. The task-level handlers are called first.

## Caching

Tasks can be cached, in which case their outputs will be reused for future runs. For example, you might want to make sure that a database is loaded before generating reports, but you might not want to run the load task every time the flow is run. No problem: just cache the load task for 24 hours, and future runs will reuse its successful output.

For more details, see the relevant docs under [execution](./execution.html#caching).


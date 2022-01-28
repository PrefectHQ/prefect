# Tasks

A task is a function that represents a discrete unit of work in a Prefect workflow. Tasks are not required &mdash; you may define Prefect workflows that consist only of flows, using regular Python statements and functions. Tasks enable you to encapsulate elements of your workflow logic in observable units that can be reused across flows and subflows. 

## Tasks overview

Tasks are functions: they can take inputs, perform work, and return an output. A Prefect task can do almost anything a Python function can do.  

Tasks are special because they receive metadata about upstream dependencies and the state of those dependencies before they run, even if they don't receive any explicit data inputs from them. This gives you the opportunity to, for example, have a task wait on the completion of another task before executing.

Tasks also take advantage of automatic Prefect [logging](/concepts/logs.md) to capture details about task runs such as runtime, tags, and final state. 

You can define your tasks within the same file as your flow definition, or you can define tasks within modules and import them for use in your flow definitions. All tasks must be called from within a flow. Tasks may not be called from other tasks.

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

Task calls return a [`PrefectFuture`](/api-ref/prefect/futures/#prefect.futures.PrefectFuture), which represents the status of a task executing in a task runner. See [Futures](#futures) for further information.

The future can be used to retrieve the current [`State`](/api-ref/orion/schemas/states/#prefect.orion.schemas.states.State) of the task run or wait for the task run to enter a final state. See [States](/concepts/states/) for further information.

!!! note "How big should a task be?"
    Prefect encourages "small tasks" &mdash; each one should represent a single logical step of your workflow. This allows Prefect to better contain task failures.

    To be clear, there's nothing stopping you from putting all of your code in a single task &mdash; Prefect will happily run it! However, if any line of code fails, the entire task will fail and must be retried from the beginning. This can be avoided by splitting the code into multiple dependent tasks.

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

For example, you can provide a `name` value for the task. Here we've used the optional `description` argument as well.

```python hl_lines="1"
@task(name="hello-task", description="This task says hello.")
def my_task():
    print("Hello, I'm a task")
```

## Tags

Sometimes, it is useful to group tasks in ways other than by name or flow. Prefect provides tags for this purpose. 

Tags may be specified as an optional keyword argument on the task decorator.

```python hl_lines="1"
@task(name="hello-task", tags=["test"])
def my_task():
    print("Hello, I'm a task")
```

You can also provide tags as an argument with a context manager, specifying tags when the task is called rather than in its definition.

```python hl_lines="9"
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

To determine whether a task run should retrieve a cached state, we use "cache keys". A cache key is a string value that indicates if a run should be considered identical to another. When a task run with a cache key finishes, we attach that cache key to the state. When each task run starts, we will look for states with a matching cache key. If we find a state with an identical key, we will use the cached state instead of running the task again.

You must specify a `cache_key_fn` that returns a cache key. You may optionally provide a `cache_expiration` timedelta indicating when the cache expires. If you do not specify a `cache_expiration`, the cache key does not expire.

You can define a task that is cached based on its inputs by using the Prefect `task_input_hash`. This is a task cache key implementation that hashes all inputs to the task using a JSON or cloudpickle serializer. If the task inputs do not change, the cached results are used rather than running the task until the cache expires.

Note that, if any arguments are not JSON serializable, the pickle serializer is used as a fallback. If cloudpickle fails, `task_input_hash` returns a null key indicating that a cache key could not be generated for the given inputs.

In this example, until the `cache_expiration` time ends, as long as the input to `hello_task()` remains the same when it is called, it runs only once, but the cached return value will be returned. However, if the input argument value changes, `hello_task()` runs using that input.

```python hl_lines="1 4"
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

You can also provide your own function or other callable that returns a string cache key. A generic `cache_key_fn` is a function that accepts two positional arguments: 

- The first argument corresponds to the `TaskRunContext`, which stores task run metadata in the attributes `task_run_id`, `flow_run_id`, and `task`.
- The second argument corresponds to a dictionary of input values to the task. For example, if your task is defined with signature `fn(x, y, z)` then the dictionary will have keys `"x"`, `"y"`, and `"z"` with corresponding values that can be used to compute your cache key.

Note that the `cache_key_fn` is _not_ defined as a `@task`. 

```python hl_lines="1-5"
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

## Using results from tasks

By default, Prefect attempts to create an execution graph for the tasks in your flow based on data dependencies. 

When tasks are called, they are submitted to a task runner, which creates a future for access to the state and result of the task. A [`PrefectFuture`](/api-ref/prefect/futures/#prefect.futures.PrefectFuture) provides access to a computation happening in a task runner.

```python
@task
def say_hello(name):
    return f"Hello {name}!"

@flow
def hello_world():
    future = say_hello("Marvin")
    print(f"variable 'future' is type {type(future)}")
```

You'll see that, in the context of a flow, the variable `future` is a `PrefectFuture`.

<div class="termy">
```
>>> hello_world()
variable 'future' is type <class 'prefect.futures.PrefectFuture'>
```
</div>

But if we pass `future` to another task, the task receives only the value as a variable:

```python
@task
def print_result(result):
    print(type(result))
    print(result)

...

@flow(name="hello-flow")
def hello_world():
    future = say_hello("Marvin")
    print_result(future)
```

<div class="termy">
```
>>> hello_world()
<class 'str'>
Hello Marvin!
```
</div>

When you pass a future into a task, we will wait for the upstream task it references to reach a final state before starting the downstream task.

Futures have a few useful methods. For example, [`get_state()`](/api-ref/prefect/futures/#prefect.futures.PrefectFuture.get_state) retrieves the current state of the task run associated with a `PrefectFuture`.

```python
@flow
def my_flow():
    future = my_task()
    state = future.get_state()
```

You can also wait for a task to complete by using the [`wait()`](/api-ref/prefect/futures/#prefect.futures.PrefectFuture.wait) method and retrieve the task's result:

```python
@flow
def my_flow():
    future = my_task()
    final_state = future.wait()
    result = final_state.result()
```

You may also use the [`wait_for=[]`](/api-ref/prefect/tasks/#prefect.tasks.Task.__call__) parameter when calling a task, specifying upstream task dependencies. This enables you to control task execution order for tasks that do not share data dependencies.

```python
@task
def task_a():
    pass

@task
def task_b():
    pass

@task
def task_c():
    pass
    
@task
def task_d():
    pass

@flow
def my_flow():
    a = task_a()
    b = task_b()
    # Wait for task_a and task_2 to complete
    c = task_c(wait_for=[a, b])
    # If waiting for one task it must still be in a list
    # task_d will wait for task_c to complete
    d = task_d(wait_for=[c])
```

## Async tasks

Coming soon.

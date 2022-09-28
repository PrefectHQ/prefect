---
description: Prefect results capture the data returned from your flows and tasks.
tags:
    - flows
    - subflows
    - tasks
    - states
    - results
---

# Results

Results represent the data returned by a flow or a task. 

## Retrieving results

When **calling** flows or tasks, the result is returned directly:

```python
from prefect import flow, task

@task
def my_task():
    return 1

@flow
def my_flow():
    task_result = my_task()
    return task_result + 1

result = my_flow()
assert result == 2
```

When working with flow and task states, the result can be retreived with the `State.result()` method:

```python
from prefect import flow, task

@task
def my_task():
    return 1

@flow
def my_flow():
    state = my_task(return_state=True)
    return state.result() + 1

state = my_flow(return_state=True)
assert state.result() == 2
```

When submitting tasks to a runner, the result can be retreived with the `Future.result()` method:

```python
from prefect import flow, task

@task
def my_task():
    return 1

@flow
def my_flow():
    future = my_task.submit()
    return future.result() + 1

result = my_flow())
assert result == 2
```

### Handling failures

Sometimes your flows or tasks will encounter an **exception**. Prefect captures all exceptions in order to report states to the orchestrator, but we do not hide them from you (unless you ask us to) as your program needs to know if an unexpected error has occurred.

When **calling** flows or tasks, the exceptions are raised as in normal Python:

```python
from prefect import flow, task

@task
def my_task():
    raise ValueError()

@flow
def my_flow():
    try:
        my_task()
    except ValueError:
        print("Oh no! The task failed.")
    
    return True

my_flow()
```

If you would prefer to check for a failed task without using `try/except`, you may ask Prefect to return the state:

```python
from prefect import flow, task

@task
def my_task():
    raise ValueError()

@flow
def my_flow():
    state = my_task(return_state=True)

    if state.is_failed():
        print("Oh no! The task failed. Falling back to '1'.")
        result = 1
    else:
        result = state.result()

    return result + 1

result = my_flow()
assert result == 2
```

If you retrieve the result from a failed state, the exception will be raised. For this reason, it's often best to check if the state is failed first. 

```python
from prefect import flow, task

@task
def my_task():
    raise ValueError()

@flow
def my_flow():
    state = my_task(return_state=True)

    try:
        result = state.result()
    except ValueError:
        print("Oh no! The state raised the error!")
    
    return True

my_flow()
```

When retrieving the result from a state, you can ask Prefect not to raise exceptions:

```python
from prefect import flow, task

@task
def my_task():
    raise ValueError()

@flow
def my_flow():
    state = my_task(return_state=True)

    maybe_result = state.result(raise_on_failure=False)
    if isinstance(maybe_result, ValueError):"
        print("Oh no! The task failed. Falling back to '1'.")
        result = 1
    else:
        result = maybe_result
    
    return result + 1

result = my_flow()
assert result == 2
```

When submitting tasks to a runner, `Future.result()` works the same as `State.result()`:

```python
from prefect import flow, task

@task
def my_task():
    raise ValueError()

@flow
def my_flow():
    future = my_task.submit()

    try:
        future.result()
    except ValueError:
        print("Ah! Futures will raise the failure as well.")

    # You can ask it not to raise the exception too
    maybe_result = future.result(raise_on_failure=False)
    print(f"Got {type(maybe_result)}")

    return True

my_flow()
```

## Persisting results

The Prefect API does not store your results [except in special cases](#storage-of-results-in-prefect). Instead, the result is **persisted** to a storage location in your infrastructure and Prefect stores a **reference** to the result.

The following Prefect features require results to be persisted:

- Task cache keys
- Flow run retries

If results are not persisted, these features will not be usable.

### Configuring results

Persistence of results requires a [**serializer**](#result-serializers) and a [**storage** location](#result-storage). Prefect sets defaults for these, and you should not need to adjust them until you want to customize behavior.

#### Configuring results for flows

The `flow` decorator provides result configuration options.

By default, flows will not persist their own result. However, configuration at the flow level sets the default for all tasks in the flow.

You may set the result storage using an instance:

```python
from prefect import flow
from prefect.filesystems import LocalFileSystem

@flow(result_storage=LocalFileSystem(basepath=".results"))
```

You may set the result storage using a block id:

```python
from prefect import flow
from prefect.filesystems import LocalFileSystem

@flow(result_storage='cae1dda0-5000-4ca2-a18c-727d400145f2')
```

Or you may **disable** result storage by setting it to a null value:

```python
from prefect import flow
from prefect.filesystems import LocalFileSystem

@flow(result_storage=None)
```

#### Configuring results for tasks

By default, tasks will persist results to the local file system if required by a feature enabled on the flow. For example, if you enable retries on the flow we will persist task run results. Otherwise, your retries will be unable to restore completed task runs from the previous attempt.
### Result storage

Result storage is responsible fo reading and writing serialized data to an external location. At this time, any file system block can be used for result storage.

### Result serializers

A result serializer is responsible for converting your Python object to and from bytes. This is necessary to store the object outside of Python and retrieve it later.

#### Pickle serializer

Pickle is a standard Python protocol for encoding arbitrary Python objects. We supply a custom Pickle serializer at `prefect.serializers.PickleSerializer`. Prefect's pickle serializer uses the [cloudpickle](https://github.com/cloudpipe/cloudpickle) project by default to support more object types. Alternative pickle libraries can be specified:

```python
from prefect.serializers import PickleSerializer

PickleSerializer(picklelib="custompickle")
```

Benefits of the pickle serializer:

- Many object types are supported
- Objects can define custom pickle support

Drawbacks of the pickle serializer:

- When nested attributes of an object cannot be pickled, it is hard to determine the cause
- When deserializing objects, your Python and pickle library versions must match the one used at serialization time
- Serialized objects cannot be easily shared across different programming languages
- Serialized objects are not human readable

#### JSON serializer


We supply a custom JSON serializer at `prefect.serializers.JSONSerializer`. Prefect's JSON serializer uses custom hooks by default to support more object types. Specifically, we add support for all types supported by [Pydantic](https://pydantic-docs.helpmanual.io/). 


By default, we use the standard Python `json` library. Alternative JSON libraries can be specified:

```python
from prefect.serializers import JSONSerializer

JSONSerializer(jsonlib="orjson")
```

Benefits of the JSON serializer:

- Serialized objects are human readable
- Serialized objects can often be shared across different programming languages
- Deserialization of serialized objects is generally version agnostic

Drawbacks of the JSON serializer:

- Supported types are limited
- Implementing support for additional types must be done at the serializer level

### Result references

Result references contain all of the information needed to retrieve the result from storage. This includes:

- Storage: a reference to the [result storage](#result-storage) that can be used to read the serialized result
- Key: indicates where this specific result is in storage
- Serializer: description of the [result serializer](#result-serializers) that can be used to deserialize the result

Result references implement the `get()` method which retrieves the data from storage, deserializes it, and returns the original object. This is done automatically when the `result()` method is used on states or futures. The `get()` operation will cache the resolved object to reduce the overhead of subsequent calls.

### Storage of results in Prefect

The Prefect API does not store your results in most cases. The system is designed this way because:

- Results can be large and slow to send to and from the API
- Results often contain private information or data
- Results would need to be stored in the database, or complex logic implemented to hydrate from another source

There are a few cases where Prefect _will_ store your results directly in the database. This is an optimization to reduce the overhead of reading and writing to result storage. 

The following data types will be stored by the API without persistence to storage:

- booleans (`True`, `False`)
- nulls (`None`)


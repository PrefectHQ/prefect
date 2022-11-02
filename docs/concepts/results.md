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

result = my_flow()
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
    if isinstance(maybe_result, ValueError):
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

### Working with async results

When **calling** flows or tasks, the result is returned directly:

```python
import asyncio
from prefect import flow, task

@task
async def my_task():
    return 1

@flow
async def my_flow():
    task_result = await my_task()
    return task_result + 1

result = asyncio.run(my_flow())
assert result == 2
```

When working with flow and task states, the result can be retreived with the `State.result()` method:

```python
import asyncio
from prefect import flow, task

@task
async def my_task():
    return 1

@flow
async def my_flow():
    state = await my_task(return_state=True)
    result = await state.result(fetch=True)
    return result + 1

async def main():
    state = await my_flow(return_state=True)
    assert await state.result(fetch=True) == 2

asyncio.run(main())
```

!!! important "Resolving results"
    Prefect 2.6.0 added automatic retrieval of persisted results.
    Prior to this version, `State.result()` did not require an `await`.
    For backwards compatibility, when used from an asynchronous context, `State.result()` returns a raw result type.
    
    You may opt-in to the new behavior by passing `fetch=True` as shown in the example above.
    If you would like this behavior to be used automatically, you may enable the `PREFECT_ASYNC_FETCH_STATE_RESULT` setting.
    If you do not opt-in to this behavior, you will see a warning.
    
    You may also opt-out by setting `fetch=False`.
    This will silence the warning, but you will need to retrieve your result manually from the result type.

When submitting tasks to a runner, the result can be retreived with the `Future.result()` method:

```python
import asyncio
from prefect import flow, task

@task
async def my_task():
    return 1

@flow
async def my_flow():
    future = await my_task.submit()
    result = await future.result()
    return result + 1

result = asyncio.run(my_flow())
assert result == 2
```


## Persisting results

The Prefect API does not store your results [except in special cases](#storage-of-results-in-prefect). Instead, the result is _persisted_ to a storage location in your infrastructure and Prefect stores a _reference_ to the result.

The following Prefect features require results to be persisted:

- Task cache keys
- Flow run retries
- Disabling in-memory caching

If results are not persisted, these features may not be usable.

### Configuring persistence of results

Persistence of results requires a [**serializer**](#result-serializers) and a [**storage** location](#result-storage). Prefect sets defaults for these, and you should not need to adjust them until you want to customize behavior. You can configure results on the `flow` and `task` decorators with the following options:

- `persist_result`: Whether the result should be persisted to storage.
- `result_storage`: Where to store the result when persisted.
- `result_serializer`: How to convert the result to a storable form.

#### Toggling persistence

Persistence of the result of a task or flow can be configured with the `persist_result` option. The `persist_result` option defaults to a null value, which will automatically enable persistence if it is needed for a Prefect feature used by the flow or task. Otherwise, persistence is disabled by default.

For example, the following flow has retries enabled. Flow retries require that all task results are persisted, so the task's result will be persisted:

```python
from prefect import flow, task

@task
def my_task():
    return "hello world!"

@flow(retries=2)
def my_flow():
    # This task does not have persistence toggled off and it is needed for the flow feature,
    # so Prefect will persist its result at runtime
    my_task()
```

Flow retries do not require the flow's result to be persisted, so it will not be.

In this next example, one task has caching enabled. Task caching requires that the given task's result is persisted:

```python
from prefect import flow, task
from datetime import timedelta

@task(cache_key_fn=lambda: "always", cache_expiration=timedelta(seconds=20))
def my_task():
    # This task uses caching so its result will be persisted by default
    return "hello world!"


@task
def my_other_task():
    ...

@flow
def my_flow():
    # This task uses a feature that requires result persistence
    my_task()

    # This task does not use a feature that requires result persistence and the
    # flow does not use any features that require task result persistence so its
    # result will not be persisted by default
    my_other_task()
```

Persistence of results can be manually toggled on or off:

```python
from prefect import flow, task

@flow(persist_result=True)
def my_flow():
    # This flow will persist its result even if not necessary for a feature.
    ...

@task(persist_result=False)
def my_task():
    # This task will never persist its result.
    # If persistence needed for a feature, an error will be raised.
    ...
```

Toggling persistence manually will always override any behavior that Prefect would infer.

You may also change Prefect's default persistence behavior with the `PREFECT_RESULTS_PERSIST_BY_DEFAULT` setting. To persist results by default, even if they are not needed for a feature change the value to a truthy value:

```
$ prefect config set PREFECT_RESULTS_PERSIST_BY_DEFAULT=true
```

Task and flows with `persist_result=False` will not persist their results even if `PREFECT_RESULTS_PERSIST_BY_DEFAULT` is `true`.

#### Result storage location

[The result storage location](#result-storage-types) can be configured with the `result_storage` option. The `result_storage` option defaults to a null value, which infers storage from the context.
Generally, this means that tasks will use the result storage configured on the flow unless otherwise specified.
If there is no context to load the storage from and results must be persisted, results will be stored in the path specified by the `PREFECT_LOCAL_STORAGE_PATH` setting (defaults to `~/.prefect/storage`).

```python
from prefect import flow, task
from prefect.filesystems import LocalFileSystem, S3

@flow(persist_result=True)
def my_flow():
    my_task()  # This task will use the flow's result storage

@task(persist_result=True)
def my_task():
    ...

my_flow()  # The flow has no result storage configured and no parent, the local file system will be used.


# Reconfigure the flow to use a different storage type
new_flow = my_flow.with_options(result_storage=S3(bucket_path="my-bucket"))

new_flow()  # The flow and task within it will use S3 for result storage.
```

You can configure this to use a specific storage using one of the following:

- A storage instance, e.g. `LocalFileSystem(basepath=".my-results")`
- A storage slug, e.g. `'s3/dev-s3-block'`

#### Result serializer

[The result serializer](#result-serializer-types) can be configured with the `result_serializer` option. The `result_serializer` option defaults to a null value, which infers the serializer from the context.
Generally, this means that tasks will use the result serializer configured on the flow unless otherwise specified.
If there is no context to load the serializer from, the serializer defined by `PREFECT_RESULTS_DEFAULT_SERIALIZER` will be used. This setting defaults to Prefect's pickle serializer.

You may configure the result serializer using:

- A type name, e.g. `"json"` or `"pickle"` &mdash; this corresponds to an instance with default values
- An instance, e.g. `JSONSerializer(jsonlib="orjson")`

#### Compressing results

Prefect provides a `CompressedSerializer` which can be used to _wrap_ other serializers to provide compression over the bytes they generate. The compressed serializer uses `lzma` compression by default. We test other compression schemes provided in the Python standard library such as `bz2` and `zlib`, but you should be able to use any compression library that provides `compress` and `decompress` methods.

You may configure compression of results using:

- A type name, prefixed with `compressed/` e.g. `"compressed/json"` or `"compressed/pickle"`
- An instance e.g. `CompressedSerializer(serializer="pickle", compressionlib="lzma")`

Note that the `"compressed/<serializer-type>"` shortcut will only work for serializers provided by Prefect. 
If you are using custom serializers, you must pass a full instance.


### Storage of results in Prefect

The Prefect API does not store your results in most cases for the following reasons:

- Results can be large and slow to send to and from the API.
- Results often contain private information or data.
- Results would need to be stored in the database or complex logic implemented to hydrate from another source.

There are a few cases where Prefect _will_ store your results directly in the database. This is an optimization to reduce the overhead of reading and writing to result storage.

The following data types will be stored by the API without persistence to storage:

- booleans (`True`, `False`)
- nulls (`None`)

If `persist_result` is set to `False`, these values will never be stored.


## Caching of results in memory

When running your workflows, Prefect will keep the results of all tasks and flows in memory so they can be passed downstream. In some cases, it is desirable to override this behavior. For example, if you are returning a large amount of data from a task it can be costly to keep it memory for the entire duration of the flow run.

Flows and tasks both include an option to drop the result from memory with `cache_result_in_memory`:

```python
@flow(cache_result_in_memory=False)
def foo():
    return "pretend this is large data"

@task(cache_result_in_memory=False)
def bar():
    return "pretend this is biiiig data"
```

When `cache_result_in_memory` is disabled, the result of your flow or task will be persisted by default. The result will then be pulled from storage when needed.

```python
@flow
def foo():
    result = bar()
    state = bar(return_state=True)

    # The result will be retrieved from storage here
    state.result()

    future = bar.submit()
    # The result will be retrieved from storage here
    future.result()

@task(cache_result_in_memory=False)
def bar():
    # This result will persisted
    return "pretend this is biiiig data"
```

If both `cache_result_in_memory` and persistence are disabled, your results will not be available downstream.

```python

@task(persist_result=False, cache_result_in_memory=False)
def bar():
    return "pretend this is biiiig data"

@flow
def foo():
    # Raises an error
    result = bar()

    # This is oaky
    state = bar(return_state=True)

    # Raises an error
    state.result()

    # This is okay
    future = bar.submit()

    # Raises an error
    future.result()
```


## Result storage types

Result storage is responsible for reading and writing serialized data to an external location. At this time, any file system block can be used for result storage.

## Result serializer types

A result serializer is responsible for converting your Python object to and from bytes. This is necessary to store the object outside of Python and retrieve it later.

### Pickle serializer

Pickle is a standard Python protocol for encoding arbitrary Python objects. We supply a custom pickle serializer at `prefect.serializers.PickleSerializer`. Prefect's pickle serializer uses the [cloudpickle](https://github.com/cloudpipe/cloudpickle) project by default to support more object types. Alternative pickle libraries can be specified:

```python
from prefect.serializers import PickleSerializer

PickleSerializer(picklelib="custompickle")
```

Benefits of the pickle serializer:

- Many object types are supported.
- Objects can define custom pickle support.

Drawbacks of the pickle serializer:

- When nested attributes of an object cannot be pickled, it is hard to determine the cause.
- When deserializing objects, your Python and pickle library versions must match the one used at serialization time.
- Serialized objects cannot be easily shared across different programming languages.
- Serialized objects are not human readable.

### JSON serializer


We supply a custom JSON serializer at `prefect.serializers.JSONSerializer`. Prefect's JSON serializer uses custom hooks by default to support more object types. Specifically, we add support for all types supported by [Pydantic](https://pydantic-docs.helpmanual.io/).


By default, we use the standard Python `json` library. Alternative JSON libraries can be specified:

```python
from prefect.serializers import JSONSerializer

JSONSerializer(jsonlib="orjson")
```

Benefits of the JSON serializer:

- Serialized objects are human readable.
- Serialized objects can often be shared across different programming languages.
- Deserialization of serialized objects is generally version agnostic.

Drawbacks of the JSON serializer:

- Supported types are limited.
- Implementing support for additional types must be done at the serializer level.


## Result types

Prefect uses internal result types to capture information about the result attached to a state. The following types are used:

- `LiteralResult`: Stores simple values inline.
- `PersistedResult`: Stores a reference to a result persisted to storage.

All result types include a `get()` method that can be called to return the value of the result. This is done behind the scenes when the `result()` method is used on states or futures.

### Literal results

Literal results are used to represent [results stored in the Prefect database](#storage-of-results-in-prefect). The values contained by these results must always be JSON serializable.

Example:
```
result = LiteralResult(value=None)
result.json()
# {"type": "result", "value": "null"}
```

Literal results reduce the overhead required to persist simple results.

###  Persisted results

The persisted result type contains all of the information needed to retrieve the result from storage. This includes:

- Storage: A reference to the [result storage](#result-storage-types) that can be used to read the serialized result.
- Key: Indicates where this specific result is in storage.

Persisted result types also contain metadata for inspection without retrieving the result:

- Serializer type: The name of the [result serializer](#result-serializer-types) type.

The `get()` method on result references retrieves the data from storage, deserializes it, and returns the original object.
The `get()` operation will cache the resolved object to reduce the overhead of subsequent calls.

#### Persisted result blob

When results are persisted to storage, they are always written as a JSON document. The schema for this is described by the `PersistedResultBlob` type. The document contains:

- The serialized data of the result.
- A full description of [result serializer](#result-serializer-types) that can be used to deserialize the result data.
- The Prefect version used to create the result.

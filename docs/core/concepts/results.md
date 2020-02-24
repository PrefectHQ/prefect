# Results and Result Handlers

Prefect allows data to pass between Tasks as a first class operation. Additionally, Prefect was designed with security and privacy concerns
in mind. Consequently, Prefect's abstractions allow users to take advantage of all its features without ever needing to surrender control, access, or even visibility of their private data.

One of the primary ways in which this is achieved is through the use of "Results" and "Result Handlers".  At a high level, all `State` objects have a `Result` object associated with them. Tasks can be configured to provide a `ResultHandler` to their `Result` objects, which specifies how the outputs of that Task should be handled if they need to be persisted for any reason. (For background on when / why this might occur, see the Concepts section on [caching](execution.html#caching)). This _includes_ the situation where a _downstream_ task needs to cache its inputs - each input will be stored according to its own individual result handler.

::: warning Result Handlers are always attached to Task outputs
For example, suppose Task A has Result Handler A, and Task B has Result Handler B, and that A passes data downstream to B. If B fails and requests a retry, it needs to cache its inputs, one of which came from A. When it stores this data, it will use Result Handler A.
:::

::: tip What gets stored
When running Prefect with Prefect Cloud, only the data contained in a `Result`'s `safe_value` attribute are stored. This `safe_value` is populated by calling a `Result`'s `store_safe_value` method, which in turn will "write" the result using its result handler. This ensures that no raw data arrives in the database.
:::

## Results

Results represent Prefect Task outputs. In particular, anytime a Task runs, its output
is encapsulated in a `Result` object. This object retains information about what the data is and how to "handle" it
if it needs to be saved / retrieved at a later time (for example, if this Task requests for its outputs to be cached or checkpointed).

An instantiated Result object has the following attributes:

- a `value`: the value of a Result represents a single piece of data
- a `safe_value`: this attribute maintains a reference to a `SafeResult` object
  which contains a "safe" representation of the `value`; for example, the `value` of a `SafeResult`
  might be a URI or filename pointing to where the raw data lives. In this context, "safe" means
  that the value is safe to be sent to Cloud.
- a `result_handler` that holds onto the `ResultHandler` used to read /
  write the value to / from its handled representation
  
In the unconfigured case, all `State` objects produced by a flow have a basic `Result` object with only `Result.value` set, and no result handler attached.

```python
>>> type(state._result)
prefect.engine.result.Result
>>> type(state._result.value)  # this is the type of your Task's return value
dict
>>> type(state._result.safe_value)
prefect.engine.result.NoResultType
>>> type(state._result.result_handler)
NoneType
```

::: tip NoResult vs. a None Result
To distinguish between a Task that runs but does not return output from a Task that has yet to run, Prefect
also provides a `NoResult` object representing the _absence_ of computation / data. This is in contrast to a `Result`
whose value is `None`. The `to_result` / `store_safe_value` methods, along with the `value` and `safe_value` attributes of `NoResult` all return the same `NoResult` object.
:::

### Interacting with `Result`s

The most common scenario in which a user might need to directly interact with a `Result` object in memory is when running Flows locally. All Prefect States have Result objects built into them, which can be accessed via the private `_result` attribute. For convenience, the public `.result` property retrieves the underlying `Result`'s value.

```python
>>> task_ref = flow.get_tasks[0]
>>> state = flow.run()
>>> state._result.value  # a Flow State's Result value is its Tasks' States
{<Task: add>: <Success: "Task run succeeded.">,
 <Task: add>: <Success: "Task run succeeded.">}
>>> state.result  # the public property aliases the same API as above
{<Task: add>: <Success: "Task run succeeded.">,
 <Task: add>: <Success: "Task run succeeded.">}
>>> state.result[task_ref]._result  # a Task State's Result contains the Task's return value
<Result: 1>
```

All Results come equipped with `to_result` / `store_safe_value` methods which read results from their handlers, and write results with their handlers, respectively.

## Result Handlers

Result handlers are a more public entity than the `Result` class, as they provide the means to persist the data from an in-memory `Result` object. A result handler is a specific implementation of a `read` / `write` interface for handling data. The only actual requirement for a result handler implementation is that the `write` method returns a JSON-compatible object. 

In general, however, result handler `write` methods are implemented so that they do two things:
1. serialize the return value of a Task in-memory in the Task State's `Result.value` attribute, and persist it to disk in the result handler's storage backend, and
2. segregate out a "safe value", usually metadata, about that stored return value in the State's `Result.safe_value` attribute and, for Cloud customers, persist that safe value in the scheduler database

On the flip side, result handler `read` methods usually access the metadata in an upstream `Result.safe_value` to locate, and then deserialize, the upstream Task's return value that is in storage.

For example, we can easily imagine different kinds of result handlers:

- a Google Cloud Storage handler which writes a given piece of data to a Google Cloud Storage bucket, and reads data from that bucket; the `write` method in this instance returns a URI
- a `LocalResultHandler` that reads / writes data from local file storage; the `write` method in this instance returns an absolute file path

In the following example, imagine my flow was configured to checkpoint each task's output using the `LocalResultHandler`. My `Result.value` is equal to `3` - the actual return value of my Task. My `Result.safe_value` is a string for a local file path.

```python
>>> state.result[first_result]._result.value
3
>>> state.result[first_result]._result.safe_value           
<SafeResult: '/Users/prefect/Desktop/HelloWorld/results/prefect-result-2020-02-23t18-38-40-381223-00-00'>
```

Inside that file is a `cloudpickle` of the value `3`, as the implementation of `LocalResultHandler` persists the data from `Result.value` as a pickle at the local filesystem location of `Result.safe_value`.
```python
>>> f = open(state.result[first_result]._result.safe_value.value, 'rb')
>>> content = f.read()     
>>> content                
b'\x80\x05K\x03.'
>>> import cloudpickle     
>>> cloudpickle.loads(content)                              
3
```

However, depending on your situation and the size of your data, you can configure Result Handlers to serialize a Task's entire `Result`, not just its metadata. For example, Core's base `JSONResultHandler` serializes the entire `Result` object as its return value. If you have a task which returns a small piece of data such as a string, or a short list of numbers, handling that data directly in the returned JSON string will suffice!

To showcase this, below is the same example with my flow configured to checkpoint each task's output using the `JSONResultHandler`. Note that now both `Result.value` and `Result.safe_value` contain references to the actual return value of my task, the integer `3`.

```python
>>> state.result[first_result]._result.value                 
3
>>> state.result[first_result]._result.safe_value            
<SafeResult: '3'>
```

In Core, the return value is associated in-memory with the `Result` object attached to flow `State`s. For Cloud customers, the return value of a result handler's `write` method is also persisted in Prefect Cloud's database.

::: warning Handle your data carefully
When running on Prefect Cloud, the return value of a Result Handler's `write` method is what is stored in the Cloud database. Though you may serialize your data during your result handler's execution, *only* `return` data that you feel is safe to persist in Prefect Cloud.
:::

### How to specify a `ResultHandler`

`ResultHandler`'s `read` and `write` methods will be called by Prefect only if you enable either checkpointing or caching. Once this configuration is set, there is a hierarchy to determining what `ResultHandler` to use for a given piece of data:

1. First, users can set a global default in their Prefect user config; if you never mention or think about Result Handlers again, this is the handler that will always be used.
1. Next, you can specify a Flow-level result handler at Flow-initialization using the `result_handler` keyword argument. Once again, if you never specify another result handler, this is the one that will be used for all your tasks in this particular Flow.
1. Lastly, you can set a Task-level result handler. This is achieved using the `result_handler` keyword argument at Task initialization (or in the `@task` decorator). If you provide a result handler here, it will _always_ be used if the _output_ of this Task needs to be cached for any reason whatsoever.

::: tip The Hierarchy
Task-level result handlers will _always_ be used over Flow-level handlers; Flow-level result handlers will _always_ be used over the handler set in your config.
:::

::: warning Parameters are different
There is one exception to the rule for Result Handlers: Prefect Parameters. Prefect Parameters always use the `JSONResultHandler` so that their cached values are inspectable in the UI.
:::

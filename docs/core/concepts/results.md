# Results and Result Handlers

Prefect allows data to pass between Tasks as a first class operation. Additionally, Prefect was designed with security and privacy concerns
in mind. Consequently, Prefect's abstractions allow users to take advantage of all its features without ever needing to surrender control, access, or even visibility of their private data.

One of the primary ways in which this is achieved is through the use of "Results" and their handlers. At a high level, you can code up a task and provide it with a "result handler" which specifies how the outputs of this Task should be handled if they need to be stored for any reason (for background on when / why this might occur, see the Concepts section on [caching](execution.html#caching)). This _includes_ the situation where a _downstream_ task needs to cache its inputs - each input will be stored according to its own individual result handler.

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

::: tip NoResult vs. a None Result
To distinguish between a Task that runs but does not return output from a Task that has yet to run, Prefect
also provides a `NoResult` object representing the _absence_ of computation / data. This is in contrast to a `Result`
whose value is `None`. The `to_result` / `store_safe_value` methods, along with the `value` and `safe_value` attributes of `NoResult` all return the same `NoResult` object.
:::

### Interacting with Results

The most common scenario in which a user might need to directly interact with a `Result` object is when running Flows locally. All Prefect States have Result objects built into them, which can be accessed via the private `_result` attribute. For convenience, the public `.result` property retrieves the underlying `Result`'s value.

All Results come equipped with `to_result` / `store_safe_value` methods which read results from their handlers, and write results with their handlers, respectively.

## Result Handlers

Result handlers are a more public entity than the `Result` class. A result handler is a specific implementation of a `read` / `write` interface for handling data. The only requirement for a result handler implementation is that the `write` method returns a JSON-compatible object. For example, we can easily imagine different kinds of result handlers:

- an Google Cloud Storage handler which writes a given piece of data to a Google Cloud Storage bucket, and reads data from that bucket; the `write` method in this instance returns a URI
- a `LocalResultHandler` that reads / writes data from local file storage; the `write` method in this instance returns an absolute file path

However, we can be more creative with Result Handlers. For example, if you have a task which returns a small piece of data such as a string, or a short list of numbers, and you are comfortable with this data living in Prefect Cloud's database, then a simple `JSONResultHandler` that dumps your data to a JSON string will suffice!

::: warning Handle your data carefully
When running on Prefect Cloud, the output of a Result Handler's `write` method is what is stored in the Cloud database.
:::

### How to specify a `ResultHandler`

There is a hierarchy to determining what `ResultHandler` to use for a given piece of data:

1. First, users can set a global default in their Prefect user config; if you never mention or think about Result Handlers again, this is the handler that will always be used.
1. Next, you can specify a Flow-level result handler at Flow-initialization using the `result_handler` keyword argument. Once again, if you never specify another result handler, this is the one that will be used for all your tasks in this particular Flow.
1. Lastly, you can set a Task-level result handler. This is achieved using the `result_handler` keyword argument at Task initialization (or in the `@task` decorator). If you provide a result handler here, it will _always_ be used if the _output_ of this Task needs to be cached for any reason whatsoever.

::: tip The Hierarchy
Task-level result handlers will _always_ be used over Flow-level handlers; Flow-level result handlers will _always_ be used over the handler set in your config.
:::

::: warning Parameters are different
There is one exception to the rule for Result Handlers: Prefect Parameters. Prefect Parameters always use the `JSONResultHandler` so that their cached values are inspectable in the UI.
:::

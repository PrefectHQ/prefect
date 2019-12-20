# Prefect Cloud Dataflow: A Guided Tour

Prefect Cloud's innovative hybrid execution model was designed to satisfy the majority of on-prem needs while still offering a managed platform. In order to achieve this, Prefect was designed to allow users the ability to ensure both their _code_ and their _data_ never leaves their internal ecosystem. This guide will focus on how _data_ moves between tasks and flows in the Prefect Cloud execution model, as well as call out any caveats that might result in data being exposed to Prefect Cloud.

All data being referenced here are the inputs and outputs of Prefect tasks. Note that _all task execution_ occurs in user-controllled infrastructure; consequently, when a task passes data to a downstream task, this data passage occurs _entirely in the user's infrastructure_ as well. The only time data might leave the user's execution infrastructure is when task data is persisted.

Note additionally that when metadata does arrive in Prefect Cloud, it is accessible only via other users in your tenant with the appropriate permissions.

## How is data persisted?

The beauty of Prefect is that output can be handled on a task-by-task basis. This is achieved through the use of a [Prefect Result Handler](https://docs.prefect.io/core/concepts/results.html#result-handlers), a Python class with a read / write interface responsible for persisting output. The only requirement for a result handler is that its `write` method returns a JSON-compatible object; a common example is a URI string.

It's worth noting that the output of a result handler's write method is sent to Prefect Cloud, making this one of the few scenarios in which your data can be sent to Prefect Cloud. Note additionally that user-written result handlers exist as code in a user's Docker container, inaccessible to Prefect Cloud. Because of this, one way to secure any output of the `write` method more secure is employ encryption secrets to make the output of the `write` method.

## When is data persisted?

There are few circumstances under which Prefect Cloud actually needs to persist data.

Ultimately, data will be persisted _anytime a task's result handler is called_. Task result handlers are _only called under the following circumstances_:

- **Task Retries**: in this event, result handlers are called on _all upstream inputs to the retrying task_
- **Task Queues**: functionally equivalent to retries, occurs whenever a task hits a user-set concurrency limit, and result handlers are called on all upstream inputs to the queued task
- **Task Caching**: if a task is set to cache its own result, result handlers are called on _all upstream inputs to the cached task_ as well as on the _task's output_
- **Task Checkpointing**: any task requesting to be "checkpointed" will have its result handler called _only on its own output_
- **Parameters**: all parameters are JSON-serialized and sent directly to Prefect Cloud

## Where does all of this take place?

All task execution, including the invocation of result handlers takes place on _user infrastructure_. Absolutely no user code is executed on Prefect Cloud infrastructure.

## Gotchas and Caveats

Here is an exhaustive list of places data might land in the Prefect Cloud database:

- **Parameters**: all parameters are "checkpointed" using a `JSONResultHandler` and consequently persisted in Prefect Cloud
- **Logs**: all logs shipped through the Prefect Logger are placed in the Prefect Cloud database; this behavior may be toggled using an environment variable on your agent. Otherwise, you are always welcome to add custom formatters and handlers to the Prefect logger which can filter out log messages based on regexes for sensitive information.
- **Exceptions**: When unexpected errors are caught, the string representation of the exception and the corresponding traceback is used as the "message" of the corresponding `Failed` state and persisted in Prefect Cloud
- **`ResultHandler.write`**: the output JSON objects from `ResultHandler.write` across all result handlers called during execution; as stated previously, this is configurable to mask sensitive URIs, etc.

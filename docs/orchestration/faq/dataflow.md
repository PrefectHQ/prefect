# Data Handling in the Hybrid Model

Prefect Cloud's innovative hybrid execution model was designed to satisfy the majority of on-prem needs while still offering a managed platform. In order to achieve this, Prefect was designed to allow users the ability to ensure both their _code_ and their _data_ never leaves their internal ecosystem. This guide will focus on how _data_ moves between tasks and flows in the Prefect Cloud execution model, as well as call out any caveats that might result in data being exposed to Prefect Cloud.

All data being referenced here are the inputs and outputs of Prefect tasks. Note that _all task execution_ occurs in user-controlled infrastructure; consequently, when a task passes data to a downstream task, this data passage occurs _entirely in the user's infrastructure_ as well. The only time data might leave the user's execution infrastructure is when task data is persisted.

Note additionally that when metadata does arrive in Prefect Cloud, it is accessible only via other users in your tenant with the appropriate permissions.

## How is data persisted?

The beauty of Prefect is that output can be handled on a task-by-task basis. This is achieved through the use of a subclass of [Result](https://docs.prefect.io/core/concepts/results.html), a Python class with a read / write interface responsible for persisting output.

It's worth noting that a result's `location` attribute is sent to Prefect Cloud, making this one of the few scenarios in which your data can be sent to Prefect Cloud. If you wish to secure this field more, consider a custom `Result` subclass that utilizes encryption secrets to format the `location` attribute of your result.

## When is data persisted?

There are few circumstances under which Prefect Cloud actually needs to persist data.

Ultimately, data will be persisted _anytime a task's result's `write` method is called_. Task result `write` methods are _only called under the following circumstances_:

- **Task Retries**: in this event, result methods are called on _all upstream inputs to the retrying task_
- **Task Queues**: functionally equivalent to retries, occurs whenever a task hits a user-set concurrency limit, and result methods are called on all upstream inputs to the queued task
- **Task Caching**: if a task is set to cache its own result, result methods are called on _all upstream inputs to the cached task_ as well as on the _task's output_
- **Task Checkpointing**: any task requesting to be "checkpointed" will have its `Result.write` method called _only on its own output_
- **Parameters**: all parameters are JSON-serialized and sent directly to Prefect Cloud

As of Prefect version `0.9.0` all flows registered with Prefect Cloud that have a storage option other than `Docker` will automatically have a result attached to the flow. This is to ensure some of Prefect Cloud's added functionality, such as restarting from a failed task, work as expected.

## Where does all of this take place?

All task execution, including the invocation of result methods takes place on _user infrastructure_. Absolutely no user code is executed on Prefect Cloud infrastructure.

## Gotchas and Caveats

Here is an exhaustive list of places data might land in the Prefect Cloud database:

- **Parameters**: all parameters are "checkpointed" using a `PrefectResult` and consequently persisted in Prefect Cloud
- **Logs**: all logs shipped through the Prefect Logger are placed in the Prefect Cloud database; this behavior may be toggled using an environment variable on your agent. Otherwise, you are always welcome to add custom formatters and handlers to the Prefect logger which can filter out log messages based on regexes for sensitive information.
- **Exceptions**: When unexpected errors are caught, the string representation of the exception and the corresponding traceback is used as the "message" of the corresponding `Failed` state and persisted in Prefect Cloud
- **`Result.location`**: the value of `Result.location` across all result subclasses called during execution; as stated previously, this is configurable to mask sensitive URIs, etc.

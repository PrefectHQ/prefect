# Prefect Cloud Dataflow: A Guided Tour

Prefect Cloud's innovative hybrid execution model was designed to satisfy the majority of on-prem needs while still offering a managed platform. In order to achieve this, Prefect was designed to allow users the ability to ensure both their _code_ and their _data_ never leaves their internal ecosystem. This guide will focus on how _data_ moves between tasks and flows in the Prefect Cloud execution model, and call out any / all caveats that might result in data leakage to Cloud. This only applies to the hybrid model, not fully on-premise deployments.

All data being referenced here are the inputs and outputs of Prefect Tasks. Note that _all task execution_ occurs in user-controllled infrastructure; consequently, when a Task passes data to a downstream Task, this data passage occurs _entirely in the user's infrastructure_. The only time data might leave the user's execution infrastructure is when Task data is persisted.

Note additionally that when metadata does arrive in Prefect Cloud, it is accessible only via other users in your tenant with the appropriate permissions.

## How is data persisted?

The beauty of Prefect is that each Task can individually specify how its result / output should be handled. This is achieved through the use of a [Prefect Result Handler](https://docs.prefect.io/core/concepts/results.html#result-handlers), which is a Python class with a read / write interface. The only requirement for a Result handler implementation is that the `write` method returns a JSON-compatible object. URI strings are typical outputs of the `write` method for a Result Handler. Note that the output of a Result Handler's write method is sent to Cloud. Whenever a Task's output data needs to be persisted, it is "written" using the Task's Result Handler. If no result handler exists on the task, an error will be raised and the data will not be persisted anywhere.

Note additionally that user-written result handlers live as-code in a user's Docker container, which is entirely inaccessible to Prefect Cloud. Thus your result handler could employ encryption secrets to make the output of the `write` method more secure.

## When is data persisted?

There are surprisingly few circumstances where Prefect Cloud actually needs to store data in a persistent way.

Ultimately, data will be persisted _anytime a Task's result handler is called_. Task result handlers are _only called in the following circumstances_:

- **Task Retries**: in this event, result handlers are called on _all upstream inputs to the retrying task_
- **Task Queues**: functionally equivalent to retries, occurs whenever a Task hits a user-set concurrency limit, and result handlers are called on all upstream inputs to the queued task
- **Task Caching**: if a Task is set to cache its own result, result handlers are called on _all upstream inputs to the cached task_ as well as on the _task's output itself_
- **Task Checkpointing**: any Task which requests to be "checkpointed" will have its result handler called _only on its own output_
- **Parameters**: all Parameters are JSON-serialized and sent directly to Cloud

## Where does all of this take place?

All task execution, including the invokation of Result Handlers takes place on _user infrastructure_. Absolutely no user code is ever executed on the Prefect Cloud servers.

## Gotchas and Caveats

Here is an exhaustive list of places data might land in the Prefect Cloud database:

- **Parameters**: all Parameters are "checkpointed" using a `JSONResultHandler` and consequently arrive in Cloud
- **Logs**: all logs which are shipped through the Prefect Logger are placed in the Cloud database; toggling this behavior is a simple environment variable on your Prefect Agent. Otherwise, you are always welcome to add custom formatters and handlers to the Prefect Logger which can filter out log messages based on regexes for sensitive information.
- **Exceptions**: When unexpected errors are caught, the string representation of the exception and the corresponding traceback is used as the "message" of the corresponding `Failed` Prefect State and arrives in Cloud
- **`ResultHandler.write`**: the output JSON objects from `ResultHandler.write` across all result handlers that are actually called during execution; as stated previously, this is easily configurable to mask sensitive URIs, etc.

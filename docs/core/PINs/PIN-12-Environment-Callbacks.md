# PIN 12: Environment Callbacks

Date: October 1, 2019
Author: Josh Meek

# Status
Accepted

# Context
Prefect Environments currently support a `setup` and `execute` paradigm when it comes to creation of the environment and using it to execute a flow (outlined in  [PIN-3](/core/PINs/PIN-03-Agent-Environment.html#process-details)). These two primary functions are key for infrastructure related processes which may arise during the execution of a flow. While they mainly deal with infrastructure creation there is another request which has arisen through use of the system in the form of pre/post-processing of the flow execution itself from the environment level.

# Proposal
Implement `on_start` and `on_exit` callback options to environments which users can use to provide _optional_ functions which execute before the flow is run and after the run has ended (or the job has exited). These functions will provide a mechanism for users to create custom hooks and notifications for their environment execution. The callbacks are meant more as a tool for execution and are not intended to replace aspects such as state handlers.

The new Environment class signature would look like:
```python
Environment(labels: Iterable[str] = None,
            on_start: Callable = None,
            on_exit: Callable = None)
```

### Callback Examples
`on_start`
- Broadcast info to a Dask cluster (e.g. `register_worker_callbacks`)
- Collect available resources for worker allocation

`on_exit`
- Send custom notification if a task became a zombie
- Collect metrics / logs from resources created by the environment

# Consequences

Users will be able to specify `on_start` and `on_exit` callbacks for their environments. One new requirement would be that users of these callbacks have to be aware of where these callbacks occur because it will be different for each environment. While they all do still run a flow in a main process somewhere they differ in where that main process happens.

An example of this is the `RemoteEnvironment`, deployed on Kubernetes, will run the main process on the initial Prefect job while the `KubernetesJobEnvironment` will run the main process on a separate custom job that spawns after the initial Prefect job.

Another consequence that still falls into the awareness category is that of knowing which callbacks are actually useful for the specified method of execution. One example to keep in mind is how a custom Dask `on_start` callback will not be entirely useful if a flow is not using a Dask executor.

# Actions
Implement #1574

Decide whether or not the failure of a callback will be allowed to fail the main process of the Environment. For example, if the `on_start` callback fails does the flow execution still occur or is the failure logged as a failure for that particular flow run?

Add example callbacks which users could use out of the box.

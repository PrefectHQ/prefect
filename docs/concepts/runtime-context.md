---
description: The runtime context allows global access to information about the current run.
tags:
    - flows
    - subflows
    - tasks
    - deployments
---


# Runtime context

Prefect tracks information about the current flow or task run with a run context. The run context can be thought of as a global variable that allows the Prefect engine to determine relationships between your runs, e.g. which flow your task is called from.

The run context itself contains many internal objects used by Prefect to manage execution of your run and is only available in specific situtations. For this reason, we expose a simple interface that only includes the items you care about and dynamically retrieves additional information when necessary. We call this the "runtime context" as it contains information that can only be accessed when a run is happening.

!!! tip "Mock values via environment variable"
    Oftentimes, you may want to mock certain values for testing purposes.  For example, by manually setting an ID or a scheduled start time to ensure your code is functioning properly.  Starting in version `2.10.3`, you can mock values in runtime via environment variable using the schema `PREFECT__RUNTIME__{SUBMODULE}__{KEY_NAME}=value`:
    <div class="terminal">
    ```bash
    $ export PREFECT__RUNTIME__TASK_RUN__FAKE_KEY='foo'
    $ python -c 'from prefect.runtime import task_run; print(task_run.fake_key)' # "foo"
    ```
    </div>


## Accessing runtime information

The `prefect.runtime` module is the home for all runtime context access. It has a submodule for each major runtime concept:

- `deployment`: Access information about the deployment for the current run
- `flow_run`: Access information about the current flow run
- `task_run`: Access information about the current task run


For example:

```python
from prefect import flow, task
import prefect.runtime


@flow(log_prints=True)
def my_flow(x):
    print("My name is", prefect.runtime.flow_run.name)
    print("I belong to deployment", prefect.runtime.deployment.name)
    my_task(2)


@task
def my_task(y):
    print("My name is", prefect.runtime.task_run.name)
    print("Flow run parameters:", prefect.runtime.flow_run.parameters)


my_flow(1)
```

Above, we demonstrate access to information about the current flow run, task run, and deployment. If you run this locally, you should see `"I belong to deployment None"` logged. When information is not available, the runtime will always return an empty value. Since we've run this flow without a deployment, there is no data in the deployment module. If this flow was deployed and executed by an agent, we'd see the name of the deployment instead.

See the [runtime API reference](/api-ref/prefect/runtime/flow_run/) for a full list of available attributes.

## Accessing the run context directly

The current run context can be accessed with `prefect.context.get_run_context()`. This will raise an exception if no run context is available, i.e. you are not in a flow or task run. If a task run context is available, it will be returned even if a flow run context is available.

Alternatively, you can access the flow run or task run contexts explicitly. This will, for example, allow you to access the flow run context from a task run. Note that we do not send the flow run context to distributed task workers because they are costly to serialize and deserialize.

```python
from prefect.context import FlowRunContext, TaskRunContext

flow_run_ctx = FlowRunContext.get()
task_run_ctx = TaskRunContext.get()
```

Unlike `get_run_context`, this will not raise an error if the context is not available. Instead, it will return `None`.

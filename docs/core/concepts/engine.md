# Engine

## Overview

Prefect's execution model is built around two classes, `FlowRunner` and `TaskRunner`, which produce and operate on [State](states.html) objects. The actual execution is handled by `Executor` classes, which can interface with external environments.

## Flow runners

The flow runner takes a flow and attempts to run all of its tasks. It collects the resulting states and, if possible, returns a final state for the flow.

Flow runners loop over all of the tasks one time. If tasks remain unfinished after that pass -- for example, if one of them needs to be retried -- then a second loop will be required to attempt to finish them. There is no limit to the number of attempts it may take to move all tasks (and therefore the flow itself) into a finished state.

### Parameters

Flows that have parameters may require parameter values (if those parameters have no defaults). Parameter values must be passed to the flow runner when it runs.

## Task runners

The task runner is responsible for executing a single task. It receives the task's initial state as well as any upstream states, and uses these to evaluate an execution pipeline. For example:

- the task must be in a `Pending` state
- the upstream tasks must be `Finished`
- the task's trigger function must pass

If these conditions (and a few others) are met, the task can move into a `Running` state.

Then, depending on the task, it may either be `run()` or it may be mapped, which involves creating dynamic children task runners.

Finally, the task moves through a post-process pipeline that checks to see if it should be retried or cached.

## Executors

The executor classes are responsible for actually running tasks. For example, the flow runner will submit each task runner to its executor, and wait for the result. We recommend [Dask distributed](https://github.com/dask/distributed) as the preferred execution engine.

Executors have a relatively simple API - users can `submit` functions and `wait` for their results.

For testing and development, the `LocalExecutor` is preferred. It runs every function synchronously in the local process and is the default executor for flows unless otherwise specified.

The `LocalDaskExecutor` is slightly more complex. It still runs functions locally, but uses Dask to parallelize across threads or processes.

The `DaskExecutor` is a completely asynchronous engine that can run functions in a distributed Dask cluster. This is the recommended engine for production.

### Using a Dask Executor

An executor can be provided to a flow at runtime:

```python{10, 12-13}
from prefect import task, Flow

@task
def say_hello():
    print("Hello, world!")

with Flow("Run Me") as flow:
    h = say_hello()

from prefect.executors import DaskExecutor

executor = DaskExecutor(address="tcp://localhost:8786")
flow.run(executor=executor)
```

This `DaskExecutor` will connect to a Dask scheduler over the address `tcp://localhost:8786` and begin submitting work to be executed on Dask workers.

!!! tip Dynamic Scheduler
    If no scheduler `address` is specified for the `DaskExecutor` than an in-process scheduler will be created and torn down upon completion. See the [DaskExecutor API Documentation](/api/latest/executors.html#daskexecutor) for more information.


!!! warning LocalDaskExecutor vs DaskExecutor
    The key difference between the `LocalDaskExecutor` and the `DaskExecutor` is the choice of scheduler. The `LocalDaskExecutor` is configurable to use [any number of schedulers](https://docs.dask.org/en/latest/scheduler-overview.html) while the `DaskExecutor` uses the [distributed scheduler](https://docs.dask.org/en/latest/scheduling.html). This means that the `LocalDaskExecutor` can help achieve some multithreading / multiprocessing however it does not provide as many distributed features as the `DaskExecutor`.


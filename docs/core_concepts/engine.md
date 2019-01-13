# Engine

## Overview

Prefect's execution model is built around two classes, `FlowRunner` and `TaskRunner`, which produce and operate on [State](/states.html) objects. The actual execution is handled by `Executor` classes, which can interface with external environments.

## Flow runners

The flow runner takes a flow and attempts to run all of its tasks. It collects the reuslting states and, if possible, returns a final state for the flow.

Flow runners loop over all of the tasks one time. If tasks remain unfinished after that pass -- for example, if one of them needs to be retried -- then a second loop will be required to attempt to finish them. There is no limit to the number of attempts it may take to move all tasks (and therefore the flow itself) into a finished state.

### Start tasks

"Start tasks" allow users to run only a subgraph of the full flow. For example, if the 50th task out of 100 needs to be retried, you can specify that task as a `start_task` and ignore the previous 50.

Start tasks are treated as root tasks, which means their upstream checks are skipped. For example, they do not evaluate their trigger functions. While this can be helpful, users must take care to provide the appropriate inputs if the task requires them.

### Return tasks

When a flow is run, users can set `return_tasks`. The runner will return states for all requested tasks; by default, it returns states for no tasks.

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

For testing and development, the `LocalExecutor` is preferred. It runs every function synchronously in the local process.

The `SynchronousExecutor` is slightly more complex. It still runs functions in a single thread, but uses Dask's scheduling logic.

The `DaskExecutor` is a completely asynchronous engine that can run functions in a distributed Dask cluster. This is the recommended engine for production.

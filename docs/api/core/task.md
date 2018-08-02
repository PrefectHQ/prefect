---
sidebarDepth: 1
---

 ## Task

### <span style="background-color:rgba(27,31,35,0.05);font-size:0.85em;">class</span> ```prefect.core.task.Task(name=None, slug=None, description=None, group=None, tags=None, max_retries=0, retry_delay=0:01:00, timeout=None, trigger=None, propagate_skip=False, cache_for=None, cache_validator=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/task.py#L39)</span>
A class that automatically uses a specified JSONCodec to serialize itself.

 ####  ```prefect.core.task.Task.inputs()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/task.py#L84)</span>


 ####  ```prefect.core.task.Task.run()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/task.py#L87)</span>
The main entrypoint for tasks.

In addition to running arbitrary functions, tasks can interact with
Prefect in a few ways:
    1. Return an optional result. When this function runs successfully,
        the task is considered successful and the result (if any) is
        made available to downstream edges.
    2. Raise an error. Errors are interpreted as failure.
    3. Raise a signal. Signals can include FAIL, SUCCESS, WAIT, etc.
        and indicate that the task should be put in the indicated
        state.
        - FAIL will lead to retries if appropriate
        - WAIT will end execution and skip all downstream tasks with
            state WAITING_FOR_UPSTREAM (unless appropriate triggers
            are set). The task can be run again and should check
            context.is_waiting to see if it was placed in a WAIT.

 ####  ```prefect.core.task.Task.serialize(task)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/task.py#L159)</span>


 ####  ```prefect.core.task.Task.set_dependencies(flow=None, upstream_tasks=None, downstream_tasks=None, keyword_tasks=None, validate=True)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/task.py#L134)</span>



 ## Parameter

### <span style="background-color:rgba(27,31,35,0.05);font-size:0.85em;">class</span> ```prefect.core.task.Parameter(name, default=None, required=True)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/task.py#L174)</span>
A Parameter is a special task that defines a required flow input.

A parameter's "slug" is automatically -- and immutably -- set to the parameter name.
Flows enforce slug uniqueness across all tasks, so this ensures that the flow has
no other parameters by the same name.

 ####  ```prefect.core.task.Parameter.info()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/task.py#L238)</span>


 ####  ```prefect.core.task.Parameter.run()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/task.py#L230)</span>
The main entrypoint for tasks.

In addition to running arbitrary functions, tasks can interact with
Prefect in a few ways:
    1. Return an optional result. When this function runs successfully,
        the task is considered successful and the result (if any) is
        made available to downstream edges.
    2. Raise an error. Errors are interpreted as failure.
    3. Raise a signal. Signals can include FAIL, SUCCESS, WAIT, etc.
        and indicate that the task should be put in the indicated
        state.
        - FAIL will lead to retries if appropriate
        - WAIT will end execution and skip all downstream tasks with
            state WAITING_FOR_UPSTREAM (unless appropriate triggers
            are set). The task can be run again and should check
            context.is_waiting to see if it was placed in a WAIT.



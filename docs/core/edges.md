 # _class_ **```prefect.core.edge.Edge```**```(upstream_task, downstream_taskkey=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/edge.py#L8)</span>
Edges represent connections between Tasks.

At a minimum, edges link an upstream_task and a downstream_task
indicating that the downstream task shouldn't run until the upstream
task is complete.

In addition, edges can specify a key that describe how upstream results
are passed to the downstream task.

Args: upstream_task (Task): the task that must run before the
    downstream_task

    downstream_task (Task): the task that will be run after the
        upstream_task. The upstream task state is passed to the
        downstream task's trigger function to determine whether the
        downstream task should run.

    key (str): Optional. Passing a key indicates
        that the upstream result should be passed to the downstream
        task as a keyword argument.

The key indicates that the result of the upstream task should be passed
to the downstream task under the key.



# Control Flow

Tasks and utilities for implementing control flow constructs like branching and rejoining flows.

## If/Else <Badge text="fn"/>
Builds a conditional branch into a workflow.

If the condition evaluates True(ish), the true_task will run. If it evaluates False(ish), the false_task will run. The task doesn't run is Skipped, as are all downstream tasks that don't set `skip_on_upstream_skip=False`.

[API Reference](/api/tasks/control_flow.html#prefect-tasks-control-flow-conditional-ifelse)


## Switch <Badge text="task"/>
Adds a SWITCH to a workflow.

The condition task is evaluated and the result is compared to the keys of the cases dictionary. The task corresponding to the matching key is run; all other tasks are skipped. Any tasks downstream of the skipped tasks are also skipped unless they set `skip_on_upstream_skip=False`.

[API Reference](/api/tasks/control_flow.html#prefect-tasks-control-flow-conditional-switch)


## Merge <Badge text="task"/>
Merges conditional branches back together.

A conditional branch in a flow results in one or more tasks proceeding and one or more tasks skipping. It is often convenient to merge those branches back into a single result. This function is a simple way to achieve that goal.

The merge will return the first real result it encounters, or `None`. If multiple tasks might return a result, group them with a list.

[API Reference](/api/tasks/control_flow.html#prefect-tasks-control-flow-conditional-merge)

## FilterTask <Badge text="task"/>
Task for filtering lists of results.

The default filter is to filter out `NoResults` and `Exceptions` for filtering out mapped results. Note that this task has a default trigger of `all_finished` and `skip_on_upstream_skip=False`.

[API Reference](/api/tasks/control_flow.html#prefect-tasks-control-flow-filter-filtertask)

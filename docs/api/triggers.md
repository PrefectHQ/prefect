---
sidebarDepth: 1
---

# Triggers
---
 ## all_finished

###  ```prefect.triggers.all_finished(upstream_states)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/triggers.py#L27)</span>
This task will run no matter what the upstream states are, as long as they are finished.


 ## manual_only

###  ```prefect.triggers.manual_only(upstream_states)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/triggers.py#L39)</span>
This task will never run automatically. It will only run if it is
specifically instructed, either by ignoring the trigger or adding it
as a flow run's start task.

Note this doesn't raise a failure, it simply doesn't run the task.


 ## always_run

###  ```prefect.triggers.always_run(upstream_states)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/triggers.py#L50)</span>
This task will run no matter what the upstream states are, as long as they are finished.


 ## never_run

###  ```prefect.triggers.never_run(upstream_states)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/triggers.py#L62)</span>
This task will never run automatically. It will only run if it is
specifically instructed, either by ignoring the trigger or adding it
as a flow run's start task.

Note this doesn't raise a failure, it simply doesn't run the task.


 ## all_successful

###  ```prefect.triggers.all_successful(upstream_states)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/triggers.py#L73)</span>
Runs if all upstream tasks were successful. Note that SKIPPED tasks are considered
successes and TRIGGER_FAILED tasks are considered failures.


 ## all_failed

###  ```prefect.triggers.all_failed(upstream_states)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/triggers.py#L86)</span>
Runs if all upstream tasks failed. Note that SKIPPED tasks are considered successes
and TRIGGER_FAILED tasks are considered failures.


 ## any_successful

###  ```prefect.triggers.any_successful(upstream_states)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/triggers.py#L99)</span>
Runs if any tasks were successful. Note that SKIPPED tasks are considered successes
and TRIGGER_FAILED tasks are considered failures.


 ## any_failed

###  ```prefect.triggers.any_failed(upstream_states)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/triggers.py#L112)</span>
Runs if any tasks failed. Note that SKIPPED tasks are considered successes and
TRIGGER_FAILED tasks are considered failures.



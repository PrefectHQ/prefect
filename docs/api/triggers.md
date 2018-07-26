---
sidebarDepth: 1
---

# Triggers
---
 ###  ```prefect.triggers.all_finished()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/triggers.py#L27)</span>
This task will run no matter what the upstream states are, as long as they are finished.


 ###  ```prefect.triggers.manual_only()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/triggers.py#L39)</span>
This task will never run automatically. It will only run if it is
specifically instructed, either by ignoring the trigger or adding it
as a flow run's start task.

Note this doesn't raise a failure, it simply doesn't run the task.


 ###  ```prefect.triggers.always_run()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/triggers.py#L50)</span>
This task will run no matter what the upstream states are, as long as they are finished.


 ###  ```prefect.triggers.never_run()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/triggers.py#L62)</span>
This task will never run automatically. It will only run if it is
specifically instructed, either by ignoring the trigger or adding it
as a flow run's start task.

Note this doesn't raise a failure, it simply doesn't run the task.


 ###  ```prefect.triggers.all_successful()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/triggers.py#L73)</span>
Runs if all upstream tasks were successful. Note that SKIPPED tasks are considered
successes and TRIGGER_FAILED tasks are considered failures.


 ###  ```prefect.triggers.all_failed()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/triggers.py#L86)</span>
Runs if all upstream tasks failed. Note that SKIPPED tasks are considered successes
and TRIGGER_FAILED tasks are considered failures.


 ###  ```prefect.triggers.any_successful()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/triggers.py#L99)</span>
Runs if any tasks were successful. Note that SKIPPED tasks are considered successes
and TRIGGER_FAILED tasks are considered failures.


 ###  ```prefect.triggers.any_failed()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/triggers.py#L112)</span>
Runs if any tasks failed. Note that SKIPPED tasks are considered successes and
TRIGGER_FAILED tasks are considered failures.



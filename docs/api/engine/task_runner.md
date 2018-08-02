---
sidebarDepth: 1
---

# TaskRunner
---
 ## TaskRunner

### <span style="background-color:rgba(27,31,35,0.05);font-size:0.85em;">class</span> ```prefect.engine.task_runner.TaskRunner(task, logger_name=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/task_runner.py#L77)</span>


 ####  ```prefect.engine.task_runner.TaskRunner.get_post_run_state(state, inputs=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/task_runner.py#L230)</span>
If the final state failed, this method checks to see if it should be retried.

 ####  ```prefect.engine.task_runner.TaskRunner.get_pre_run_state(state, upstream_states=None, ignore_trigger=False, inputs=None, parameters=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/task_runner.py#L118)</span>
Checks if a task is ready to run.

This method accepts an initial state and returns the next state that the task
should take. If it should not change state, it returns None.

 ####  ```prefect.engine.task_runner.TaskRunner.get_retry_state(inputs=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/task_runner.py#L246)</span>
Returns a Retry state with the appropriate scheduled_time and last_run_number set.

 ####  ```prefect.engine.task_runner.TaskRunner.get_run_state(state, inputs=None, parameters=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/task_runner.py#L188)</span>
Runs a task.

This method accepts an initial state and returns the next state that the task
should take. If it should not change state, it returns None.

 ####  ```prefect.engine.task_runner.TaskRunner.run(state=None, upstream_states=None, inputs=None, ignore_trigger=False, context=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/task_runner.py#L82)</span>




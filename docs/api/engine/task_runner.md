 ### _class_ **```prefect.engine.task_runner.TaskRunner```**```(tasklogger_name=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/task_runner.py#L76)</span>


 ####  **```prefect.engine.task_runner.TaskRunner.get_post_run_state```**```()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/task_runner.py#L199)</span>
If the final state failed, this method checks to see if it should be retried.

 ####  **```prefect.engine.task_runner.TaskRunner.get_pre_run_state```**```(stateupstream_states=None, ignore_trigger=False)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/task_runner.py#L110)</span>
Checks if a task is ready to run.

This method accepts an initial state and returns the next state that the task
should take. If it should not change state, it returns None.

 ####  **```prefect.engine.task_runner.TaskRunner.get_retry_state```**```()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/task_runner.py#L215)</span>
Returns a Retry state with the appropriate retry_time and last_run_number set.

 ####  **```prefect.engine.task_runner.TaskRunner.get_run_state```**```(stateinputs=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/task_runner.py#L174)</span>
Runs a task.

This method accepts an initial state and returns the next state that the task
should take. If it should not change state, it returns None.

 ####  **```prefect.engine.task_runner.TaskRunner.run```**```(state=None, upstream_states=None, inputs=None, ignore_trigger=False, context=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/task_runner.py#L81)</span>




"""
An example Flow that logs the duration of task runs
by using a task state handler.
"""
import time

import pendulum

from prefect import Flow, task


def timestamper(task, old_state, new_state):
    """
    Task state handler that timestamps new states
    and logs the duration between state changes using
    the task's logger.
    """
    new_state.timestamp = pendulum.now("utc")
    if hasattr(old_state, "timestamp"):
        duration = (new_state.timestamp - old_state.timestamp).in_seconds()
        task.logger.info(
            "{} seconds passed in between state transitions".format(duration)
        )
    return new_state


@task(state_handlers=[timestamper])
def sleeper():
    time.sleep(2)


f = Flow("log-task-duration", tasks=[sleeper])
f.run()
# INFO - prefect.FlowRunner | Beginning Flow run for 'log-task-duration'
# INFO - prefect.FlowRunner | Starting flow run.
# INFO - prefect.TaskRunner | Task 'sleeper': Starting task run...
# INFO - prefect.Task | 2 seconds passed in between state transitions
# INFO - prefect.TaskRunner | Task 'sleeper': finished task run for task with final state: 'Success'
# INFO - prefect.FlowRunner | Flow run SUCCESS: all reference tasks succeeded

# Pause for Approval

There are many situations when a workflow contains tasks that require some form of manual approval to continue. Prefect has two built-in mechanisms for achieving this pattern:

- a manual-only trigger that can be configured on a per task basis, and unconditionally prevents the task from running unless a user approves it
- a [PAUSE](/api/latest/engine/signals.html#pause) signal that can be raised programmatically when certain conditions are met and also prevents the task from running unless a user approves it

Both these mechanisms can only be resumed by an individual or event, either from the Prefect UI or GraphQL API. 

This manual-only trigger example demonstrates the functionality by running the workflow with Prefect Cloud, being alerted with a notification to request approval of a task and using the approve button to resume the task.
 
```python

from prefect import task, Flow
from prefect.triggers import manual_only

@task
def build():
    print("build task")
    return True

@task
def test(build_result):
    print("test task")
    build_result == True

@task(trigger=manual_only)
def deploy():
    """With the manual_only trigger this task will only run after it has been approved"""
    print("deploy task")
    pass
    
with Flow("code_deploy") as flow:
    res = build()
    deploy(upstream_tasks=[test(res)])

# flow.run has been commented out to register and run the flow with Prefect Cloud
# use flow.run to run and test the flow locally
# the manual only trigger will prompt to resume the task in the command line
# flow.run()

# Registers the flow with a project named pause_resume
flow.register("pause_resume")

flow.run_agent()
```

Notification for a paused task

![Notification for Task in Paused State](/idioms/pause_resume_notification.png)

Task ready for approval

![Approval to Resume Task](/idioms/pause_resume_approve.png)


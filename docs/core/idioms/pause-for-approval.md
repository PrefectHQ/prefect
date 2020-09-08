# Pause for Approval

A manual-only trigger that has been applied to a task will pause the task once it is reached. The task can only be resumed by an individual or event, either from the Prefect UI or GraphQL API. 

This example demonstrates the functionality by running the workflow with Prefect Cloud, using a cloud hook for a notification to approve the task run and then continuing with the approve button.

Cloud hook to notify of flows in a paused state.

![Cloud Hook Paused State](/idioms/pause_resume_cloud_hook.png)
 
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


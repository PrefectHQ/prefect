# Pause for Approval

A manual-only trigger that has been applied to a task will pause the task once it is reached. The task can only be resumed by an individual or event, either from the Prefect UI or GraphQL API. 

This example demonstrates the functionality by running the workflow in your local environment and surfacing a prompt to continue the flow. 

```python
from prefect import task, Flow
from prefect.triggers import manual_only

@task
def return_data():
    return [1, 2, 3]

@task(trigger=manual_only)
def process_data(xs):
    d = [i + 2 for i in xs]
    return d
    
with Flow() as flow:
    process_data(return_data)

flow.run()
```


---
description: Prefect results capture the data returned from your flows and tasks.
tags:
    - flows
    - subflows
    - tasks
    - states
    - results
---

# Results

Results represent the data returned by a flow or a task. 

## Retrieving results

When **calling** flows or tasks, the result is returned directly:

```python
from prefect import flow, task

@task
def my_task():
    return 1

@flow
def my_flow():
    task_result = my_task()
    return task_result + 1

result = my_flow()
assert result == 2
```

When working with flow and task states, the result can be retreived with the `State.result()` method:

```python
from prefect import flow, task

@task
def my_task():
    return 1

@flow
def my_flow():
    state = my_task(return_state=True)
    return state.result() + 1

state = my_flow(return_state=True)
assert state.result() == 2
```

When submitting tasks to a runner, the result can be retreived with the `Future.result()` method:

```python
from prefect import flow, task

@task
def my_task():
    return 1

@flow
def my_flow():
    future = my_task.submit()
    return future.result() + 1

result = my_flow())
assert result == 2
```

## Handling failures

Sometimes your flows or tasks will encounter an **exception**. Prefect captures all exceptions in order to report states to the orchestrator, but we do not hide them from you (unless you ask us to) as your program needs to know if an unexpected error has occurred.

When **calling** flows or tasks, the exceptions are raised as in normal Python:

```python
from prefect import flow, task

@task
def my_task():
    raise ValueError()

@flow
def my_flow():
    try:
        my_task()
    except ValueError:
        print("Oh no! The task failed.")
    
    return True

my_flow()
```

If you would prefer to check for a failed task without using `try/except`, you may ask Prefect to return the state:

```python
from prefect import flow, task

@task
def my_task():
    raise ValueError()

@flow
def my_flow():
    state = my_task(return_state=True)

    if state.is_failed():
        print("Oh no! The task failed. Falling back to '1'.")
        result = 1
    else:
        result = state.result()

    return result + 1

result = my_flow()
assert result == 2
```

If you retrieve the result from a failed state, the exception will be raised. For this reason, it's often best to check if the state is failed first. 

```python
from prefect import flow, task

@task
def my_task():
    raise ValueError()

@flow
def my_flow():
    state = my_task(return_state=True)

    try:
        result = state.result()
    except ValueError:
        print("Oh no! The state raised the error!")
    
    return True

my_flow()
```

When retrieving the result from a state, you can ask Prefect not to raise exceptions:

```python
from prefect import flow, task

@task
def my_task():
    raise ValueError()

@flow
def my_flow():
    state = my_task(return_state=True)

    maybe_result = state.result(raise_on_failure=False)
    if isinstance(maybe_result, ValueError):"
        print("Oh no! The task failed. Falling back to '1'.")
        result = 1
    else:
        result = maybe_result
    
    return result + 1

result = my_flow()
assert result == 2
```

When submitting tasks to a runner, `Future.result()` works the same as `State.result()`:

```python
from prefect import flow, task

@task
def my_task():
    raise ValueError()

@flow
def my_flow():
    future = my_task.submit()

    try:
        future.result()
    except ValueError:
        print("Ah! Futures will raise the failure as well.")

    # You can ask it not to raise the exception too
    maybe_result = future.result(raise_on_failure=False)
    print(f"Got {type(maybe_result)}")

    return True

my_flow()
```

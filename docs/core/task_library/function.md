# Functions

The `FunctionTask` turns any function into a task, including inputs and outputs. Users will often use this task via Prefect's `@task` decorator:

```python
@task
def add_one(x):
    return x + 1

# roughly equivalent to:
FunctionTask(fn=lambda x: x + 1)
```

## FunctionTask <Badge text="task"/>

A convenience Task for functionally creating Task instances with arbitrary callable `run` methods. This is the Task that powers Prefect's `@task` decorator.

[API Reference](/api/unreleased/tasks/function.html#prefect-tasks-core-function-functiontask)

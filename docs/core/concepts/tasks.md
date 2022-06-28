# Tasks

## Overview

A `Task` represents a discrete action in a Prefect workflow.

A task is like a function: it optionally takes inputs, performs an action, and produces an optional result. In fact, the easiest way to create a task is by decorating a Python function:

```python
from prefect import task

@task
def plus_one(x):
    return x + 1
```

For more sophisticated tasks that may require customization, you can subclass the `Task` class directly:

```python
from prefect import Task

class HTTPGetTask(Task):

    def __init__(self, username, password, **kwargs):
        self.username = username
        self.password = password
        super().__init__(**kwargs)

    def run(self, url):
        return requests.get(url, auth=(self.username, self.password))
```

All `Task` subclasses must have a `run()` method.

!!! tip Tasks may be run individually
    A task's `run` method can be called anytime for testing:

    ```python
    plus_one.run(2)  # 3
    ```



Tasks allow a great deal of customization via arguments that may be provided to either the `Task` class constructor or the `@task` decorator. Examples include retry behavior, triggers, names, tags, and more. For a complete description, see the [Task API docs](/api/latest/core/task.html).

When using the `@task` decorator, you can override arguments on a per-task basis by passing them to a special `task_args` keyword argument:

```python
@task(name="a")
def add_one(x):
    return x + 1

with Flow("Add One") as flow:
    a = add_one(1)
    b = add_one(2, task_args=dict(name="b"))

assert a.name == "a"
assert b.name == "b"
```

!!! tip How big should a task be?
    People often wonder how much code to put in each task.

    Prefect encourages "small tasks" -- each one should represent a single logical step of your workflow. This allows Prefect to better contain task failures.

    To be clear, there's nothing stopping you from putting all of your code in a single task -- Prefect will happily run it! However, if any line of code fails, the entire task will fail and need to be retried from the beginning. This can be trivially avoided by splitting the code into multiple dependent tasks.


## Retries

One of the most common reasons to put code in a Prefect task is to automatically retry it on failure. To enable retries, pass appropriate `max_retries` and `retry_delay` parameters to your task:

```python
# this task will retry up to 3 times, waiting 10 minutes between each retry
Task(max_retries=3, retry_delay=datetime.timedelta(minutes=10))
```

!!! tip Retries don't create new task runs
    A new task run is not created when a task is retried. A new state is added to the state history of the original task run.


## Triggers

Before a Prefect task runs, it evaluates a "trigger function" to decide whether it should run at all. Triggers are functions that receive the states of any upstream tasks and return `True` if the task should run, or `False` (or raise an error) otherwise. If a task's trigger fails and does not raise a more specific error, the task will enter a `TriggerFailed` state, which is a more specific type of `Failed` state that indicates that the task failed to run, but because of its trigger function, not its own code.

!!! tip Skips are treated as successes
    In Prefect, skipped tasks are treated as if they succeeded. This is because skips only take place if users want them to, so they represent the "successful" execution of a user's design. However, by default, skips also propagate: a task that follows a skipped task will also skip, unless it receives `skip_on_upstream_skip=False`.


Built-in trigger functions include:

- `all_successful`: This is the default trigger, and will only allow tasks to run if all upstream tasks succeeded.
- `all_failed`: Tasks will only run if all upstream tasks failed.
- `any_successful`: Tasks will run if at least one upstream task succeeded.
- `any_failed`: Tasks will run if at least one upstream task failed.
- `all_finished`: Tasks will run as long as all upstream tasks finished. This is equivalent to "always run", because Prefect tasks are only evaluated when their upstream tasks finish.
- `manual_only`: This trigger is unique in that it won't let the task run at all. Tasks will always enter a `Paused` state when the `manual_only` trigger runs. Users can cause those tasks to run by explicitly putting them in a `Resume` state. Therefore, this trigger is a useful way to introduce a mandatory break into a workflow.

Users can also supply any function that has the following signature, though we encourage users to put custom logic in the task's `run()` method instead:

```python
trigger_fn(upstream_states: Set[State]) -> bool
```

## Constants

If a non-`Task` input is provided to a task, it is automatically converted to a `Constant`.

```python
from prefect import Flow, task

@task
def add(x, y):
    return x + y

with Flow('Flow With Constant') as flow:
    output = add(1, 2)

assert len(flow.tasks) == 1
assert len(flow.constants[output]) == 2
```

Prefect will attempt to automatically turn Python objects into `Constants`, including collections (like `lists`, `tuples`, `sets`, and `dicts`). If the resulting constant is used directly as the input to a task, it is optimized out of the task graph and stored in the `flow.constants` dict. However, if the constant is mapped over, then it remains in the dependency graph.

## Operators

When using the [functional API](flows.html#functional-api), Prefect tasks support basic mathematical and logical operators. For example:

```python
import random
from prefect import Flow, task

@task
def a_number():
    return random.randint(0, 100)

with Flow('Using Operators') as flow:
    a = a_number()
    b = a_number()

    add = a + b
    sub = a - b
    lt = a < b
    # etc
```

These operators automatically add new tasks to the active flow context.

!!! warning Operator validation
    Because Prefect flows are not executed when you create them, Prefect can not validate that operators are being applied to compatible types. For example, you could subtract a task that produces a list from a task that produces an integer. This would create an error at runtime, but not during task definition.


## Collections

When using the [functional API](flows.html#functional-api), Prefect tasks can automatically be used in collections. For example:

```python
import random
from prefect import Flow, task

@task
def a_number():
    return random.randint(0, 100)

@task
def get_sum(x):
    return sum(x)

with Flow('Using Collections') as flow:
    a = a_number()
    b = a_number()
    s = get_sum([a, b])
```

In this case, a `List` task will automatically be created to take the results of `a` and `b` and put them in a list. That automatically-created task becomes the sole upstream dependency of `s`.

Prefect will perform automatic collection extraction for lists, tuples, sets, and dictionaries.

## Indexing

When using the [functional API](flows.html#functional-api), Prefect tasks can be indexed to retrieve specific results.

```python
from prefect import Flow, task

@task
def fn():
    return {'a': 1, 'b': 2}


with Flow('Indexing Flow') as flow:
    x = fn()
    y = x['a']
```

This will automatically add a `GetItem` task to the flow that receives `x` as its input and attempts to perform `x['a']`. The result of that task (`1`) is stored as `y`.

!!! warning Key validation
    Because Prefect flows are not executed when you create them, Prefect can not validate that the indexed key is available ahead of time. Therefore, Prefect will allow you to index any task by any value. If the key does not exist when the flow is actually run, a runtime error will be raised.


## Multiple Return Values

Sometimes your task may have multiple return values that you want to deal with
separately. By default Prefect tasks aren't iterable, so the standard Python
pattern will error:

```python
from prefect import Flow, task

@task
def inc_and_dec(x):
    return x + 1, x - 1

with Flow("This Errors") as flow:
    # This raises a TypeError, since Prefect doesn't know how many values
    # `inc_and_dec` returns
    inc, dec = inc_and_dec(1)
```

To make this work, you need to let Prefect know how many return values your
task has. You can do this by either:

- Passing in `nout` to the `@task` decorator or the `Task` constructor when defining your task.
- Providing a return type annotation for your task (in a class-based task, this
  would go on the `run` method).

For example:

```python
# Passing in `nout` explicitly
@task(nout=2)
def inc_and_dec(x):
    return x + 1, x - 1

# Using a return type annotation
from typing import Tuple

@task
def double_and_triple(x: int) -> Tuple[int, int]:
    return x * 2, x * 3

with Flow("This works") as flow:
    inc, dec = inc_and_dec(1)
    double, triple = double_and_triple(inc)
```

Note that multiple return values can also be used by explicitly indexing tasks
(as described above). Providing `nout` or a return type annotation only adds
the convenience of tuple unpacking.

## Mapping

_For more detail, see the [mapping concept docs](mapping.html)._

Generally speaking, Prefect's [functional API](flows.html#functional-api) allows you to call a task like a function.

In addition, you can call `Task.map()` to automatically map a task over its inputs. Prefect will generate a dynamic copy of the task for each element of the input. If you don't want an input to be treated as iterable (for example, you want to provide it to every dynamic copy), just wrap it with Prefect's `unmapped()` annotation.

```python
from prefect import task, unmapped

@task
def add(x, y):
    return x + y

add.map(x=[1, 2, 3], y=unmapped(1))
```

Maps can be composed, allowing the creation of powerful dynamic pipelines:

```python
z1 = add.map(x=[1, 2, 3], y=unmapped(1))
z2 = add.map(x=z1, y=unmapped(100))
```

In addition, if the result of a mapped task is passed to an un-mapped task (or used as the `unmapped` input to a mapped task), then its results will be collected in a list. This allows transparent but totally flexible map/reduce functionality.

## Flattening

_For more detail, see the [mapping concept docs](mapping.html)._

To "un-nest" a task that returns a list of lists, use Prefect's `flatten()` annotation. This is most useful when a task in a mapped pipeline returns a sequence.

## Identification

### Name

A task may be given an optional `name`; if not provided, it will be taken from the task's class name (or function name, in the case of the `@task` decorator). Names are purely for user convenience: they are used to render the task in various visualizations, and can also be used when querying for information about specific tasks. There are no restrictions on task names, and two tasks may have the same name.

```python
# assigning a name to a Task instance
t = Task(name="My Task")

# assigning a name to a decorated task function
@task(name="My Other Task")
def my_task():
    pass
```

### Slug

Slugs are similar to ids, because Prefect will not allow two tasks with the same slug to both be in the same flow. Therefore, a slug can serve as an optional human-readable unique identifier. If not provided, it will automatically be generated based on the task name, its tags, and the order in which it was added to the Flow.

```python
Task(slug="my-task")
```

### Tags

Sometimes, it is useful to group a variety a tasks in multiple ways. Prefect provides `tags` for this purpose. Tags may be specified either as a keyword argument or with a convenient context manager. The context manager can be nested.

```python
from prefect import tags

with tags('red', 'blue'):
    t = Task()

assert t.tags == {'red', 'blue'}
```

### Retrieving tasks

While identifying attributes are most useful when querying for tasks in Prefect Cloud and applying some advanced tag-based features, they can be used locally with a flow's `get_tasks()` function. This will return any tasks that match all of the provided arguments. For example:

```python
flow.get_tasks(name='my-task')
flow.get_tasks(tags=['red'])
```

## State handlers

State handlers allow users to provide custom logic that fires whenever a task changes state. For example, you could send a Slack notification if the task failed -- we actually think that's so useful we included it [here](/api/latest/utilities/notifications.html#functions)!

State handlers must have the following signature:

```python
state_handler(task: Task, old_state: State, new_state: State) -> State
```

The handler is called anytime the task's state changes, and receives the task itself, the old state, and the new state. The state that the handler returns is used as the task's new state.

If multiple handlers are provided, they are called in sequence. Each one will receive the "true" `old_state` and the `new_state` generated by the previous handler.

Handlers can also be associated with the `Flow`, `TaskRunner`, and `FlowRunner` classes. The task-level handlers are called first.

## Caching

Tasks can be cached, in which case their outputs will be reused for future runs. For example, you might want to make sure that a database is loaded before generating reports, but you might not want to run the load task every time the flow is run. No problem: just cache the load task for 24 hours, and future runs will reuse its successful output.

For more details, see the relevant docs under [execution](./execution.html#caching).

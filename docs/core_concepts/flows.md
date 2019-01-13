# Flows

## Overview

A `Flow` is a container for `Tasks`. It represents an entire workflow or application by describing the dependencies between tasks.

## APIs

### Functional API

The most convenient way to build a Prefect pipeline is with the **functional API**. The functional API is available any time you enter a `Flow` context. In this mode, you can call `Tasks` on other `Tasks` as if they were functions, and Prefect will build up a computational graph in the background by modifying the flow appropriately.

For example:

```python
from prefect import task, Task, Flow
import random

@task
def random_number():
    return random.randint(0, 100)

@task
def plus_one(x):
    return x + 1

with Flow('My Functional Flow') as flow:
    r = random_number()
    y = plus_one(x=r)
```

::: tip Using Task Subclasses with the Functional API
Note that in order to use a `Task` subclass with the functional API (as opposed to a `@task`-decorated function), you need to instantiate the class before calling it:

```python
class PlusOneTask(Task):
    def run(self, x):
        return x + 1

with Flow():
    task = PlusOneTask() # first create the Task instance
    result = task(10) # then call it with arguments
```

Instantiation is when properties including the task's `retry_delay`, `trigger`, and `caching` mechanisms are set. With the functional API, these properties can be passed as arguments to the `@task` decorator.

:::

### Imperative API

Prefect's **imperative API** allows more fine-grained control. Its main advantage over the functional API is that it allows tasks to be set as upstream or downstream dependencies without passing their results. This allows you to create a strict ordering of tasks through **state dependencies** without also creating **data dependencies**.

```python
from prefect import Task, Flow

class RunMeFirst(Task):
    def run(self):
        print("I'm running first!")

class PlusOneTask(Task):
    def run(self, x):
        return x + 1

flow = Flow('My Imperative Flow')
plus_one = PlusOneTask()
flow.set_dependencies(
    task=plus_one,
    upstream_tasks=[RunMeFirst()],
    keyword_tasks=dict(x=10))

flow.visualize()
```

![](/assets/concepts/imperative_flow_example.png)

::: tip
`flow.set_dependencies()` and `task.set_dependencies()` (the latter is only available inside an active flow context) are the main entrypoints for the imperative API. Flows also provide some lower-level methods like `add_task()` and `add_edge()` that can be used to manipulate the graph directly.
:::

## Running a flow

To run a flow, simply call `flow.run()`:

```python
from prefect import task, Flow

@task
def say_hello():
    print('Hello, world!')

with Flow() as flow:
    h = say_hello()

flow.run() # prints "Hello, world!"
```

This will return a `State` object representing the outcome of the run. To receive task states as well, supply a `return_tasks` argument to `flow.run()`:

```python
state = flow.run(return_tasks=[h])
state.result[h] # the task state of the say_hello task
```

:::tip Task classes vs Task instances
Notice that we passed `return_tasks=[h]`, not `return_tasks=[say_hello]`. This is because `h` represents a specific instance of a task that is contained inside the flow, whereas `say_hello` is just a generator of such tasks. Similarly, with a custom subclass, we would pass the task instance rather than the subclass itself.
:::

## Schedules

Prefect treats flows as functions, which means they can be run at any time, with any concurrency, for any reason.

However, flows may also have schedules. In Prefect terms, a schedule is nothing more than a way to indicate that you want to start a new run at a specific time. Even if a flow has a schedule, you may still run it manually.

For more information, see the [Schedules concept doc](schedules.html).

## Key tasks

### Terminal tasks

The terminal tasks of the flow are any tasks that have no downstream dependencies -- they are the last tasks to run.

Flows are not considered `Finished` until all of their terminal tasks finish, and will remain `Running` otherwise. By default, terminal tasks are also the flow's [reference tasks](#reference-tasks), and therefore determine its state.

:::tip Run order
Prefect does not guarantee the order in which tasks will run, other than that tasks will not run before their upstream dependencies are evaluated. Therefore, you might have a terminal task that actually runs before other tasks in your flow, as long as it does not depend on those tasks.
:::

### Reference tasks

When a flow runs, its state is determined by the state of its reference tasks. By default, a flow's reference tasks are its terminal tasks, which includes any task that has no downstream tasks. If the reference tasks are all successful (including any skipped tasks), the flow is considered a `Success`. If any reference tasks fail, the flow is considered `Failed`. No matter what state the reference tasks are in, the flow is considered `Pending` if any of its tasks are unfinished.

```python

with Flow() as flow:
    a, b, c = Task(), Task(), Task()
    flow.add_edge(a, b)
    flow.add_edge(b, c)

# by default, the reference tasks are the terminal tasks
assert flow.reference_tasks() == {c}
```

::: tip When should you change the reference tasks?

Generally, a flow's terminal tasks are appropriate reference tasks. However, there are times when that isn't the case.

Consider a flow that takes some action, and has a downstream task that only runs if the main action fails, in order to clean up the environment. If the main task fails and the clean up task is successful, was the flow as a whole successful? To some users, the answer is yes: the clean up operation worked as expected. To other users, the answer is no: the main purpose of the flow was not achieved.

Custom reference tasks allow you to alter this behavior to suit your needs.

:::

## Environments

Flows can have `Environment` objects attached, which describe how to serialize and execute the flow. For example, environment could be used to run a flow locally, or in a Docker container, or from a source code repository.

For more information, see the [Environments concept doc](environments.html).

## Serialization

Flow metadata can be serialized by calling the flow's `serialize()` method. If the flow has an `Environment`, then `build=True` may be passed to build the environment and prepare the flow for remote execution.

## Retrieving tasks

Flows can contain many tasks, and it can be challenging to find the exact task you need. Fortunately, the `get_tasks()` method makes this simpler. Pass any of the various [task identification](tasks.html#identification) keys to the function, and it will retrieve any matching tasks.

```python
# any tasks with the name "my task"
flow.get_tasks(name="my task")

# any tasks with the name "my task" and the "blue" tag
flow.get_tasks(name="my task", tags=["blue"])

# the task with the slug "x"
flow.get_tasks(slug="x")
```

## State handlers

State handlers allow users to provide custom logic that fires whenever a flow changes state. For example, you could send a Slack notification if the flow failed -- we actually think that's so useful we included it [here](/api/utilities/notifications.html#functions)!

State handlers must have the following signature:

```python
state_handler(flow: Flow, old_state: State, new_state: State) -> State
```

The handler is called anytime the flow's state changes, and receives the flow itself, the old state, and the new state. The state that the handler returns is used as the flow's new state.

If multiple handlers are provided, they are called in sequence. Each one will receive the "true" `old_state` and the `new_state` generated by the previous handler.

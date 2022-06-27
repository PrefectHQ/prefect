# Using conditional logic in a Flow

Sometimes you have parts of a flow that you only want to run under certain
conditions. To support this, Prefect provides several built-in [tasks for
control-flow](/api/latest/tasks/control_flow.html) that you can use to add
conditional branches to your flow.

## Running a task based on a condition

Let's say you want to have a flow where different tasks are run based on the
result of some conditional task.  In normal Python code this logic might look
like:

```python
if check_condition():
    val = action_if_true()
    another_action(val)
else:
    val = action_if_false()
    another_action(val)
```

To implement the same logic as a Flow, you can make use of Prefect's `case`
blocks. Tasks added to a flow inside a `case` block are only run if the
condition matches the case. Tasks in branches that aren't run will finish with
a `Skipped` state.

The resulting flow looks like:

![Flow with conditional branches](/idioms/conditional-branches.png)


Functional API:

```python
from random import random

from prefect import task, Flow, case

@task
def check_condition():
    return random() < .5

@task
def action_if_true():
    return "I am true!"

@task
def action_if_false():
    return "I am false!"

@task
def another_action(val):
    print(val)


with Flow("conditional-branches") as flow:
    cond = check_condition()

    with case(cond, True):
        val = action_if_true()
        another_action(val)

    with case(cond, False):
        val = action_if_false()
        another_action(val)
```

Imperative API:

```python
from random import random

from prefect import Task, Flow, case

class CheckCondition(Task):
    def run(self):
        return random() < 0.5

class ActionIfTrue(Task):
    def run(self):
        return "I am true!"

class ActionIfFalse(Task):
    def run(self):
        return "I am false!"

class AnotherAction(Task):
    def run(self, val):
        print(val)


flow = Flow("conditional-branches")

check_condition = CheckCondition()
flow.add_task(check_condition)

with case(check_condition, True):
    val = ActionIfTrue()
    flow.add_task(val)
    AnotherAction().bind(val=val, flow=flow)

with case(check_condition, False):
    val = ActionIfFalse()
    flow.add_task(val)
    AnotherAction().bind(val=val, flow=flow)
```

## Merging branches in a flow

Looking at the above flow, you might notice that `another_action` is run on the
output of a task regardless of which branch is taken. If you were writing this
in normal Python code, you might refactor the logic as:

```python
if check_condition():
    val = action_if_true()
else:
    val = action_if_false()

another_action(val)
```

To implement the same logic as a Flow, you can make use of Prefect's `merge`
function. This function takes one or more tasks conditional tasks, and returns
the output of the first task that isn't `Skipped`. This can be used to "merge"
multiple branches in a flow together.

The resulting flow looks like:

![Flow with conditional branches](/idioms/conditional-branches-merge.png)


Functional API:
```python
from random import random

from prefect import task, Flow, case
from prefect.tasks.control_flow import merge

@task
def check_condition():
    return random() < .5

@task
def action_if_true():
    return "I am true!"

@task
def action_if_false():
    return "I am false!"

@task
def another_action(val):
    print(val)


with Flow("conditional-branches") as flow:
    cond = check_condition()

    with case(cond, True):
        val1 = action_if_true()

    with case(cond, False):
        val2 = action_if_false()

    val = merge(val1, val2)

    another_action(val)
```

Imperative API:
```python
from random import random

from prefect import Task, Flow, case
from prefect.tasks.control_flow import merge

class CheckCondition(Task):
    def run(self):
        return random() < 0.5

class ActionIfTrue(Task):
    def run(self):
        return "I am true!"

class ActionIfFalse(Task):
    def run(self):
        return "I am false!"

class AnotherAction(Task):
    def run(self, val):
        print(val)


flow = Flow("conditional-branches")

check_condition = CheckCondition()
flow.add_task(check_condition)

with case(check_condition, True):
    val1 = ActionIfTrue()
    flow.add_task(val1)

with case(check_condition, False):
    val2 = ActionIfFalse()
    flow.add_task(val2)

val = merge(val1, val2, flow=flow)
AnotherAction().bind(val=val, flow=flow)
```


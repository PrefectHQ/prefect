
# Creating (conditional) branches in a flow

Since Prefect flows are represented as DAGs it is easy to add branching logic to a flow. By default branches can be specified by setting upstreams and downstreams to tasks in the flow. To take it a step further, Prefect also has concepts built in to allow for conditional branching based on task outputs.

### Adding branches to a flow

Let's use the following example. I have a piece of data that I want to perform some arithmetic on and then output that resulting value. My flow would look something like this:

![Flow with Branching](/faq/branching.png)

By using Prefect's syntax definition for setting task upstreams and downstreams this can be accomplished without any extras.

:::: tabs
::: tab "Functional API"
```python
from prefect import task, Flow

@task
def get_number():
    return 10

@task
def multiply(n):
    return n * 10

@task
def divide(n):
    return n / 10

@task
def output_value(value):
    print(value)

with Flow("branches") as flow:
    n = get_number()

    m = multiply(n)
    d = divide(n)

    output_value(m)
    output_value(d)
```
:::

::: tab "Imperative API"
```python
from prefect import Task, Flow

class GetNumber(Task):
    def run(self):
        return 10

class Multiply(Task):
    def run(self, n):
        return n * 10

class Divide(Task):
    def run(self, n):
        return n / 10

class OutputValue(Task):
    def run(self, value):
        print(value)

flow = Flow("branches")

n = GetNumber()

m = Multiply()
d = Divide()

m.set_upstream(n, key="n", flow=flow)
d.set_upstream(n, key="n", flow=flow)

output_1 = OutputValue()
output_2 = OutputValue()

output_1.set_upstream(m, key="value", flow=flow)
output_2.set_upstream(d, key="value", flow=flow)
```
:::
::::

### Branching based on conditional logic

Prefect ships with various [tasks for control logic](/core/task_library/control_flow.html) that you can use off-the-shelf to control the branching structure of your flow. This is especially useful in cases where under certain conditions you want to control which branches of your flow run based on upstream events. Branches that you don't want to run should enter a `Skipped` state.

Let's say you want to have a flow where some conditional task is evaluated and then the downstream branches are run depending on the output of that conditional task. An example of this might look like the following:

![Flow with Conditional Branching](/faq/conditional_branch.png)

If you choose to use some of Prefect's default control flow tasks such as `ifelse` and `merge` then Prefect will automatically add some additional tasks to your flow:

![Flow with ifelse and merge](/faq/if_else_merge.png)

In this flow, Prefect's control tasks do some boolean casting and conditional checks for you with the `ifelse` task performing the check `if true then take the true branch, else take the false branch`. The `merge` task is used to bring your conditional branches back together after completion. For more information on control flow tasks take a look at their [API documentation](/core/task_library/control_flow.html). The code for a flow using these control flow tasks will look something like the following:

:::: tabs
::: tab "Functional API"
```python
from random import random

from prefect import task, Flow
from prefect.tasks.control_flow.conditional import ifelse, merge

@task
def check_condition():
    return random() < .5

@task
def action_if_true():
    print("I am true!")

@task
def action_if_false():
    print("I am false!")

with Flow("conditional-branches") as flow:
    true_branch = action_if_true()
    false_branch = action_if_false()
    ifelse(check_condition(), true_branch, false_branch)

    merged_result = merge(true_branch, false_branch)
```
:::

::: tab "Imperative API"
```python
from random import random

from prefect import Task, Flow
from prefect.tasks.control_flow.conditional import CompareValue, Merge

class CheckCondition(Task):
    def run(self):
        return random() < 0.5

class AsBool(Task):
    def run(self, x):
        return bool(x)

class ActionIfTrue(Task):
    def run(self):
        print("I am true!")

class ActionIfFalse(Task):
    def run(self):
        print("I am false!")

flow = Flow("conditional-branches")

check_condition = CheckCondition()

as_bool = AsBool()
as_bool.set_upstream(check_condition, key="x", flow=flow)


compare_true = CompareValue(True)
compare_false = CompareValue(False)
compare_true.set_upstream(as_bool, key="value", flow=flow)
compare_false.set_upstream(as_bool, key="value", flow=flow)

true_branch = ActionIfTrue()
false_branch = ActionIfFalse()
true_branch.set_upstream(compare_true, flow=flow)
false_branch.set_upstream(compare_false, flow=flow)

merge = Merge()
merge.set_upstream(true_branch, key="task1", flow=flow)
merge.set_upstream(false_branch, key="task2", flow=flow)
```
:::
::::

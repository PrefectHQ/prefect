# Use task mapping to map over a specific set of arguments

[Mapping](/core/concepts/mapping.html) in Prefect is a great way for dynamic task creation and parallel execution. Sometimes you may want to pass extra arguments to functions that you're using to map over inputs but you don't want to map over those extra arguments. This is where Prefect's [`unmapped`](/api/latest/utilities/tasks.html#unmapped) operator can come into play.

In this example let's take a flow where we want to pass in a [Parameter](/core/concepts/parameters.html) `multiple` to be multiplied against a random list of numbers also specified with a `total` Parameter. This random list of numbers will be generated at runtime. If your tasks map over iterables that are generated at runtime then Prefect will dynamically build the DAG based on those values.

![Unmapped Option](/faq/unmapped.png)

This flow is going to map over the output from the `get_numbers` task, generating `total` additional tasks with random numbers, and then it is going to output each of those numbers multiplied by the supplied `multiple`.

Functional API:
```python
from random import sample

from prefect import Flow, Parameter, task, unmapped

@task
def get_numbers(total):
    return sample(range(100), total)

@task
def output_value(n, multiple):
    print(n * multiple)

with Flow("unmapped-values") as flow:
    total = Parameter("total")
    multiple = Parameter("multiple")

    numbers = get_numbers(total)

    output_value.map(numbers, multiple=unmapped(multiple))
```

Imperative API:
```python
from random import sample

from prefect import Flow, Parameter, Task, unmapped

class GetNumbers(Task):
    def run(self, total):
        return sample(range(100), total)

class OutputValue(Task):
    def run(self, n, multiple):
        print(n * multiple)

flow = Flow("unmapped-values")

total = Parameter("total")
multiple = Parameter("multiple")

numbers = GetNumbers()
numbers.set_upstream(total, key="total", flow=flow)

output_value = OutputValue()
output_value.set_upstream(numbers, key="n", mapped=True, flow=flow)
output_value.set_upstream(multiple, key="multiple", mapped=False, flow=flow)
```


# Parallelism within a Prefect flow

Prefect supports fully asynchronous / parallel running of a flow's tasks and the preferred method for doing this is using [Dask](https://dask.org/). By connecting to a Dask scheduler, a flow can begin executing its tasks on either local or remote Dask workers. Parallel execution is incredibly useful when executing many mapped tasks simultaneously but for this example you will see a flow that has three pre-defined tasks at the same level that we want to execute asynchronously in order to better visualize it.

![Parallel Tasks](/faq/parallel.png)

This flow takes in a [Parameter](/core/concepts/parameters.html) `stop` and then in three separate tasks it generates random numbers up until that `stop`. Those numbers are then turned into a list and their sum is printed in the final `sum_numbers` task.

Functional API:
```python
from random import randrange

from prefect import task, Flow, Parameter

@task
def random_num(stop):
    number = randrange(stop)
    print(f"Your number is {number}")
    return number

@task
def sum_numbers(numbers):
    print(sum(numbers))

with Flow("parallel-execution") as flow:
    stop = Parameter("stop")

    number_1 = random_num(stop)
    number_2 = random_num(stop)
    number_3 = random_num(stop)

    sum_numbers = sum_numbers(numbers=[number_1, number_2, number_3])
```

Imperative API:
```python
from random import randrange

from prefect import Flow, Parameter, Task

class RandomNum(Task):
    def run(self, stop):
        number = randrange(stop)
        print(f"Your number is {number}")
        return number

class Sum(Task):
    def run(self, numbers):
        print(sum(numbers))

flow = Flow("parallel-execution")

stop = Parameter("stop")

number_1 = RandomNum()
number_2 = RandomNum()
number_3 = RandomNum()

stop.set_downstream(number_1, key="stop", flow=flow)
stop.set_downstream(number_2, key="stop", flow=flow)
stop.set_downstream(number_3, key="stop", flow=flow)

sum_numbers = Sum()

sum_numbers.bind(numbers=[number_1, number_2, number_3], flow=flow)
```


By default Prefect uses a
[LocalExecutor](/api/latest/executors.html#localexecutor) which executes
tasks serially. However, the above flow could be run in parallel. To enable
parallelism, you can swap out the executor for either a
[DaskExecutor](/api/latest/executors.html#daskexecutor) or a
[LocalDaskExecutor](/api/latest/executors.md#localdaskexecutor) (see
[Choosing an
Executor](/orchestration/flow_config/executors.html#choosing-an-executor) for
info on which executor makes sense for your flows).

Using a `LocalDaskExecutor`:

```python
from prefect.executors import LocalDaskExecutor
flow.run(parameters={"stop": 5}, executor=LocalDaskExecutor())
```

Using a `DaskExecutor`:

```python
from prefect.executors import DaskExecutor

# If run in a script, you'll need to call `flow.run` from within an
# `if __name__ == "__main__"` block. This isn't needed if using
# prefect with Dask in an interactive terminal/notebook.
if __name__ == "__main__":
    flow.run(parameters={"stop": 5}, executor=DaskExecutor())
```

For more information on using Prefect's executors (and Dask) see the
[Executors docs](/orchestration/flow_config/executors.html#choosing-an-executor).

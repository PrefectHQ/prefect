# Parallelism within a Prefect flow

Prefect supports fully asynchronous / parallel running of a flow's tasks and the preferred method for doing this is using [Dask](https://dask.org/). By connecting to a Dask scheduler, a flow can begin executing its tasks on either local or remote Dask workers. Parallel execution is incredibly useful when executing many mapped tasks simultaneously but for this example you will see a flow that has three pre-defined tasks at the same level that we want to execute asynchronously in order to better visualize it.

![Parallel Tasks](/faq/parallel.png)

This flow takes in a [Parameter](/core/concepts/parameters.html) `stop` and then in three separate tasks it generates random numbers up until that `stop`. Those numbers are then turned into a list and their sum is printed in the final `sum_numbers` task.

:::: tabs
::: tab "Functional API"
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
:::

::: tab "Imperative API"
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
:::
::::

Whenever you run this flow it will by default use Prefect's [`LocalExecutor`](/api/latest/engine/executors.html#localexecutor) which executes tasks synchronously. This means that you will always see the tasks executed in the same order without any parallelization. In order to start executing the tasks in parallel you should run the flow with a [`DaskExecutor`](/api/latest/engine/executors.html#daskexecutor). The Dask Executor is responsible for taking the tasks of this flow and executing them on various Dask workers. You can start using the Dask Executor instantly by importing it and passing it into the flow's run function.

```python
from prefect.engine.executors import DaskExecutor
flow.run(parameters={"stop": 5}, executor=DaskExecutor())
```

By not specifying a scheduler address the Dask Executor will create a local Dask cluster, begin executing tasks on it, and then it will be torn down upon flow completion. If you stand up a Dask cluster somewhere else then a scheduler address can be provided to distribute task execution to the remote Dask cluster.

```sh
# in a new terminal window
> dask-scheduler
# Scheduler at: tcp://10.0.0.41:8786

# in new terminal windows
> dask-worker tcp://10.0.0.41:8786
> dask-worker tcp://10.0.0.41:8786
```

```python
flow.run(parameters={"stop": 5}, executor=DaskExecutor(address="tcp://10.0.0.41:8786))
```

Now that you are using Dask for execution you should see the random number generation tasks in the flow execute asynchronously. For more information on execution with Dask check out [this document](/core/advanced_tutorials/dask-cluster.html).

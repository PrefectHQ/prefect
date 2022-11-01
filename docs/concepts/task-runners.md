---
description: Prefect task runners let you specify the executors for tasks in a flow run, including returning a PrefectFuture contianing both results and state. 
tags:
    - tasks
    - task runners
    - executors
    - PrefectFuture
    - submit
    - concurrent execution
    - sequential execution
    - parallel execution
    - Dask
    - Ray
---

# Task runners

Task runners enable you to engage specific executors for Prefect tasks, such as for concurrent, parallel, or distributed execution of tasks.

Task runners are not required for task execution. If you call a task function directly, the task executes as a regular Python function, without a task runner, and produces whatever result is returned by the function.

## Task runner overview

Calling a task function from within a flow, using the default task settings, executes the function sequentially. Execution of the task function blocks execution of the flow until the task completes. This means, by default, calling multiple tasks in a flow causes them to run in order. 

However, that's not the only way to run tasks!

You can use the `.submit()` method on a task function to submit the task to a _task runner_. Using a task runner enables you to control whether tasks run sequentially, concurrently, or if you want to take advantage of a parallel or distributed execution library such as Dask or Ray.

Using the `.submit()` method to submit a task also causes the task run to return a [`PrefectFuture`](/api-ref/prefect/futures/#prefect.futures.PrefectFuture), a Prefect object that contains both any _data_ returned by the task function and a [`State`](/api-ref/orion/schemas/states/), a Prefect object indicating the state of the task run.

Prefect currently provides the following built-in task runners: 

- [`SequentialTaskRunner`](/api-ref/prefect/task-runners/#prefect.task_runners.SequentialTaskRunner) can run tasks sequentially. 
- [`ConcurrentTaskRunner`](/api-ref/prefect/task-runners/#prefect.task_runners.ConcurrentTaskRunner) can run tasks concurrently, allowing tasks to switch when blocking on IO. Tasks will be submitted to a thread pool maintained by `anyio`.

In addition, the following Prefect-developed task runners for parallel or distributed task execution may be installed as [Prefect Collections](/collections/catalog/). 

- [`DaskTaskRunner`](https://prefecthq.github.io/prefect-dask/) can run tasks requiring parallel execution using [`dask.distributed`](http://distributed.dask.org/). 
- [`RayTaskRunner`](https://prefecthq.github.io/prefect-ray/) can run tasks requiring parallel execution using [Ray](https://www.ray.io/).

!!! note "Concurrency versus parallelism"
    The words "concurrency" and "parallelism" may sound the same, but they mean different things in computing.

    **Concurrency** refers to a system that can do more than one thing simultaneously, but not at the _exact_ same time. It may be more accurate to think of concurrent execution as non-blocking: within the restrictions of resources available in the execution environment and data dependencies between tasks, execution of one task does not block execution of other tasks in a flow.

    **Parallelism** refers to a system that can do more than one thing at the _exact_ same time. Again, within the restrictions of resources available, parallel execution can run tasks at the same time, such as for operations mapped across a dataset.

## Using a task runner

You do not need to specify a task runner for a flow unless your tasks require a specific type of execution. 

To configure your flow to use a specific task runner, import a task runner and assign it as an argument for the flow when the flow is defined.

!!! note "Remember to call `.submit()` when using a task runner"
    Make sure you use `.submit()` to run your task with a task runner. Calling the task directly, without `.submit()`, from within a flow will run the task sequentially instead of using a specified task runner.

For example, you can use `ConcurrentTaskRunner` to allow tasks to switch when they would block.

```python hl_lines="2 11"
from prefect import flow, task
from prefect.task_runners import ConcurrentTaskRunner
import time

@task
def stop_at_floor(floor):
    print(f"elevator moving to floor {floor}")
    time.sleep(floor)
    print(f"elevator stops on floor {floor}")

@flow(task_runner=ConcurrentTaskRunner())
def elevator():
    for floor in range(10, 0, -1):
        stop_at_floor.submit(floor)
```

If you specify an uninitialized task runner class, a task runner instance of that type is created with the default settings. You can also pass additional configuration parameters for task runners that accept parameters, such as [`DaskTaskRunner`](https://prefecthq.github.io/prefect-dask/) and [`RayTaskRunner`](https://prefecthq.github.io/prefect-ray/).

!!! tip "Default task runner"
    If you don't specify a task runner for a flow and you call a task with `.submit()` within the flow, Prefect uses the default `ConcurrentTaskRunner`.

## Running tasks sequentially

Sometimes, it's useful to force tasks to run sequentially to make it easier to reason about the behavior of your program. Switching to the `SequentialTaskRunner` will force submitted tasks to run sequentially rather than concurrently.

!!! note "Synchronous and asynchronous tasks"
    The `SequentialTaskRunner` works with both synchronous and asynchronous task functions. Asynchronous tasks are Python functions defined using `async def` rather than `def`.

The following example demonstrates using the `SequentialTaskRunner` to ensure that tasks run sequentially. In the example, the flow `glass_tower` runs the task `stop_at_floor` for floors one through 38, in that order.

```python
from prefect import flow, task
from prefect.task_runners import SequentialTaskRunner
import random

@task
def stop_at_floor(floor):
    situation = random.choice(["on fire","clear"])
    print(f"elevator stops on {floor} which is {situation}")

@flow(task_runner=SequentialTaskRunner(),
      name="towering-infernflow",
      )
def glass_tower():
    for floor in range(1, 39):
        stop_at_floor.submit(floor)
    
glass_tower()
```

## Using multiple task runners

Each flow can only have a single task runner, but sometimes you may want a subset of your tasks to run using a specific task runner. In this case, you can create [subflows](/concepts/flows/#composing-flows) for tasks that need to use a different task runner.

For example, you can have a flow (in the example below called `sequential_flow`) that runs its tasks locally using the `SequentialTaskRunner`. If you have some tasks that can run more efficiently in parallel on a Dask cluster, you could create a subflow (such as `dask_subflow`) to run those tasks using the `DaskTaskRunner`.

```python
from prefect import flow, task
from prefect.task_runners import SequentialTaskRunner
from prefect_dask.task_runners import DaskTaskRunner

@task
def hello_local():
    print("Hello!")

@task
def hello_dask():
    print("Hello from Dask!")

@flow(task_runner=SequentialTaskRunner())
def sequential_flow():
    hello_local.submit()
    dask_subflow()
    hello_local.submit()

@flow(task_runner=DaskTaskRunner())
def dask_subflow():
    hello_dask.submit()

if __name__ == "__main__":
    sequential_flow()
```

!!! tip "Guarding main"
    Note that you should guard the `main` function by using `if __name__ == "__main__"` to avoid issues with parallel processing. 

This script outputs the following logs demonstrating the use of the Dask task runner:

<div class="terminal">
```bash 
120:14:29.785 | INFO    | prefect.engine - Created flow run 'ivory-caiman' for flow 'sequential-flow'
20:14:29.785 | INFO    | Flow run 'ivory-caiman' - Starting 'SequentialTaskRunner'; submitted tasks will be run sequentially...
20:14:29.880 | INFO    | Flow run 'ivory-caiman' - Created task run 'hello_local-7633879f-0' for task 'hello_local'
20:14:29.881 | INFO    | Flow run 'ivory-caiman' - Executing 'hello_local-7633879f-0' immediately...
Hello!
20:14:29.904 | INFO    | Task run 'hello_local-7633879f-0' - Finished in state Completed()
20:14:29.952 | INFO    | Flow run 'ivory-caiman' - Created subflow run 'nimble-sparrow' for flow 'dask-subflow'
20:14:29.953 | INFO    | prefect.task_runner.dask - Creating a new Dask cluster with `distributed.deploy.local.LocalCluster`
20:14:31.862 | INFO    | prefect.task_runner.dask - The Dask dashboard is available at http://127.0.0.1:8787/status
20:14:31.901 | INFO    | Flow run 'nimble-sparrow' - Created task run 'hello_dask-2b96d711-0' for task 'hello_dask'
20:14:32.370 | INFO    | Flow run 'nimble-sparrow' - Submitted task run 'hello_dask-2b96d711-0' for execution.
Hello from Dask!
20:14:33.358 | INFO    | Flow run 'nimble-sparrow' - Finished in state Completed('All states completed.')
20:14:33.368 | INFO    | Flow run 'ivory-caiman' - Created task run 'hello_local-7633879f-1' for task 'hello_local'
20:14:33.368 | INFO    | Flow run 'ivory-caiman' - Executing 'hello_local-7633879f-1' immediately...
Hello!
20:14:33.386 | INFO    | Task run 'hello_local-7633879f-1' - Finished in state Completed()
20:14:33.399 | INFO    | Flow run 'ivory-caiman' - Finished in state Completed('All states completed.')
```
</div>


## Using results from submitted tasks

When you use `.submit()` to submit a task to a task runner, the task runner creates a [`PrefectFuture`](/api-ref/prefect/futures/#prefect.futures.PrefectFuture) for access to the state and result of the task.

A `PrefectFuture` is an object that provides access to a computation happening in a task runner &mdash; even if that computation is happening on a remote system.

In the following example, we save the return value of calling `.submit()` on the task `say_hello` to the variable `future`, and then we print the type of the variable:

```python
from prefect import flow, task

@task
def say_hello(name):
    return f"Hello {name}!"

@flow
def hello_world():
    future = say_hello.submit("Marvin")
    print(f"variable 'future' is type {type(future)}")

hello_world()
```

When you run this code, you'll see that the variable `future` is a `PrefectFuture`:

<div class="terminal">
```bash
variable 'future' is type <class 'prefect.futures.PrefectFuture'>
```
</div>

When you pass a future into a task, Prefect waits for the "upstream" task &mdash; the one that the future references &mdash; to reach a final state before starting the downstream task.

This means that the downstream task won't receive the `PrefectFuture` you passed as an argument. Instead, the downstream task will receive the value that the upstream task returned.

Take a look at how this works in the following example

```python
from prefect import flow, task

@task
def say_hello(name):
    return f"Hello {name}!"

@task
def print_result(result):
    print(type(result))
    print(result)

@flow(name="hello-flow")
def hello_world():
    future = say_hello.submit("Marvin")
    print_result.submit(future)

hello_world()
```

<div class="terminal">
```bash
<class 'str'>
Hello Marvin!
```
</div>

Futures have a few useful methods. For example, you can get the return value of the task run with  [`.result()`](/api-ref/prefect/futures/#prefect.futures.PrefectFuture.result):

```python
from prefect import flow, task

@task
def my_task():
    return 42

@flow
def my_flow():
    future = my_task.submit()
    result = future.result()
    print(result)

my_flow()
```

The `.result()` method will wait for the task to complete before returning the result to the caller. If the task run fails, `.result()` will raise the task run's exception. You may disable this behavior with the `raise_on_failure` option:

```python
from prefect import flow, task

@task
def my_task():
    return "I'm a task!"


@flow
def my_flow():
    future = my_task.submit()
    result = future.result(raise_on_failure=False)
    if future.get_state().is_failed():
        # `result` is an exception! handle accordingly
        ...
    else:
        # `result` is the expected return value of our task
        ...
```

You can retrieve the current state of the task run associated with the `PrefectFuture` using [`.get_state()`](/api-ref/prefect/futures/#prefect.futures.PrefectFuture.get_state):

```python
@flow
def my_flow():
    future = my_task.submit()
    state = future.get_state()
```

You can also wait for a task to complete by using the [`.wait()`](/api-ref/prefect/futures/#prefect.futures.PrefectFuture.wait) method:

```python
@flow
def my_flow():
    future = my_task.submit()
    final_state = future.wait()
```

You can include a timeout in the `wait` call to perform logic if the task has not finished in a given amount of time:

```python
@flow
def my_flow():
    future = my_task.submit()
    final_state = future.wait(1)  # Wait one second max
    if final_state:
        # Take action if the task is done
        result = final_state.result()
    else:
        ... # Task action if the task is still running
```


You may also use the [`wait_for=[]`](/api-ref/prefect/tasks/#prefect.tasks.Task.__call__) parameter when calling a task, specifying upstream task dependencies. This enables you to control task execution order for tasks that do not share data dependencies.

```python
@task
def task_a():
    pass

@task
def task_b():
    pass

@task
def task_c():
    pass
    
@task
def task_d():
    pass

@flow
def my_flow():
    a = task_a.submit()
    b = task_b.submit()
    # Wait for task_a and task_b to complete
    c = task_c.submit(wait_for=[a, b])
    # task_d will wait for task_c to complete
    # Note: If waiting for one task it must still be in a list.
    d = task_d(wait_for=[c])
```

### When to use `.result()` in flows

The simplest pattern for writing a flow is either only using tasks or only using pure Python functions. When you need to mix the two, use `.result()`.

Using only tasks:

```python
from prefect import flow, task

@task
def say_hello(name):
    return f"Hello {name}!"

@task
def say_nice_to_meet_you(hello_greeting):
    return f"{hello_greeting} Nice to meet you :)"

@flow
def hello_world():
    hello = say_hello.submit("Marvin")
    nice_to_meet_you = say_nice_to_meet_you.submit(hello)

hello_world()
```

Using only Python functions:

```python
from prefect import flow, task

def say_hello(name):
    return f"Hello {name}!"

def say_nice_to_meet_you(hello_greeting):
    return f"{hello_greeting} Nice to meet you :)"

@flow
def hello_world():
    # because this is just a Python function, calls will not be tracked
    hello = say_hello("Marvin") 
    nice_to_meet_you = say_nice_to_meet_you(hello)

hello_world()
```

Mixing tasks and Python functions:

```python
from prefect import flow, task

def say_hello_extra_nicely_to_marvin(hello): # not a task or flow!
    if hello == "Hello Marvin!":
        return "HI MARVIN!"
    return hello

@task
def say_hello(name):
    return f"Hello {name}!"

@task
def say_nice_to_meet_you(hello_greeting):
    return f"{hello_greeting} Nice to meet you :)"

@flow
def hello_world():
    # run a task and get the result
    hello = say_hello.submit("Marvin").result()

    # not calling a task or flow
    special_greeting = say_hello_extra_nicely_to_marvin(hello)

    # pass our modified greeting back into a task
    nice_to_meet_you = say_nice_to_meet_you.submit(special_greeting)

    print(nice_to_meet_you.result())

hello_world()
```

Note that `.result()` also limits Prefect's ability to track task dependencies. In the "mixed" example above, Prefect will not be aware that `say_hello` is upstream of `nice_to_meet_you`.


!!! note "Calling `.result()` is blocking"
    When calling `.result()`, be mindful your flow function will have to wait until the task run is completed before continuing.

```python
@task
from prefect import flow, task

def say_hello(name):
    return f"Hello {name}!"

@task
def do_important_stuff():
    print("Doing lots of important stuff!")

@flow
def hello_world():
    # blocks until `say_hello` has finished
    result = say_hello.submit("Marvin").result() 
    do_important_stuff.submit()

hello_world()
```

## Running tasks on Dask

The [`DaskTaskRunner`](https://prefecthq.github.io/prefect-dask/) is a parallel task runner that submits tasks to the [`dask.distributed`](http://distributed.dask.org/) scheduler. By default, a temporary Dask cluster is created for the duration of the flow run. If you already have a Dask cluster running, either local or cloud hosted, you can provide the connection URL via the `address` kwarg.

1. Make sure the `prefect-dask` collection is installed: `pip install prefect-dask`.
2. In your flow code, import `DaskTaskRunner` from `prefect_dask.task_runners`.
3. Assign it as the task runner when the flow is defined using the `task_runner=DaskTaskRunner` argument.

For example, this flow uses the `DaskTaskRunner` configured to access an existing Dask cluster at `http://my-dask-cluster`.

```python hl_lines="4"
from prefect import flow
from prefect_dask.task_runners import DaskTaskRunner

@flow(task_runner=DaskTaskRunner(address="http://my-dask-cluster"))
def my_flow():
    ...
```

`DaskTaskRunner` accepts the following optional parameters:

| Parameter | Description |
| --- | --- |
| address | Address of a currently running Dask scheduler. |
| cluster_class | The cluster class to use when creating a temporary Dask cluster. It can be either the full class name (for example, `"distributed.LocalCluster"`), or the class itself. |
| cluster_kwargs | Additional kwargs to pass to the `cluster_class` when creating a temporary Dask cluster. |
| adapt_kwargs | Additional kwargs to pass to `cluster.adapt` when creating a temporary Dask cluster. Note that adaptive scaling is only enabled if `adapt_kwargs` are provided. |
| client_kwargs | Additional kwargs to use when creating a [`dask.distributed.Client`](https://distributed.dask.org/en/latest/api.html#client). |

!!! warning "Multiprocessing safety"
    Note that, because the `DaskTaskRunner` uses multiprocessing, calls to flows
    in scripts must be guarded with `if __name__ == "__main__":` or you will encounter 
    warnings and errors.

If you don't provide the `address` of a Dask scheduler, Prefect creates a temporary local cluster automatically. The number of workers used is based on the number of cores on your machine. The default provides a mix of processes and threads that should work well for
most workloads. If you want to specify this explicitly, you can pass values for `n_workers` or `threads_per_worker` to `cluster_kwargs`.

```python
# Use 4 worker processes, each with 2 threads
DaskTaskRunner(
    cluster_kwargs={"n_workers": 4, "threads_per_worker": 2}
)
```

### Using a temporary cluster

The `DaskTaskRunner` is capable of creating a temporary cluster using any of [Dask's cluster-manager options](https://docs.dask.org/en/latest/setup.html). This can be useful when you want each flow run to have its own Dask cluster, allowing for per-flow adaptive scaling.

To configure, you need to provide a `cluster_class`. This can be:

- A string specifying the import path to the cluster class (for example, `"dask_cloudprovider.aws.FargateCluster"`)
- The cluster class itself
- A function for creating a custom cluster. 

You can also configure `cluster_kwargs`, which takes a dictionary of keyword arguments to pass to `cluster_class` when starting the flow run.

For example, to configure a flow to use a temporary `dask_cloudprovider.aws.FargateCluster` with 4 workers running with an image named `my-prefect-image`:

```python
DaskTaskRunner(
    cluster_class="dask_cloudprovider.aws.FargateCluster",
    cluster_kwargs={"n_workers": 4, "image": "my-prefect-image"},
)
```

### Connecting to an existing cluster

Multiple Prefect flow runs can all use the same existing Dask cluster. You
might manage a single long-running Dask cluster (maybe using the Dask 
[Helm Chart](https://docs.dask.org/en/latest/setup/kubernetes-helm.html)) and
configure flows to connect to it during execution. This has a few downsides
when compared to using a temporary cluster (as described above):

- All workers in the cluster must have dependencies installed for all flows you
  intend to run.
- Multiple flow runs may compete for resources. Dask tries to do a good job
  sharing resources between tasks, but you may still run into issues.

That said, you may prefer managing a single long-running cluster. 

To configure a `DaskTaskRunner` to connect to an existing cluster, pass in the address of the
scheduler to the `address` argument:

```python
# Connect to an existing cluster running at a specified address
DaskTaskRunner(address="tcp://...")
```

### Adaptive scaling

One nice feature of using a `DaskTaskRunner` is the ability to scale adaptively
to the workload. Instead of specifying `n_workers` as a fixed number, this lets
you specify a minimum and maximum number of workers to use, and the dask
cluster will scale up and down as needed.

To do this, you can pass `adapt_kwargs` to `DaskTaskRunner`. This takes the
following fields:

- `maximum` (`int` or `None`, optional): the maximum number of workers to scale
  to. Set to `None` for no maximum.
- `minimum` (`int` or `None`, optional): the minimum number of workers to scale
  to. Set to `None` for no minimum.

For example, here we configure a flow to run on a `FargateCluster` scaling up
to at most 10 workers.

```python
DaskTaskRunner(
    cluster_class="dask_cloudprovider.aws.FargateCluster",
    adapt_kwargs={"maximum": 10}
)
```

### Dask annotations

Dask annotations can be used to further control the behavior of tasks.

For example, we can set the [priority](http://distributed.dask.org/en/stable/priority.html) of tasks in the Dask scheduler:

```python
import dask
from prefect import flow, task
from prefect_dask.task_runners import DaskTaskRunner

@task
def show(x):
    print(x)


@flow(task_runner=DaskTaskRunner())
def my_flow():
    with dask.annotate(priority=-10):
        future = show.submit(1)  # low priority task

    with dask.annotate(priority=10):
        future = show.submit(2)  # high priority task
```

Another common use case is [resource](http://distributed.dask.org/en/stable/resources.html) annotations:

```python
import dask
from prefect import flow, task
from prefect_dask.task_runners import DaskTaskRunner

@task
def show(x):
    print(x)

# Create a `LocalCluster` with some resource annotations
# Annotations are abstract in dask and not inferred from your system.
# Here, we claim that our system has 1 GPU and 1 process available per worker
@flow(
    task_runner=DaskTaskRunner(
        cluster_kwargs={"n_workers": 1, "resources": {"GPU": 1, "process": 1}}
    )
)

def my_flow():
    with dask.annotate(resources={'GPU': 1}):
        future = show(0)  # this task requires 1 GPU resource on a worker

    with dask.annotate(resources={'process': 1}):
        # These tasks each require 1 process on a worker; because we've 
        # specified that our cluster has 1 process per worker and 1 worker,
        # these tasks will run sequentially
        future = show(1)
        future = show(2)
        future = show(3)


if __name__ == "main":
    my_flow()
```

## Running tasks on Ray

The [`RayTaskRunner`](https://prefecthq.github.io/prefect-ray/) &mdash; installed separately as a [Prefect Collection](/collections/catalog/) &mdash; is a parallel task runner that submits tasks to [Ray](https://www.ray.io/). By default, a temporary Ray instance is created for the duration of the flow run. If you already have a Ray instance running, you can provide the connection URL via an `address` argument.

!!! note "Remote storage and Ray tasks"
    We recommend configuring [remote storage](/concepts/storage/) for task execution with the `RayTaskRunner`. This ensures tasks executing in Ray have access to task result storage, particularly when accessing a Ray instance outside of your execution environment.

To configure your flow to use the `RayTaskRunner`:

1. Make sure the `prefect-ray` collection is installed: `pip install prefect-ray`.
2. In your flow code, import `RayTaskRunner` from `prefect_ray.task_runners`.
3. Assign it as the task runner when the flow is defined using the `task_runner=RayTaskRunner` argument.

For example, this flow uses the `RayTaskRunner` configured to access an existing Ray instance at `ray://192.0.2.255:8786`.

```python hl_lines="4"
from prefect import flow
from prefect_ray.task_runners import RayTaskRunner

@flow(task_runner=RayTaskRunner(address="ray://192.0.2.255:8786"))
def my_flow():
    ... 
```

`RayTaskRunner` accepts the following optional parameters:

| Parameter | Description |
| --- | --- |
| address | Address of a currently running Ray instance, starting with the [ray://](https://docs.ray.io/en/master/cluster/ray-client.html) URI. |
| init_kwargs | Additional kwargs to use when calling `ray.init`. |

Note that Ray Client uses the [ray://](https://docs.ray.io/en/master/cluster/ray-client.html) URI to indicate the address of a Ray instance. If you don't provide the `address` of a Ray instance, Prefect creates a temporary instance automatically.

!!! warning "Ray environment limitations"
    While we're excited about adding support for parallel task execution via Ray to Prefect, there are some inherent limitations with Ray you should be aware of:
    
    Alpha support for Python 3.10 was added in [Ray 1.13](https://github.com/ray-project/ray/releases/tag/ray-1.13.0).

    Ray support for non-x86/64 architectures such as ARM/M1 processors with installation from `pip` alone and will be skipped during installation of Prefect. It is possible to manually install the blocking component with `conda`. See the [Ray documentation](https://docs.ray.io/en/latest/ray-overview/installation.html#m1-mac-apple-silicon-support) for instructions.

    See the [Ray installation documentation](https://docs.ray.io/en/latest/ray-overview/installation.html) for further compatibility information.



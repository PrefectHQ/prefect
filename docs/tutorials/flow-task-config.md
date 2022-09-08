---
description: Explore the configuration available for Prefect flows and tasks.
tags:
    - tutorial
    - configuration
    - tasks
    - flows
    - parameters
    - caching
---

# Flow and task configuration

Now that you've written some [basic flows and tasks](/tutorials/first-steps/), let's explore some of the configuration options that Prefect exposes.

Simply decorating functions as flows and tasks lets you take advantage of the orchestration and visibility features enabled by the Prefect Orion orchestration engine. You can also configure additional options on your flows and tasks, enabling Prefect to execute and track your workflows more effectively.

## Basic flow configuration

Basic flow configuration includes the ability to provide a name, description, and version and other options for the flow via [flow arguments](/concepts/flows/#flow-arguments).

You specify flow configuration as arguments on the `@flow` decorator.

A flow `name` is a distinguished piece of metadata within Prefect. The name that you give to a flow becomes the unifying identifier for all future runs of that flow, regardless of version or task structure.

```python
from prefect import flow

@flow(name="My Example Flow")
def my_flow():
    # run tasks and subflows
```

A flow `description` enables you to provide documentation right alongside your flow object. You can also provide a specific `description` string as a flow option.

```python
from prefect import flow

@flow(name="My Example Flow", 
      description="An example flow for a tutorial.")
def my_flow():
    # run tasks and subflows
```

Prefect can also use the flow function's docstring as a description.

```python
from prefect import flow

@flow(name="My Example Flow")
def my_flow():
    """An example flow for a tutorial."""
    # run tasks and subflows
```

A flow `version` enables you to associate a given run of your workflow with the version of code or configuration that was used. 

```python
from prefect import flow

@flow(name="My Example Flow", 
      description="An example flow for a tutorial.",
      version="tutorial_02")
def my_flow():
    # run tasks and subflows
```

If you are using `git` to version control your code, you might use the commit hash as the version. 

```python
import os
from prefect import flow

@flow(name="My Example Flow", 
      description="An example flow for a tutorial.",
      version=os.getenv("GIT_COMMIT_SHA"))
def my_flow():
    # run tasks and subflows
```

You don't have to supply a version for your flow. By default, Prefect makes a best effort to compute a stable hash of the `.py` file in which the flow is defined to automatically detect when your code changes.  However, this computation is not always possible and so, depending on your setup, you may see that your flow has a version of `None`.

## Basic task configuration

By design, tasks follow a very similar model to flows: you can independently assign tasks their own name and description.

```python
from prefect import flow, task

@task(name="My Example Task", 
      description="An example task for a tutorial.")
def my_task():
    # do some work

@flow
def my_flow():
    my_task()
```

Tasks also accept [tags](/concepts/tasks/#tags) as an option. Tags are runtime metadata used by the Prefect Orion orchestration engine that enable features like filtering display of task runs and configuring task concurrency limits.

You specify the tags on a task as a list of tag strings.

```python hl_lines="5"
from prefect import flow, task

@task(name="My Example Task", 
      description="An example task for a tutorial.",
      tags=["tutorial","tag-test"])
def my_task():
    # do some work

@flow
def my_flow():
    my_task()
```

## Flow and task retries

Prefect includes built-in support for both flow and [task retries](/concepts/tasks/#retries), which you configure on the flow or task. This enables flows and tasks to automatically retry on failure. You can specify how many retries you want to attempt and, optionally, a delay between retry attempts:

```python hl_lines="4"
from prefect import flow, task

# this tasks runs 3 times before the flow fails
@task(retries=2, retry_delay_seconds=60)
def failure():
    print('running')
    raise ValueError("bad code")

@flow
def test_retries():
    return failure()
```

If you run `test_retries()`, the `failure()` task always raises an error, but will run a total of three times.

<div class="terminal">
```bash
>>> state = test_retries()
13:48:40.570 | Beginning flow run 'red-orca' for flow 'test-retries'...
13:48:40.570 | Starting task runner `SequentialTaskRunner`...
13:48:40.630 | Submitting task run 'failure-acc38180-0' to task runner...
running
13:48:40.663 | Task run 'failure-acc38180-0' encountered exception:
Traceback (most recent call last):...
13:48:40.708 | Task run 'failure-acc38180-0' received non-final state 
'AwaitingRetry' when proposing final state 'Failed' and will attempt to run again...
running
13:48:40.748 | Task run 'failure-acc38180-0' encountered exception:
Traceback (most recent call last):...
13:48:40.786 | Task run 'failure-acc38180-0' received non-final state 
'AwaitingRetry' when proposing final state 'Failed' and will attempt to run again...
running
13:48:40.829 | Task run 'failure-acc38180-0' encountered exception:
Traceback (most recent call last):...
13:48:40.871 | Task run 'failure-acc38180-0' finished in state 
Failed(message='Task run encountered an exception.', type=FAILED)
13:48:40.872 | Shutting down task runner `SequentialTaskRunner`...
13:48:40.899 | Flow run 'red-orca' finished in state 
Failed(message='1/1 states failed.', type=FAILED)
```
</div>

Once we dive deeper into state transitions and orchestration policies, you will see that this task run actually went through the following state transitions some number of times: 

`Pending` -> `Running` -> `AwaitingRetry` -> `Retrying` 

Metadata such as this allows for a full reconstruction of what happened with your flows and tasks on each run.

!!! note "Flow retries"
    [Flow retries](/concepts/flows/#flow-retries) use the same argument syntax as task retry configuration. Note that retries for failed flows will retry the flow, tasks within the flow, and any child flows, and those are potentially subject to any configured retries.

## Task caching

[Caching](/concepts/tasks/#caching) refers to the ability of a task run to reflect a finished state without actually running the code that defines the task. This allows you to efficiently reuse results of tasks that may be particularly "expensive" to run with every flow run.  Moreover, Prefect makes it easy to share these states across flows and flow runs using the concept of a "cache key function".

You can specify the cache key function using the `cache_key_fn` argument on a task. 

!!! note "Task results, retries, and caching"
    Task results are cached in memory during a flow run and peristed to the location specified by the `PREFECT_LOCAL_STORAGE_PATH` setting. As a result, task caching between flow runs is currently limited to flow runs with access to that local storage path.

### Task input hash

One way to use `cache_key_fn` is to cache based on inputs by specifying `task_input_hash`. If the input parameters to the task are the same, Prefect returns the cached results rather than running the task again. 

To illustrate, run the following flow in a Python interpreter.

```python hl_lines="5"
from prefect import flow, task
from prefect.tasks import task_input_hash
from datetime import timedelta

@task(cache_key_fn=task_input_hash, cache_expiration=timedelta(minutes=1))
def hello_task(name_input):
    # Doing some work
    print(f"Saying hello {name_input}")
    return "hello " + name_input

@flow
def hello_flow(name_input):
    hello_task(name_input)
```

Run the flow a few times in a row passing the same name (in this case we used "Marvin") and notice that the task only prints out its message the first time.

But if you change the argument passed to the task (here we used "Trillian" instead of "Marvin"), the task runs again, as demonstrated by printing the message "Saying hello Trillian".

<div class="terminal">
```bash
>>> hello_flow("Marvin")
11:52:09.553 | INFO    | prefect.engine - Created flow run 'attentive-turaco' for flow 'hello-flow'
11:52:09.553 | INFO    | Flow run 'attentive-turaco' - Using task runner 'ConcurrentTaskRunner'
11:52:09.761 | INFO    | Flow run 'attentive-turaco' - Created task run 'hello_task-e97fb216-0' for task 'hello_task'
Saying hello Marvin
11:52:10.798 | INFO    | Task run 'hello_task-e97fb216-0' - Finished in state Completed(None)
11:52:12.004 | INFO    | Flow run 'attentive-turaco' - Finished in state Completed('All states completed.')
Completed(message='All states completed.', type=COMPLETED, result=[Completed(message=None, type=COMPLETED, result='hello Marvin', task_run_id=90dcb0d6-ae5b-4ad2-bb74-92e58626850b)], flow_run_id=8af63f45-b50c-46ef-b59e-ec19897421cd)
>>> hello_flow("Marvin")
11:52:17.512 | INFO    | prefect.engine - Created flow run 'taupe-grasshopper' for flow 'hello-flow'
11:52:17.512 | INFO    | Flow run 'taupe-grasshopper' - Using task runner 'ConcurrentTaskRunner'
11:52:17.718 | INFO    | Flow run 'taupe-grasshopper' - Created task run 'hello_task-e97fb216-1' for task 'hello_task'
11:52:18.316 | INFO    | Task run 'hello_task-e97fb216-1' - Finished in state Cached(None, type=COMPLETED)
11:52:19.429 | INFO    | Flow run 'taupe-grasshopper' - Finished in state Completed('All states completed.')
Completed(message='All states completed.', type=COMPLETED, result=[Cached(message=None, type=COMPLETED, result='hello Marvin', task_run_id=79bb8dd6-f640-4bc2-b1fd-ec6ee84a8974)], flow_run_id=757bd56e-6ee3-44dc-a9fe-ada4b4cefe13)
>>> hello_flow("Trillian")
11:53:06.637 | INFO    | prefect.engine - Created flow run 'imposing-stork' for flow 'hello-flow'
11:53:06.637 | INFO    | Flow run 'imposing-stork' - Using task runner 'ConcurrentTaskRunner'
11:53:06.846 | INFO    | Flow run 'imposing-stork' - Created task run 'hello_task-e97fb216-3' for task 'hello_task'
Saying hello Trillian
11:53:07.787 | INFO    | Task run 'hello_task-e97fb216-3' - Finished in state Completed(None)
11:53:09.027 | INFO    | Flow run 'imposing-stork' - Finished in state Completed('All states completed.')
Completed(message='All states completed.', type=COMPLETED, result=[Completed(message=None, type=COMPLETED, result='hello Trillian', task_run_id=20d269b5-fccd-4804-9806-5e13ebd0685b)], flow_run_id=22b9b3a5-08df-40f0-8334-475c6446c4ff)
```
</div>

Why does this happen? Whenever each task run requested to enter a `Running` state, it provided its cache key computed from the `cache_key_fn`. The Prefect Orion orchestration engine identified that there was a `COMPLETED` state associated with this key and instructed the run to immediately enter the same state, including the same return values. See the Tasks [Caching](/concepts/tasks/#caching) documentation for more details.

!!! tip "Cache expiration"
    Note that in this example we're also specifying a cache expiration duration: `cache_expiration=timedelta(minutes=1)`. This causes the cache to expire after one minute regardless of the task input. You can demonstrate this by: 

    - Running `hello_flow("Marvin")` a few times, noting that the task only prints its message the first time. 
    - Waiting 60 seconds.
    - Running `hello_flow("Marvin")` again, noting that the task prints its message this time, even though the input didn't change.

    It's a good practice to set a cache expiration.

### Cache key function

You can also define your own cache key function that returns a string cache key. As long as the cache key remains the same, the Prefect backend identifies that there is a `COMPLETED` state associated with this key and instructs the new run to immediately enter the same `COMPLETED` state, including the same return values.

In this example, you could provide different input, but the cache key remains the same if the sum of the inputs remains the same.

```python hl_lines="5-9"
from prefect import flow, task
from datetime import timedelta
import time

def cache_key_from_sum(context, parameters):
    print(parameters)
    return sum(parameters["nums"])

@task(cache_key_fn=cache_key_from_sum, cache_expiration=timedelta(minutes=1))
def cached_task(nums):
    print('running an expensive operation')  
    time.sleep(3)
    return sum(nums)

@flow
def test_caching(nums):
    cached_task(nums)
```

Notice that if we call `test_caching()` with the value `[2,2]`, the long running operation runs only once. The task still doesn't run if we call it with the value `[1,3]` &mdash; both 2+2 and 1+3 return the same cache key string, "4".

But if you then call `test_caching([2,3])`, which results in the cache key string "5", `cached_task()` runs.

<div class='terminal'>
```bash
>>> test_caching([2,2])
13:52:52.072 | INFO    | prefect.engine - Created flow run 'saffron-lemur' for flow 'test-caching'
13:52:52.072 | INFO    | Flow run 'saffron-lemur' - Using task runner 'ConcurrentTaskRunner'
13:52:52.293 | INFO    | Flow run 'saffron-lemur' - Created task run 'cached_task-64beb460-0' for task 'cached_task'
{'nums': [2, 2]}
running an expensive operation
13:52:55.724 | INFO    | Task run 'cached_task-64beb460-0' - Finished in state Completed(None)
13:52:56.135 | INFO    | Flow run 'saffron-lemur' - Finished in state Completed('All states completed.')
Completed(message='All states completed.', type=COMPLETED, result=[Completed(message=None, type=COMPLETED, result=4, task_run_id=6233c853-f711-4843-a256-4cfdf2b25d15)], flow_run_id=c0cd85aa-4893-4c81-9efd-7c6531466ea1)
>>> test_caching([2,2])
13:53:12.169 | INFO    | prefect.engine - Created flow run 'pristine-chicken' for flow 'test-caching'
13:53:12.169 | INFO    | Flow run 'pristine-chicken' - Using task runner 'ConcurrentTaskRunner'
13:53:12.370 | INFO    | Flow run 'pristine-chicken' - Created task run 'cached_task-64beb460-1' for task 'cached_task'
{'nums': [2, 2]}
13:53:12.556 | INFO    | Task run 'cached_task-64beb460-1' - Finished in state Cached(None, type=COMPLETED)
13:53:12.959 | INFO    | Flow run 'pristine-chicken' - Finished in state Completed('All states completed.')
Completed(message='All states completed.', type=COMPLETED, result=[Cached(message=None, type=COMPLETED, result=4, task_run_id=f4925f7f-f8de-4434-9943-1d08c23f2994)], flow_run_id=46d0d0ac-defb-4dbd-a086-2b89f24250f5)
>>> test_caching([1,3])
13:53:20.765 | INFO    | prefect.engine - Created flow run 'holistic-loon' for flow 'test-caching'
13:53:20.766 | INFO    | Flow run 'holistic-loon' - Using task runner 'ConcurrentTaskRunner'
13:53:20.972 | INFO    | Flow run 'holistic-loon' - Created task run 'cached_task-64beb460-2' for task 'cached_task'
{'nums': [1, 3]}
13:53:21.160 | INFO    | Task run 'cached_task-64beb460-2' - Finished in state Cached(None, type=COMPLETED)
13:53:21.520 | INFO    | Flow run 'holistic-loon' - Finished in state Completed('All states completed.')
Completed(message='All states completed.', type=COMPLETED, result=[Cached(message=None, type=COMPLETED, result=4, task_run_id=ac43e614-4ffe-4798-af5b-40ab7b419914)], flow_run_id=bbb7117c-e362-474e-aa16-8aa88290ab11)
>>> test_caching([2,3])
13:53:26.145 | INFO    | prefect.engine - Created flow run 'chestnut-jackal' for flow 'test-caching'
13:53:26.146 | INFO    | Flow run 'chestnut-jackal' - Using task runner 'ConcurrentTaskRunner'
13:53:26.343 | INFO    | Flow run 'chestnut-jackal' - Created task run 'cached_task-64beb460-3' for task 'cached_task'
{'nums': [2, 3]}
running an expensive operation
13:53:29.715 | INFO    | Task run 'cached_task-64beb460-3' - Finished in state Completed(None)
13:53:30.070 | INFO    | Flow run 'chestnut-jackal' - Finished in state Completed('All states completed.')
Completed(message='All states completed.', type=COMPLETED, result=[Completed(message=None, type=COMPLETED, result=5, task_run_id=95673be8-4d7c-49e2-90f2-880369efadd9)], flow_run_id=c136a29a-6fed-49d9-841a-0b54249a0f0e)
```
</div>

For further details on cache key functions, see the [Caching](/concepts/tasks/#caching) topic in the Tasks documentation.

!!! warning "The persistence of state"
    Note that, up until now, we have run all of our workflows interactively. This means our metadata store is a SQLite database located at the default database location. This can be configured in various ways, but please note that any cache keys you experiment with will be persisted in this SQLite database until they expire or you clear the database manually!

    That is why the examples here include `cache_expiration=timedelta(minutes=1)` so that tutorial cache keys do not remain in your database permanently.

## Configuring task runners

A more advanced configuration option for flows is to specify a [task runner](/concepts/task-runners/), which enables you to specify the execution environment used for task runs within a flow. 

You must use `.submit()` to submit your task to a task runner. Calling the task directly from within a flow does not invoke the task runner for execution and will execute tasks sequentially. Tasks called directly without submitting to a task runner return the result data you'd expect from a Python function.

Prefect provides two built-in task runners: 

- [`SequentialTaskRunner`](/api-ref/prefect/task-runners/#prefect.task_runners.SequentialTaskRunner) can run tasks sequentially. 
- [`ConcurrentTaskRunner`](/api-ref/prefect/task-runners/#prefect.task_runners.ConcurrentTaskRunner) can run tasks concurrently, allowing tasks to switch when blocking on IO. Tasks will be submitted to a thread pool maintained by `anyio`.

We'll cover the use cases for more advanced task runners for parallel and distributed execution in the [Dask and Ray task runners](/tutorials/dask-ray-task-runners/) tutorial. 

!!! tip "Task runners are optional"
    If you just need the result from a task, you can simply call the task from your flow. For most workflows, the default behavior of calling a task directly and receiving a result is all you'll need.

For now, we'll just demonstrate that you can specify the task runner _almost_ like any other option. The difference is that you need to: 

- Import the task runner
- Specify you're using the task runner for tasks within your flow with the `task_runner` setting on the flow. 
- Call [`.submit()`](/concepts/task-runners/#using-a-task-runner) on your task to submit task execution to the task runner.

```python
from prefect import flow, task
from prefect.task_runners import SequentialTaskRunner

@task
def first_task(num):
    return num + num

@task
def second_task(num):
    return num * num

@flow(name="My Example Flow", 
      task_runner=SequentialTaskRunner(),
)
def my_flow(num):
    plusnum = first_task.submit(num)
    sqnum = second_task.submit(plusnum)
    print(f"add: {plusnum.result()}, square: {sqnum.result()}")

my_flow(5)
```

See [Task Runners](/concepts/task-runners/) for more details about submitting tasks to a task runner and returning results from a `PrefectFuture`.

!!! tip "Next steps: Flow execution"
    The next step is learning about [flow execution](/tutorials/execution/), the ability to configure many aspects of how your flows and tasks run.

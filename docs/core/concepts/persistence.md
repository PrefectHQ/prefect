# Caching and Persisting Data

Prefect provides a few ways to work with cached data between tasks or flows. In-memory caching of task **inputs** is automatically applied by the Prefect pipeline to optimize retries or other times when Prefect can anticipate rerunning the same task in the future. Users can also configure to cache the **output** of a prior run of a task and use it as the output of a future run of that task or even as the output of a run of a different task.

Out of the box, Prefect Core does not persist cached data in a permanent fashion. All data, results, _and_ cached states are only stored in memory within the
Python process running the flow. However, Prefect Core provides all of the necessary hooks for configuring your data to be persisted and retrieved from external locations. When combined with a compatible state persistence layer, such as Prefect Core's server or [Prefect Cloud](/orchestration/getting-started/set-up.html), this means flows can pick up exactly where they left off if the in-memory cache is lost.

[[toc]]

## Input Caching

When running a Prefect flow, it's common to have tasks that will need to be re-run in the future. For example, this could happen when a task fails and needs to be retried, or when a task has a `manual_only` trigger.

Whenever Prefect detects that a task will need to be run in the future, it automatically caches any information that the task needs to run and stores it on the resulting `State`. The next time Prefect encounters the task, the critical information is deserialized and used to run the task.

!!! tip Automatic caching
    Input caching is an automatic caching. Prefect will automatically apply it whenever necessary.
:::

## Output Caching

Sometimes, it's desirable to cache the output of a task to avoid recomputing it in the future. Common examples of this pattern include expensive or time-consuming computations that are unlikely to change. In this case, users can indicate that a task should be cached for a certain duration or as long as certain conditions are met.

Prefect even supports caching output by a shared key, which can be accessed between flow runs. This mechanism is sometimes called "Time Travel" because it makes results computed in one flow run available to other runs.

Output caching is controlled with three `Task` arguments: `cache_for`, `cache_validator` and `cache_key`.

- `cache_for`: a `timedelta` indicating how long the output should be cached
- `cache_validator`: a `callable` indicating how the cache should be expired. The default is `duration_only`, meaning the cache will be active for the duration of `cache_for`. Other validators can be found in `prefect.engine.cache_validators` and include mechanisms for invalidating the cache if the task receives different inputs or if the flow is run with different parameters.
- `cache_key`: an optional key under which to store the output cache; specifying this key allows different Tasks as well as different Flows to share a common cache.

```python
# this task will be cached for 1 hour
task_1 = prefect.Task(
    cache_for=datetime.timedelta(hours=1))

# this task will be cached for 1 hour, but only if the flow is run with the same parameters
task_2 = prefect.Task(
    cache_for=datetime.timedelta(hours=1),
    cache_validator=prefect.engine.cache_validators.all_parameters)
```

!!! warning The cache is stored in context
    Note that when running Prefect Core locally, your Tasks' cached states will be stored in memory within `prefect.context`.
:::

## Persisting Output

Oftentimes it is useful to persist your task's data in an external location. You could always write this logic directly into the `Task` itself, but this can sometimes make testing difficult. Prefect offers a notion of task "checkpointing" that ensures that every time a task is successfully run, its return value is written to persistent storage based on the configuration in a [Result](results.md) object for the task. To configure your tasks for checkpointing, provide a `Result` matching the storage backend you want to the task's `result` kwarg and set `checkpoint=True` at task initialization:

```python
from prefect.engine.results import LocalResult
from prefect import task, Task


class MyTask(Task):
    def run(self):
        return 42


# create a task via initializing our custom Task class
class_task = MyTask(
    checkpoint=True, result=LocalResult(dir="~/.prefect")
)


# create a task via the task decorator
@task(checkpoint=True, result=LocalResult(dir="~/.prefect"))
def func_task():
    return 99
```

There are many different `Result` classes aligning with different storage backends depending on your needs, such as `GCSResult` and `S3Result`. See the whole list in the [API docs for results](../../api/latest/engine/results.md).

!!! tip Check your global configuration, too
    The default setting in Prefect Core is that checkpointing is globally turned _off_, and the default setting in Prefect Cloud 0.9.1+ is that checkpointing is globally turned _on_. For more information, read the concepts documentation on [Results](results.md) and the setup tutorial on [Using Results](../advanced_tutorials/using-results.html).
:::

## Output Caching based on a file target

You can combine the concepts of persistent output and skipping task execution by configuring a task to skip execution based on the presence of a persisted `Result`. Many workflow authors may recognize this from tools like Make or Luigi, where tasks define "targets" (usually files on disk) and task computation is avoided in favor of using the data from the target if the target exists.

To enable this behavior for a task, provide the target location to the task's `target` kwarg along with the `result` and `checkpoint` kwargs necessary to enable checkpointing. Whenever this task is run, it will first check to see if the storage backend configured by the result has a file matching the name of the target, and if so, will enter a `Cached` state with the data from the target file as the task's return value. If it has not been cached, the output of the task will be written to the `target` location and be available as a cache for future runs of this task, even between running Python processes.

```python
from prefect.engine.results import LocalResult
from prefect import task, Task


# create a task via the task decorator
@task(target="func_task_target.txt", checkpoint=True, result=LocalResult(dir="~/.prefect"))
def func_task():
    return 99
```

!!! tip Targets can be templated
    Note that `target`s can optionally be templated, using [values found in `prefect.context`](/api/latest/utilities/context.html).  For example, the following target specification will store data based on the day of the week the flow is run on:

    ```python
    from prefect.engine.results import LocalResult
    from prefect import task, Task


    # create a task via the task decorator
    @task(target="{date:%A}/{task_name}.txt", checkpoint=True, result=LocalResult(dir="~/.prefect"))
    def func_task():
        return 99
    ```

    See the [official Python documentation](https://www.python.org/dev/peps/pep-3101/#format-strings) for more information on the flexibility of string formatting.
:::


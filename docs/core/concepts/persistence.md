# Persistence and Caching

Out of the box, Prefect Core does not persist data in a permanent fashion. All data, results, _and_ cached states are stored in memory within the
Python process running the flow. However, Prefect Core provides all of the necessary hooks for persisting / retrieving your data in external locations. If you require an out-of-the-box persistence layer, you might consider [Prefect Cloud](../../cloud/faq.html#what-is-the-difference-between-prefect-core-and-prefect-cloud).

Prefect provides a few ways to work with cached data. Wherever possible, caching is handled automatically or with minimal user input.

[[toc]]

## Input Caching

When running a Prefect flow, it's common to have tasks that will need to be re-run in the future. For example, this could happen when a task fails and needs to be retried, or when a task has a `manual_only` trigger.

Whenever Prefect detects that a task will need to be run in the future, it automatically caches any information that the task needs to run and stores it on the resulting `State`. The next time Prefect encounters the task, the critical information is deserialized and used to run the task.

::: tip Automatic caching
Input caching is an automatic caching. Prefect will automatically apply it whenever necessary.
:::

## Output Caching

Sometimes, it's desirable to cache the output of a task to avoid recomputing it in the future. Common examples of this pattern include expensive or time-consuming computations that are unlikely to change. In this case, users can indicate that a task should be cached for a certain duration or as long as certain conditions are met.

This mechanism is sometimes called "Time Travel" because it makes results computed in one flow run available to other runs.

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

::: warning The cache is stored in context
Note that when running Prefect Core locally, your Tasks' cached states will be stored in memory within `prefect.context`.
:::

## Checkpointing

Oftentimes it is useful to persist your task's data in an external location. You could always write this logic directly into the `Task` itself, but this can sometimes make testing difficult. Prefect offers a notion of task "checkpointing" that ensures that every time a task is successfully run, its [result handler](results.html#result-handlers) is called. To configure your tasks for checkpointing, provide a result handler and set `checkpoint=True` at task initialization:

```python
from prefect.engine.result_handlers import LocalResultHandler
from prefect import task, Task


class MyTask(Task):
    def run(self):
        return 42


# create a task via initializing our custom Task class
class_task = MyTask(
    checkpoint=True, result_handler=LocalResultHandler(dir="~/.prefect")
)


# create a task via the task decorator
@task(checkpoint=True, result_handler=LocalResultHandler(dir="~/.prefect"))
def func_task():
    return 99
```

The default setting in Prefect Core is that checkpointing is turned _off_. To turn checkpointing on during your flow runs, you can:

- update your [Prefect user configuration file](configuration.html) to include `checkpointing = true` in the `[flows]` section; this option ensures that _all_ Flows which you run will have checkpointing enabled
- set `PREFECT__FLOWS__CHECKPOINTING=true` as an environment variable; this option is better when you only want to temporarily target certain flow runs for checkpointing

Note that checkpointing is always set to `true` for Flows which run in Prefect Cloud.

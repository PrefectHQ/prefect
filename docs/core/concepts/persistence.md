## Persistence and Caching

Out of the box, Prefect Core does not persist data in a permanent fashion.  All data, results, _and_ cached states are stored in memory within the
Python process running the Flow.  


Prefect provides a few ways to work with cached data. Wherever possible, caching is handled automatically or with minimal user input.

[[toc]]

### Input Caching

When running a Prefect flow, it's common to have tasks that will need to be re-run in the future. For example, this could happen when a task fails and needs to be retried, or when a task has a `manual_only` trigger.

Whenever Prefect detects that a task will need to be run in the future, it automatically caches any information that the task needs to run and stores it on the resulting `State`. The next time Prefect encounters the task, the critical information is deserialized and used to run the task.

::: tip Automatic caching
Input caching is an automatic caching. Prefect will automatically apply it whenever necessary.
:::

### Output Caching ("Time Travel")

Sometimes, it's desirable to cache the output of a task to avoid recomputing it in the future. Common examples of this pattern include expensive or time-consuming computations that are unlikely to change. In this case, users can indicate that a task should be cached for a certain duration or as long as certain conditions are met.

This mechanism is sometimes called "Time Travel" because it makes results computed in one flow run available to other runs.

Output caching is controlled with two `Task` arguments: `cache_for` and `cache_validator`.

- `cache_for`: a `timedelta` indicating how long the output should be cached
- `cache_validator`: a `callable` indicating how the cache should be expired. The default is `duration_only`, meaning the cache will be active for the duration of `cache_for`. Other validators can be found in `prefect.engine.cache_validators` and include mechanisms for invalidating the cache if the task receives different inputs or if the flow is run with different parameters.

```python
# this task will be cached for 1 hour
task_1 = prefect.Task(
    cache_for=datetime.timedelta(hours=1))

# this task will be cached for 1 hour, but only if the flow is run with the same parameters
task_2 = prefect.Task(
    cache_for=datetime.timedelta(hours=1),
    cache_validator=prefect.engine.cache_validators.all_parameters)
```

### Checkpointing

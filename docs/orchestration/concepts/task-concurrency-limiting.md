# Task Concurrency Limiting <Badge text="Cloud"/>

::: tip Platform Feature
Setting global concurrency limits is a feature of Prefect Cloud's Platform Tier.
:::

Oftentimes there are situations in which users want to actively prevent too many tasks from running simultaneously; for example, if many tasks across multiple Flows are designed to interact with a database that only allows 10 max connections, we want to ensure that no more than 10 tasks which connect to this database are running at any given time.

Prefect Cloud has built-in functionality for achieving this; Tasks can be "tagged" with as many tags as you wish, and each tag can optionally be provided a concurrency limit. If a task has multiple tags, it will only run if _all_ tags have available concurrency. Tag concurrency limits are enforced globally across your entire team, and tags without explicit limits are considered to have unlimited concurrency.

Note that the ability to _alter_ or _update_ your Tag Concurrency limits requires [Tenant Admin level permissions](tokens.html#tenant).

::: warning Concurrency Limiting requires Core 0.6.6+
Note that in order to utilize this feature, your Flows containing the relevant tagged tasks must be running Prefect version 0.6.6+.
:::

## Tagging your Tasks

Tagging your tasks is as simple as providing a list of tags to your Task at initialization via the `tags` keyword argument:

```python
from prefect import task, Task


# using the task decorator
@task(tags=["database", "aws"])
def my_task():
    pass


# using a custom Task subclass
class MyTask(Task):
    pass

my_task = MyTask(tags=["webservice"])
```

These tags are then available via the `tags` attribute on your Task instances. More information about Task settings and initialization keywords can be found in the corresponding [API documentation](../../api/latest/core/task.html#task-2).

## Setting Concurrency Limits

Once you have tagged your various tasks and [registered your Flow(s)](flows.html#registering-a-flow-from-prefect-core) to Prefect Cloud, you can set concurrency limits on as few or as many tags as you wish. You can set limits in any of the following three ways.

### UI

To set Task tag concurrency limits from the UI, go to Prefect Cloud and navigate to Team Settings -> Task Concurrency Limits.

![](/orchestration/ui/task-concurrency-limits.png)

Select _Add Tag_ to open a dialog where you can set the concurrency limit on a tag. For example, you could set a concurrency limit of 10 on tasks with the "database" tag.

![](/orchestration/ui/task-concurrency-add-limit.png)

This means that Prefect Cloud will ensure that _no more than 10 tasks with the "database" tag will be running at any given time_. You are free to set / update as many of your task tags as you wish, and _all_ of your concurrency limits will be respected.

You can edit and remove the concurrency limit of tags at any time. Select the blue edit icon for your tag to change its concurrency limit. Select the red delete icon for your tag to remove its concurrency limit.

![](/orchestration/ui/task-concurrency-limit-icons.png)

### Core Client

Assuming you are set up with the proper [authentication](api.html) with Prefect Cloud, setting Task tag concurrency limits in the Prefect Client is simple:

```python
from prefect import Client

client = Client()

# set a concurrency limit of 10 on the 'database' tag
client.update_task_tag_limit("database", 10)
```

### GraphQL <Badge text="GQL"/>

To update your tag concurrency limits with GraphQL, issue the following mutation:

```graphql
mutation {
  update_task_tag_limit(input: { tag: "database", limit: 10 }) {
    id
  }
}
```

::: tip You can always update your concurrency limits
Changing the value of a tag concurrency limit is as simple as re-issuing the above mutation with the new value.
:::

To remove all concurrency limits on a tag, issue:

```graphql
mutation {
  delete_task_tag_limit(input: { limit_id: "uuid-returned-from-above" }) {
    success
  }
}
```

## Querying Concurrency Limits

If you wish to query for the currently set limit on a tag, or see _all_ of your limits across all of your tags, you can do so in any of the following three ways.

### UI

You can view your Task tag concurrency limits by navigating to Team Settings -> Task Concurrency Limits. You can also view the current number of task runs that are utilizing available concurrency space.

![](/orchestration/ui/task-concurrency-limit-usage.png)

### Core Client

```python
from prefect import Client

client = Client()

# retrieve the current limit on the "database" tag
# a return value of `None` means no limit is currently set
client.get_task_tag_limit("database")
```

### GraphQL <Badge text="GQL"/>

GraphQL allows you to retrieve tag limit IDs, which is useful for deleting limits:

```graphql
query {
  task_tag_limit(where: { tag: { _eq: "webservice" } }) {
    limit
    id
  }
}
```

You can query for specific tags, as shown above, or retrieve _all_ of your tag limits:

```graphql
query {
  task_tag_limit {
    limit
    id
  }
}
```

## Execution Behavior

Task tag limits are checked whenever a task run attempts to enter a [`Running` state](../../core/concepts/states.html) in Prefect Cloud. If there are no concurrency slots available for any one of your Task's tags, the Task will instead enter a `Queued` state. The same Python process that is attempting running your Task will then attempt to re-enter a `Running` state every 30 seconds (this value is configurable via `config.cloud.queue_interval` in [Prefect Configuration](../../core/concepts/configuration.html)). Additionally, if that process ever fails, Prefect Cloud will create a new runner every 10 minutes, which will then attempt to rerun your task on the specified queue interval. This process will repeat until all requested concurrency slots become available.

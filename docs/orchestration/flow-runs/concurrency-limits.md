# Concurrency limits <Badge text="Cloud"/>

!!! tip Standard Tier Feature
  Setting global concurrency limits is a feature of Prefect Cloud's Standard Tier.


## Flow run limits <Badge text="Cloud"/>

Sometimes, you want to limit the number of flow runs executing simultaneously. For example, you may have an agent on a machine that cannot handle the load of many flow runs.

Prefect Cloud provides functionality to limit the number of simultaneous flow runs. This limit is based on [flow run labels](../agents/overview.md#labels). Flow runs can be given as many labels as you wish, and each label can be provided a concurrency limit. If a flow has multiple labels, it will only run if _all_ the labels have available concurrency. Flow run label concurrency limits are enforced globally across your entire team, and labels without explicit limits are considered to have unlimited concurrency.

### Labeling your flow runs

Labels can be set on a `Flow` via the run config

```python
from prefect import Flow
from prefect.run_configs import UniversalRun

flow = Flow("example-flow")
flow.run_config = UniversalRun(labels=["small-machine"])
```

Labels can also be set per flow run, see the [flow run creation documentation](./creation.md#labels) for details.

### Setting concurrency limits

UI:

To set flow concurrency limits from the UI, go to Prefect Cloud and navigate to Team -> Flow Concurrency.

![](/orchestration/ui/flow-concurrency-limits.png)

Select _Add Label_ to open a dialog where you can set the concurrency limit on a label. For example, you could set a concurrency limit of 10 for flow runs with the "small-machine" label.

![](/orchestration/ui/flow-concurrency-add-limit.png)

This means that Prefect Cloud will ensure that _no more than 10 flow runs with the "small-machine" label will be running at any given time_.

You can edit and remove the concurrency limit of labels at any time. Select the blue edit icon for your label to change its concurrency limit. Select the red delete icon for your label to remove its concurrency limit.

![](/orchestration/ui/flow-concurrency-limit-icons.png)

GraphQL:

To update your flow concurrency limits with GraphQL, issue the following mutation:

```graphql
mutation {
  update_flow_concurrency_limit(input: { label: "small-machine", limit: 10 }) {
    id
  }
}
```

To remove all concurrency limits on a label, issue:

```graphql
mutation {
  delete_flow_concurrency_limit(input: { limit_id: "uuid-returned-from-above" }) {
    success
  }
}
```


### Inspecting concurrency limits

UI:

You can view your flow concurrency limits by navigating to Team -> Flow Concurrency. You can also view the current number of flow runs that are utilizing available concurrency space.

![](/orchestration/ui/flow-concurrency-limit-usage.png)

GraphQL:

GraphQL allows you to retrieve tag limit IDs, which is useful for deleting limits:

```graphql
query {
  flow_concurrency_limit (where: { name: { _eq: "small-machine" } }) {
    limit
    id
  }
}
```

You can query for specific labels, as shown above, or retrieve _all_ of your flow concurrency limits:

```graphql
query {
  flow_concurrency_limit  {
    limit
    name
    id
  }
}
```


## Task run limits <Badge text="Cloud"/>


There are situations in which you want to actively prevent too many tasks from running simultaneously; for example, if many tasks across multiple Flows are designed to interact with a database that only allows 10 max connections, we want to ensure that no more than 10 tasks which connect to this database are running at any given time.

Prefect Cloud has built-in functionality for achieving this; tasks can be "tagged" with as many tags as you wish, and each tag can optionally be provided a concurrency limit. If a task has multiple tags, it will only run if _all_ tags have available concurrency. Tag concurrency limits are enforced globally across your entire team, and tags without explicit limits are considered to have unlimited concurrency.

<!-- TODO:tokens -->
Note that the ability to _alter_ or _update_ your task tag concurrency limits requires tenant admin level permissions.

### Tagging your tasks

Tagging your tasks is as simple as providing a list of tags to your `Task` at initialization via the `tags` keyword argument:

```python
from prefect import task, Task


# While using the task decorator
@task(tags=["database", "aws"])
def my_task():
    pass

# While using a `Task` subclass
class MyTask(Task):
    pass

my_task = MyTask(tags=["webservice"])
```

These tags are then available via the `tags` attribute on your `Task` instances. More information about `Task` settings and initialization keywords can be found in the corresponding [API documentation](../../api/latest/core/task.md#task-2).

### Setting concurrency limits

Once you have tagged your various tasks and [registered your Flow(s)](flows.md#registering-a-flow-from-prefect-core) to Prefect Cloud, you can set concurrency limits on as few or as many tags as you wish. You can set limits in any of the following three ways.

UI:

To set task tag concurrency limits from the UI, go to Prefect Cloud and navigate to Team Settings -> Task Concurrency.

![](/orchestration/ui/task-concurrency-limits.png)

Select _Add Tag_ to open a dialog where you can set the concurrency limit on a tag. For example, you could set a concurrency limit of 10 on tasks with the "database" tag.

![](/orchestration/ui/task-concurrency-add-limit.png)

This means that Prefect Cloud will ensure that _no more than 10 tasks with the "database" tag will be running at any given time_. You are free to set / update as many of your task tags as you wish, and _all_ of your concurrency limits will be respected.

You can edit and remove the concurrency limit of tags at any time. Select the blue edit icon for your tag to change its concurrency limit. Select the red delete icon for your tag to remove its concurrency limit.

![](/orchestration/ui/task-concurrency-limit-icons.png)

Python client:

To update your tag concurrency limits programmatically, use the Prefect library client:

```python
from prefect import Client

client = Client()

# set a concurrency limit of 10 on the 'database' tag
client.update_task_tag_limit("database", 10)
```

GraphQL:

To update your tag concurrency limits with GraphQL, issue the following mutation:

```graphql
mutation {
  update_task_tag_limit(input: { tag: "database", limit: 10 }) {
    id
  }
}
```

To remove all concurrency limits on a tag, issue:

```graphql
mutation {
  delete_task_tag_limit(input: { limit_id: "uuid-returned-from-above" }) {
    success
  }
}
```


### Inspecting concurrency limits

If you wish to query for the currently set limit on a tag, or see _all_ of your limits across all of your tags, you can do so in any of the following three ways.

UI:

You can view your Task tag concurrency limits by navigating to Team Settings -> Task Concurrency. You can also view the current number of task runs that are utilizing available concurrency space.

![](/orchestration/ui/task-concurrency-limit-usage.png)

Python client:

```python
from prefect import Client

client = Client()

# retrieve the current limit on the "database" tag
# a return value of `None` means no limit is currently set
client.get_task_tag_limit("database")
```

GraphQL:

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

### Execution Behavior

Task tag limits are checked whenever a task run attempts to enter a [`Running` state](../../core/concepts/states.md) in Prefect Cloud. If there are no concurrency slots available for any one of your Task's tags, the Task will instead enter a `Queued` state. The same Python process that is attempting running your Task will then attempt to re-enter a `Running` state every 30 seconds (this value is configurable via `config.cloud.queue_interval` in [Prefect Configuration](../../core/concepts/configuration.md)). Additionally, if that process ever fails, Prefect Cloud will create a new runner every 10 minutes, which will then attempt to rerun your task on the specified queue interval. This process will repeat until all requested concurrency slots become available.

# Flow Concurrency Limiting <Badge text="Server">

Oftentimes there are situations in which users want to actively prevent their infrastructure that are running flows from running too many simultaneously. For example, in a testing environment, you may want to create several flow runs at once, but only let a couple of them run at once to avoid overwhelming your infrastructure.

Prefect's Orchestration has built-in functionality for achieving this. To do so, [Execution Environments](../execution/overview.md#labels) can be "labeled" with labels as you wish, and each label can optionally provide a concurrency limit. If an environment has multiple labels, it will only run if _all_ labels have available concurrency. Execution environments without explicit limits are considered to have unlimited concurrency.

## Labeling your Environments

Labeling your environments is as simple as providing a list of labels to your Environment at instantiation via the `labels` keyword argument:

```python
from prefect import Flow
from prefect.environments import RemoteEnvironment

env = RemoteEnvironment(labels=["dev"])
f = Flow("example-label", environment=env)
```

More information about Environment settings and initialization keywords can be found in the corresponding [API documentation](../../orchestration/execution/overview.md).

## Setting Concurrency Limits

Once you have tagged your environment and [registered your Flow(s)](flows.html#registering-a-flow-from-prefect-core), you can set concurrency limits on as few or as many labels as you wish.

### GraphQL <Badge text="GQL">

To update your flow concurrency limits with GraphQL, issue the following mutation:

```graphql
mutation {
  update_flow_concurrency_limit(input: { name: "dev", limit: 10 }) {
    id
  }
}
```

## Querying Concurrency Limits

If you wish to query for the currently set limit on an environment label, or see _all_ of your limits across all of your tags, you can do so with the following.

### GraphQL <Badge text="GQL">

GraphQL allows you to retrieve label limit IDs, which is useful for deleting limits:

```graphql
query {
  flow_concurrency_limit(where: { name: { _eq: "dev" } }) {
    limit
    id
  }
}
```

You can query for specific tags, as shown above, or retrieve _all_ of your tag limits:

```graphql
query {
  flow_concurrency_limit {
    limit
    id
  }
}
```

## Execution Behavior

Flow concurrency limits are checked whenever a flow run attempts to enter a [`Running` state](../../core/concepts/states.html) when using Prefect's Orchestration. If there are no concurrency slots available for any one of your Environment's labels, the Flow will instead enter a `Queued` state. The same python process attempting to run the Flow will then attempt to re-enter a `Running` state every 30 seconds (this value is configurable via `config.cloud.queue_interval` in [Prefect Configuration](../../core/concepts/configuration.html)).

### Execution Behavior Examples

Assuming you issue the following mutations to create concurrency limits, the expected behavior is that any `Environment` tagged with `"prod"` will have at most 10 flows running, while `"dev"` has at most 5. If any environment is tagged as both, the limiting takes the stricter of the two, only allowing 5 flows to run at once.

```graphql
mutation {
  update_flow_concurrency_limit(input: { name: "prod", limit: 10 }) {
    id
  }
}

mutation {
  update_flow_concurrency_limit(input: { name: "dev", limit: 5 }) {
    id
  }
}
```

```python
from prefect import Flow
from prefect.environments import RemoteEnvironment

first_dev_flow = Flow("concurrency-limited-example", environment=RemoteEnvironment(labels=["dev"]))
second_dev_flow = Flow("other-limited-example", environment=RemoteEnvironment(labels=["dev"]))
```

The flow has one label, `"reporting"`, that does not have a concurrency limit associated with it. In this case, this label is ignored for the purposes of concurrency checks, and only is limited by the capacity of `"prod"`.

```python
from prefect import Flow
from prefect.environments import RemoteEnvironment

prod_flow = Flow("concurrency-limited-prod-example", environment=RemoteEnvironment(labels=["prod", "reporting"]))
```

### Failure Recovery: Lazarus <Badge text="Cloud"/>

The `Lazarus` process, among other things, is responsible for rescheduling any flow runs that are stuck in a `Queued` state. To see a full list of Lazurus' responsibilities, see [the docs](services.md#Lazarus).

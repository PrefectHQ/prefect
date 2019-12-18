# Flows

Flows can be registered with Prefect Cloud for scheduling and execution, as well as management of run histories, logs, and other important metrics.

## Registering a Flow from Prefect Core

To register a Flow from Prefect Core, simply use its `register()` method:

```python
flow.register(project_name="<a project name>")
```

Note that this assumes you have already [authenticated](../tutorial/configure.html#log-in-to-prefect-cloud) with Prefect Cloud. For more information on Flow registration see [here](../tutorial/first.html#register-flow-with-prefect-cloud).

## Registering a Flow <Badge text="GQL"/>

To register a Flow via the GraphQL API, first serialize the Flow to JSON:

```python
flow.serialize()
```

Next, use the `createFlow` GraphQL mutation to pass the serialized Flow to Prefect Cloud. You will also need to provide a project ID:

```graphql
mutation($flow: JSON!) {
  createFlow(input: { serializedFlow: $flow, projectId: "<project id>" }) {
    id
  }
}
```

```json
// graphql variables
{
    serializedFlow: <the serialized flow JSON>
}
```

## Flow Versions and Archiving <Badge text="GQL"/>

You can control how Cloud versions your Flows by providing a `versionGroupId` whenever you register a Flow (exposed via the `version_group_id` keyword argument in `flow.register`). Flows which provide the same `versionGroupId` will be considered versions of each other. By default, Flows with the same name in the same Project will be given the same `versionGroupId` and are considered "versions" of each other. Anytime you register a new version of a Flow, Prefect Cloud will automatically "archive" the old version in place of the newly registered Flow. Archiving means that the old version's schedule is set to "Paused" and no new Flow runs can be created.

You can always revisit old versions and unarchive them, if for example you want the same Flow to run on two distinct schedules. To archive or unarchive a Flow, use the following GraphQL mutations:

```graphql
mutation {
  archiveFlow(input: { flowId: "your-flow-id-here" }) {
    id
  }
}
```

```graphql
mutation {
  unarchiveFlow(input: { flowId: "your-flow-id-here" }) {
    id
  }
}
```

## Flow Settings <Badge text="GQL"/>

Prefect Cloud has several insurance policies to ensure Flows run healthily and robustly. Three such policies are:

- Flow and task run heartbeats
- [Lazarus resurrections](lazarus-process.html)
- and version locking

These safeguards can be disabled on a Flow-by-Flow basis using Flow settings.

::: warning Disabling safeguards
Disabling these safeguards can alter fundamental assumptions about how Flows run in Cloud. Be sure to read the docs and understand how each of these settings alters Flow behavior in Cloud.
:::

### Disable Heartbeats <Badge text="0.8.1+"/>

When running Flows registered with Cloud, Prefect Core sends heartbeats to Cloud every 30 seconds. These heartbeats are used to confirm the Flow run and its task runs are healthy, and runs missing four heartbeats in a row will be marked as `Failed` by the [Zombie Killer](zombie-killer.html). For most users, this is a useful safeguard. In some rare cases, however, the heartbeat falls victim to thread deadlocking and falsely registers a run as unhealthy. To prevent this, users may disable Flow heartbeats, which will disable heartbeats and the Zombie Killer for runs of this Flow. To do so, use the following GraphQL mutation:

```graphql
mutation {
  disableFlowHeartbeat(input: { flowId: "your-flow-id-here", value: True }) {
    id
  }
}
```

To reenable heartbeats for a Flow, rerun this mutation with `value` set to `False`. Future runs of this Flow will resume standard heartbeat functionality.

### Disable Lazarus

The Lazarus process is responsible for rescheduling flow runs under the circumstances described [here](lazarus-process.html). If this is not desirable behavior for your Flow, use the following GraphQL mutation to disable it:

```graphql
mutation {
  disableLazarusForFlow(input: { flowId: "your-flow-id-here", value: True }) {
    id
  }
}
```

To reenable Lazarus resurrections for a flow, rerun this mutation with `value` set to `False`. Future runs of this flow will be subject to Lazarus resurrection.

### Disable Version Locking

Prefect Cloud's version locking mechanism enforces the assertion that your work runs once _and only once_. For some, primarily those running highly-distributed, idempotent operations, this guarantee is less useful. To disable version locking for a flow and its tasks, use the following GraphQL mutation:

```graphql
mutation {
  disableFlowVersionLocking(
    input: { flowId: "your-flow-id-here", value: True }
  ) {
    id
  }
}
```

To reenable version locking for a Flow, rerun this mutation with `value` set to `False`. Future runs of this Flow will resume standard version locking behavior.

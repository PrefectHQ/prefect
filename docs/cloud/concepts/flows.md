# Flows

Flows can be registered with Prefect Cloud for scheduling and execution, as well as management of run histories, logs, and other important metrics.

## Registering a Flow from Prefect Core

To register a flow from Prefect Core, use its `register()` method:

```python
flow.register(project_name="<a project name>")
```

Note that this assumes you have already [authenticated](../tutorial/configure.html#log-in-to-prefect-cloud) with Prefect Cloud. For more information on Flow registration see [here](../tutorial/first.html#register-flow-with-prefect-cloud).

## Registering a Flow <Badge text="GQL"/>

To register a flow via the GraphQL API, first serialize the `Flow` object to JSON:

```python
flow.serialize()
```

Next, use the `createFlow` GraphQL mutation to pass the serialized `Flow` to Prefect Cloud. You will also need to provide a project ID:

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

You can control how Cloud versions your flows by providing a `versionGroupId` whenever you register a flow (exposed via the `version_group_id` keyword argument in `flow.register`). Flows which provide the same `versionGroupId` will be considered versions of each other. By default, flows with the same name in the same Project will be given the same `versionGroupId` and are considered "versions" of each other. Anytime you register a new version of a flow, Prefect Cloud will automatically "archive" the old version in place of the newly registered flow. Archiving means that the old version's schedule is set to "Paused" and no new flow runs can be created.

You can always revisit old versions and unarchive them, if for example you want the same flow to run on two distinct schedules. To archive or unarchive a flow, use the following GraphQL mutations:

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

Prefect Cloud has several insurance policies to ensure flows run healthily and robustly. Three such policies are:

- Flow and task run heartbeats
- [Lazarus resurrections](lazarus-process.html)
- and version locking

These safeguards can be toggled on a flow-by-flow basis using flow settings.

::: warning Disabling safeguards
Disabling these safeguards can alter fundamental assumptions about how flows run in Cloud. Be sure to read the docs and understand how each of these settings alters flow behavior in Cloud.
:::

### Disable Heartbeats <Badge text="0.8.1+"/>

When running flows registered with Cloud, Prefect Core sends heartbeats to Cloud every 30 seconds. These heartbeats are used to confirm the flow run and its task runs are healthy, and runs missing four heartbeats in a row will be marked as `Failed` by the [Zombie Killer](zombie-killer.html). For most users, this is a useful safeguard. In some rare cases, however, the heartbeat falls victim to thread deadlocking and falsely registers a run as unhealthy. To prevent this, users may disable flow heartbeats, which will disable heartbeats and the Zombie Killer for runs of this flow. To do so, use the following GraphQL mutation:

```graphql
mutation {
  disableFlowHeartbeat(input: { flowId: "your-flow-id-here", value: true }) {
    success
  }
}
```

To reenable heartbeats for a flow, rerun this mutation with `value` set to `False`. Future runs of this flow will resume standard heartbeat functionality.

### Disable Lazarus

The Lazarus process is responsible for rescheduling flow runs under the circumstances described [here](lazarus-process.html). If this is not desirable behavior for your flow, use the following GraphQL mutation to disable it:

```graphql
mutation {
  disableLazarusForFlow(input: { flowId: "your-flow-id-here", value: true }) {
    success
  }
}
```

To reenable Lazarus resurrections for a flow, rerun this mutation with `value` set to `False`. Future runs of this flow will be subject to Lazarus resurrection.

### Enable Version Locking

Prefect Cloud's _opt-in_ version locking mechanism enforces the assertion that your work runs once _and only once_. To enable version locking for a flow and its tasks, use the following GraphQL mutation:

```graphql
mutation {
  enableFlowVersionLocking(
    input: { flowId: "your-flow-id-here", value: true }
  ) {
    success
  }
}
```

To disable this functionality again, rerun this mutation with `value` set to `False`. Future runs of this flow will once again ignore the version locking mechanism.

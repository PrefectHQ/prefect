# Flows

Flows can be registered with Prefect Cloud for scheduling and execution, as well as management of run histories, logs, and other important metrics.

## Registering a flow from Prefect Core

To register a flow from Prefect Core, simply use its `register()` method:

```python
flow.register(project_name="<a project name>")
```

Note that this assumes you have already [authenticated](auth.md) with Prefect Cloud.  For more information on Flow registration see [here](../flow-register.html).

## Registering a flow <Badge text="GQL"/>

To register a flow via the GraphQL API, first serialize the flow to JSON:

```python
flow.serialize()
```

Next, use the `createFlow` GraphQL mutation to pass the serialized flow to Prefect Cloud. You will also need to provide a project ID:

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

You can control how Cloud versions your Flows by providing a `versionGroupId` whenever you register a Flow (exposed via the `version_group_id` keyword argument in `flow.register`).  Flows which provide the same `versionGroupId` will be considered versions of each other. By default, Flows with the same name in the same Project will be given the same `versionGroupId` and are considered "versions" of each other.  Anytime you register a new version of a flow, Prefect Cloud will automatically "archive" the old version in place of the newly registered flow.  Archiving means that the old version's schedule is set to "Paused" and no new flow runs can be created.

You can always revisit old versions and unarchive them, if for example you want the same Flow to run on two distinct schedules.  To archive or unarchive a flow, use the following GraphQL mutations:

```graphql
mutation {
  archiveFlow( input: { flowId: "your-flow-id-here" }) {
    id
  }
}
```

```graphql
mutation {
  unarchiveFlow( input: { flowId: "your-flow-id-here" }) {
    id
  }
}
```

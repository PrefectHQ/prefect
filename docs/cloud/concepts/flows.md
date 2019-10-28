# Flows

Flows can be deployed to Prefect Cloud for scheduling and execution, as well as management of run histories, logs, and other important metrics.

## Deploying a flow from Prefect Core

To deploy a flow from Prefect Core, simply use its `deploy()` method:

```python
flow.deploy(project_name="<a project name>")
```

Note that this assumes you have already [authenticated](auth.md) with Prefect Cloud.  For more information on Flow deployment see [here](../flow-deploy.html).

## Deploying a flow <Badge text="GQL"/>

To deploy a flow via the GraphQL API, first serialize the flow to JSON:

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

Flows with the same name in the same Project are considered "versions" of each other.  Anytime you deploy a flow to a project which contains a flow of the same name, Prefect Cloud will automatically "archive" the old version in place of the newly deployed flow.  Archiving means that the old version's schedule is set to "Paused" and no new flow runs can be created.  You can always revisit old versions and unarchive them, if for example you want the same Flow to run on two distinct schedules.  To archive or unarchive a flow, use the following GraphQL mutations:

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

# Flows

Flows can be deployed to Prefect Cloud for scheduling and execution, as well as management of run histories, logs, and other important metrics.

## Deploying a flow from Prefect Core

To deploy a flow from Prefect Core, simply use its `deploy()` method:

```python
flow.deploy(project_name="<a project name>")
```

Note that this assumes you have already [authenticated](auth.md) with Prefect Cloud.

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

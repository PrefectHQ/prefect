# Flows

## Deploying a flow (from Prefect Core)

To deploy a flow from Prefect Core, simply use its `deploy` method:

```python
flow.deploy(project_id="<a project id>")
```

## Deploying a flow (via GraphQL)

To deploy a flow via the Prefect Cloud API, use the following GraphQL mutation:

```graphql
mutation($flow: JSON!) {
  createFlow(input: { serializedFlow: $flow, projectId: "<project id>" }) {
    id
    error
  }
}
```

The `flow` variable should be the JSON returned by calling `flow.serialize(build=True)` in Prefect Core:

```json
{
    serializedFlow: <the serialized flow JSON>
}
```

# Authentication

In order to use the Cloud APIs from your local machine, you'll need to generate an API token.

To generate an API token, use the Cloud UI or the following GraphQL call:

```graphql
mutation {
  createAPIToken(input: { name: "My API token", role: USER }) {
    token
  }
}
```

## Prefect Core client

This token can either be added to your Prefect [user configuration file](../../guide/core_concepts/configuration.html):

```
[cloud]
auth_token = "<your auth token>"
```

or assigned to the environment variable `PREFECT__CLOUD__AUTH_TOKEN`.

## GraphQL

You can also use your API token to communicate directly with the Cloud GraphQL API, including the GraphQL Playground. Simply include the token in your HTTP headers like this:

```json
{ "Authorization": "Bearer <token>" }
```

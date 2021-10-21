---
sidebarDepth: 2
---

# API

Prefect exposes a powerful GraphQL API for interacting with the platform and is accessed through `https://api.prefect.io` when using Prefect Cloud or `http://localhost:4200` when using the default Prefect Core setup. There are a variety of ways you can access the API.

## Authentication <Badge text="Cloud"/>

In order to interact with Prefect Cloud from your local machine, you'll need to generate an API key.

To generate an API key, use the Cloud UI or the following GraphQL call (from an already authenticated client!):

```graphql
mutation {
  create_api_key(input: { user_id: <user_id>, name: "My API key" }) {
    key
  }
}
```

### API Keys

To authenticate with Prefect Cloud, an API key is required. Users can generate a key associated with their user, or they can generate keys associated with a Service Account User. See [the API keys page](api_keys.html) for more details.

## Python Client

### About the Client

Prefect Core includes a Python client for interacting with the API. The Python client was designed for both interactive and programmatic use, and includes convenience methods for transparently managing authentication when used with API keys.

### Getting Started

If using Prefect Server, no authentication is required. This means the Python Client can be used immediately without any extra configuration:

```python
import prefect
client = prefect.Client()

client.graphql(
    {
        'query': {
            'flow': {
                'id'
            }
        }
    }
)
```

### Authenticating the Client with Cloud <Badge text="Cloud"/>

If using Prefect Cloud, authentication is required. See the [API key documentation](./api_keys.md) for instructions on creating and using API keys.

We recommend using the CLI to manage authentication, but authentication may be passed directly to the `Client` as well.

The API key can be passed directly to the client:

```python
import prefect

client = prefect.Client(api_key="API_KEY")
```

Since API keys can be used across tenants if linked to a user account, you may also pass a tenant:

```python
client = prefect.Client(api_key="API_KEY", tenant_id="<id>")
```

If you do not pass a tenant, it will be left as `None` which means the default tenant associated with the API key will be used for requests. In that case, you can get the default tenant associated with the key from the client:

```python
client.tenant_id
```

The tenant id can be changed on an existing client, but requests will fail if the API key is not valid for that tenant:

```python
client.tenant_id = "<new-id>"
```

Authentication can be saved to disk. This will save the current API key and tenant id to `~/.prefect/auth.toml` and future clients instantiated without an API key or tenant id will load these values as defaults.

```python
client.save_auth_to_disk()
```


To inspect the auth stored on disk, you may also use the client method `load_auth_from_disk()`:

```python
disk_auth = client.load_auth_from_disk()
# {"api_key": "API_KEY", "tenant_id": "ID"}
```

After authenticating, you can make any GraphQL query against the Cloud API:

```python
client.graphql(
    {
        'query': {
            'flow': {
                'id'
            }
        }
    }
)
```

## GraphQL

Prefect exposes a full GraphQL API for querying and interacting with the platform.

We've designed this API to be clear and powerful. Not only does it allow users to send instructions to the backend, it allows users to fully introspect every piece of relevant data.

Throughout these docs, sections directly related to the GraphQL API are denoted with a <Badge text="GQL" vertical="middle"/> badge.

### Interactive API in the UI

For ease of interacting with the GraphQL API, the UI contains a full GraphQL client that automatically handles authentication. See the [Interactive API](/orchestration/ui/interactive-api) docs for more.

### Client

Make GraphQL queries directly from the client:

```python
client.graphql(
    {
        'query': {
            'flow': {
                'id'
            }
        }
    }
)
```

### Other clients <Badge text="Cloud"/>
To use API keys in other clients such as cURL, include the API key as the `authorization` header:

```json
{ "authorization": "Bearer API_KEY" }
```

### Queries

All Prefect API metadata may be queried via GraphQL. You can view the interactive GraphQL schema browser for an API reference and complete details on available fields. In general, the API exposes a SQL-like interface for accessing data.

For example, the following query retrieves the id and name of all flows with names ending in "train", as well as the state of their most recent flow run:

```graphql
query {
  flow(where: { name: { _ilike: "%train" } }) {
    id
    name
    flow_run(order_by: { start_time: desc }, limit: 1) {
      id
      state
    }
  }
}
```

In this example, we retrieve the name, start time, and end time of the 5 task runs that failed
most recently:

```graphql
query {
  task_run(
    where: { state: { _eq: "Failed" } }
    order_by: { state_timestamp: desc }
    limit: 5
  ) {
    name
    start_time
    end_time
  }
}
```

### Mutations

In order to interact with the Prefect API, users can issue "mutations," which represent various actions. You can view the interactive GraphQL schema browser for an API reference and complete details on available fields.

Most sections of these concepts docs show examples of relevant mutations.

### Formatting and Conventions

#### IDs

All Prefect IDs are UUIDs and should be provided as strings.

##### Example:

```graphql
query {
  flow(where: { id: { _eq: "07786de2-7283-434f-a9b1-600044a8afb3" } }) {
    name
  }
}
```

#### Dates & Times

Dates and times should be provided as ISO 8601-formatted strings. If no time zone information is included, UTC will be assumed.

##### Example:

```graphql
query {
  flow_run(where: { start_time: { _gt: "2019-01-01 12:00:00" } }) {
    id
    start_time
  }
}
```

#### JSON

GraphQL has a difficult time parsing JSON inline, so we recommend providing any JSON values as GraphQL variables.

##### Example:

```graphql
mutation($state: JSON!) {
  set_flow_run_state(
    input: {
      id: "61cab648-f09d-467d-b205-3892c8d55250"
      version: 1
      state: $state
    }
  ) {
    id
    start_time
  }
}
```

with variables:

```json
{
  "state": {
    "type": "Scheduled"
  }
}
```

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

Prefect Cloud users can generate API Keys for their user, or create Service Accounts and API Keys associated with them.  For more information on hwo to manage these keys, go [here](api_keys.html)

## Python Client

### About the Client

Prefect Core includes a Python client for interacting with the API. The Python client was designed for both interactive and programmatic use, and includes convenience methods for transparently managing authentication when used with API keys.

### Getting Started

If using Prefect Core's server, no authentication is required. This means the Python client can be used immediately without any extra configuration:

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

If using Prefect Cloud, authentication is required. For interactive use, the most common way to use the Cloud Client is to generate an API key and provide it to the client. After doing so, users can save the API key so it persists across all Python sessions:

```python
import prefect
client = prefect.Client(api_token="API_KEY")
client.save_api_token()
```

Now, starting a client in another session will automatically reload the token:

```python
client = prefect.Client()
assert client._api_token == "API_KEY"  # True
```

Note that an API key can be provided by environment variable (`PREFECT__CLOUD__AUTH_TOKEN`) or in your Prefect config (under `cloud.auth_token`).

Once provisioned with an API key, the Cloud Client can query for available tenants and login to those tenants. In order to query for tenants, call:

```python
client.get_available_tenants()
```

This will print the id, name, and slug of all the tenants the user can login to.

```python
client.login_to_tenant(tenant_slug='a-tenant-slug')
# OR
client.login_to_tenant(tenant_id='A_TENANT_ID')
```

Both of these calls persist the active tenant in local storage, so you won't have to login again until you're ready to switch tenants.

Once logged in, you can make any GraphQL query against the Cloud API:

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

(Note that this illustrates how Prefect can parse Python structures to construct GraphQL query strings!)

Finally, you can logout:

```python
client.logout_from_tenant()
```

## GraphQL

Prefect exposes a full GraphQL API for querying and interacting with the platform.

We've designed this API to be clear and powerful. Not only does it allow users to send instructions to the backend, it allows users to fully introspect every piece of relevant data.

Throughout these docs, sections directly related to the GraphQL API are denoted with a <Badge text="GQL" vertical="middle"/> badge.

### Interactive API in the UI

For ease of interacting with the GraphQL API, the UI contains a full GraphQL client that automatically handles authentication. See the [Interactive API](/orchestration/ui/interactive-api) docs for more.

### Client <Badge text="Cloud"/>

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

### Other clients
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

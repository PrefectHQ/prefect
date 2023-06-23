---
description: Prefect REST API for interacting with the orchestration engine and Prefect Cloud.
tags:
    - REST API
    - Prefect Cloud
    - Prefect server
    - curl
    - PrefectClient
    - Requests
    - API reference
---

# REST API

The Prefect REST API is used for communicating data from clients to a Prefect server so that orchestration can be performed. This API is consumed by clients such as the Prefect Python SDK or the server dashboard.

Prefect Cloud and a locally hosted Prefect server each provide a REST API.

- Prefect Cloud:
    - [Interactive Prefect Cloud REST API documentation](https://app.prefect.cloud/api/docs)
    - [Finding your Prefect Cloud details](#finding-your-prefect-cloud-details)
- A Locally hosted open-source Prefect server:
    - Interactive REST API documentation for a locally hosted open-source Prefect server is available at `http://localhost:4200/docs` or the `/docs` endpoint of the [PREFECT_API_URL](/concepts/settings/#prefect_api_url) you have configured to access the server. You must have the server running with `prefect server start` to access the interactive documentation.
    - [Prefect REST API documentation](/api-ref/rest-api-reference/)

## Interacting with the REST API

You have many options to interact with the Prefect REST API:

- Create an instance of [`PrefectClient`](/api-ref/prefect/client/orchestration/#prefect.client.orchestration.PrefectClient) 
- Use your favorite Python HTTP library such as [Requests](https://requests.readthedocs.io/en/latest/) or [HTTPX](https://www.python-httpx.org/)
- Use an HTTP library in your language of choice
- Use [curl](https://curl.se/) from the command line 

### PrefectClient with a Prefect server
This example uses `PrefectClient` with a locally hosted Prefect server:

```python
import asyncio
from prefect.client import get_client

async def get_flows():
    client = get_client()
    r = await client.read_flows(limit=5)
    return r

r = asyncio.run(get_flows())

for flow in r:
    print(flow.name, flow.id)

if __name__ == "__main__":
    asyncio.run(get_flows())
```

Output:

<div class="terminal">
```bash
cat-facts 58ed68b1-0201-4f37-adef-0ea24bd2a022
dog-facts e7c0403d-44e7-45cf-a6c8-79117b7f3766
sloth-facts 771c0574-f5bf-4f59-a69d-3be3e061a62d
capybara-facts fbadaf8b-584f-48b9-b092-07d351edd424
lemur-facts 53f710e7-3b0f-4b2f-ab6b-44934111818c
```
</div>

### Requests with Prefect

This example uses the Requests library with Prefect Cloud to return the five newest artifacts.

```python
import requests

PREFECT_API_URL="https://api.prefect.cloud/api/accounts/abc-my-cloud-account-id-is-here/workspaces/123-my-workspace-id-is-here"
PREFECT_API_KEY="123abc_my_api_key_goes_here"
data = {
    "sort": "CREATED_DESC",
    "limit": 5,
    "artifacts": {
        "key": {
            "exists_": True
        }
    }
}

headers = {"Authorization": f"Bearer {PREFECT_API_KEY}"}
endpoint = f"{PREFECT_API_URL}/artifacts/filter"

response = requests.post(endpoint, headers=headers, json=data)
assert response.status_code == 200
for artifact in response.json():
    print(artifact)
```

### curl with Prefect Cloud

This example uses curl with Prefect Cloud to create a flow run:

```bash
ACCOUNT_ID="abc-my-cloud-account-id-goes-here"
WORKSPACE_ID="123-my-workspace-id-goes-here"
PREFECT_API_URL="https://api.prefect.cloud/api/accounts/$ACCOUNT_ID/workspaces/$WORKSPACE_ID"
PREFECT_API_KEY="123abc_my_api_key_goes_here"
DEPLOYMENT_ID="my_deployment_id"

curl --location --request POST "$PREFECT_API_URL/deployments/$DEPLOYMENT_ID/create_flow_run" \
  --header "Content-Type: application/json" \
  --header "Authorization: Bearer $PREFECT_API_KEY" \
  --header "X-PREFECT-API-VERSION: 0.8.4" \
  --data-raw "{}"
```

Note that in this example `--data-raw "{}"` is required and is where you can specify other aspects of the flow run such as the state. Windows users substitute `^` for `\` for line multi-line commands.


## Finding your Prefect Cloud details

When working with the Prefect Cloud REST API you will need your Account ID and often the Workspace ID for the [workspace](/cloud/workspaces/) you want to interact with. You can find both IDs for a [Prefect profile](/concepts/settings/) in the CLI with `prefect profile inspect my_profile`. This command will also display your [Prefect API key](/cloud/users/api-keys/), as shown below:

<div class="terminal">
```bash
PREFECT_API_URL='https://api.prefect.cloud/api/accounts/abc-my-account-id-is-here/workspaces/123-my-workspace-id-is-here'
PREFECT_API_KEY='123abc_my_api_key_is_here'
```
</div>

Alternatively, view your Account ID and Workspace ID in your browser URL. For example: `https://app.prefect.cloud/account/abc-my-account-id-is-here/workspaces/123-my-workspace-id-is-here`. 


## REST Guidelines

The REST APIs adhere to the following guidelines:

- Collection names are pluralized (for example, `/flows` or `/runs`).
- We indicate variable placeholders with colons: `GET /flows/:id`.
- We use snake case for route names: `GET /task_runs`.
- We avoid nested resources unless there is no possibility of accessing the child resource outside the parent context. For example, we query `/task_runs` with a flow run filter instead of accessing `/flow_runs/:id/task_runs`.
- The API is hosted with an `/api/:version` prefix that (optionally) allows versioning in the future. By convention, we treat that as part of the base URL and do not include that in API examples.
- Filtering, sorting, and pagination parameters are provided in the request body of `POST` requests where applicable.
    - Pagination parameters are `limit` and `offset`.
    - Sorting is specified with a single `sort` parameter.
    - See more information on [filtering](#filtering) below.

### HTTP verbs

- `GET`, `PUT` and `DELETE` requests are always idempotent. `POST` and `PATCH` are not guaranteed to be idempotent.
- `GET` requests cannot receive information from the request body.
- `POST` requests can receive information from the request body.
- `POST /collection` creates a new member of the collection.
- `GET /collection` lists all members of the collection.
- `GET /collection/:id` gets a specific member of the collection by ID.
- `DELETE /collection/:id` deletes a specific member of the collection.
- `PUT /collection/:id` creates or replaces a specific member of the collection.
- `PATCH /collection/:id` partially updates a specific member of the collection.
- `POST /collection/action` is how we implement non-CRUD actions. For example, to set a flow run's state, we use `POST /flow_runs/:id/set_state`.
- `POST /collection/action` may also be used for read-only queries. This is to allow us to send complex arguments as body arguments (which often cannot be done via `GET`). Examples include `POST /flow_runs/filter`, `POST /flow_runs/count`, and `POST /flow_runs/history`.

## Filtering

Objects can be filtered by providing filter criteria in the body of a `POST` request. When multiple criteria are specified, logical AND will be applied to the criteria.

Filter criteria are structured as follows:

```json
{
    "objects": {
        "object_field": {
            "field_operator_": <field_value>
        }
    }
}
```

In this example, `objects` is the name of the collection to filter over (for example, `flows`). The collection can be either the object being queried for (`flows` for `POST /flows/filter`) or a related object (`flow_runs` for `POST /flows/filter`).

`object_field` is the name of the field over which to filter (`name` for `flows`). Note that some objects may have nested object fields, such as `{flow_run: {state: {type: {any_: []}}}}`.

`field_operator_` is the operator to apply to a field when filtering. Common examples include:

- `any_`: return objects where this field matches any of the following values.
- `is_null_`: return objects where this field is or is not null.
- `eq_`: return objects where this field is equal to the following value.
- `all_`: return objects where this field matches all of the following values.
- `before_`: return objects where this datetime field is less than or equal to the following value.
- `after_`: return objects where this datetime field is greater than or equal to the following value.

For example, to query for flows with the tag `"database"` and failed flow runs, `POST /flows/filter` with the following request body:

```json
{
    "flows": {
        "tags": {
            "all_": ["database"]
        }
    },
    "flow_runs": {
        "state": {
            "type": {
              "any_": ["FAILED"]
            }
        }
    }
}
```

## OpenAPI

The Prefect REST API can be fully described with an OpenAPI 3.0 compliant document. [OpenAPI](https://swagger.io/docs/specification/about/) is a standard specification for describing REST APIs.

To generate the Prefect server's complete OpenAPI document, run the following commands in an interactive Python session:

```python
from prefect.server.api.server import create_app

app = create_app()
openapi_doc = app.openapi()
```

This document allows you to generate your own API client, explore the API using an API inspection tool, or write tests to ensure API compliance.

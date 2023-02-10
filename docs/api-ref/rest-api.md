---
description: Prefect REST API for interacting with the orchestration engine and Prefect Cloud.
tags:
    - REST API
    - Prefect Cloud
---

Both Prefect Cloud and locally run Prefect servers host a REST API that gives you access to many observability, coordination, and account management functions of the platform.

Prefect Cloud REST API documentation is available at <a href="https://app.prefect.cloud/api/docs" target="_blank">https://app.prefect.cloud/api/docs</a>.

The Prefect REST API documentation for locally run open-source Prefect servers is available in the [Prefect REST API Reference](/api-ref/rest-api-reference/).

!!! note "Prefect REST API interactive documentation"
    If you are running a local instance of the Prefect server with `prefect server start`, the Prefect REST API documentation for your instance is available at <a href="http://localhost:4200/docs" target="_blank">http://localhost:4200/docs</a> or the `/docs` endpoint of the [`PREFECT_API_URL`](/concepts/settings/#prefect_api_url) you have configured to access the server.

## REST Guidelines

The Prefect REST API adheres to the following guidelines:

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

To generate Prefect's complete OpenAPI document, run the following commands in an interactive Python session:

```python
from prefect.server.api.server import create_app

app = create_app()
openapi_doc = app.openapi()
```

This document allows you to generate your own API client, explore the API using an API inspection tool, or write tests to ensure API compliance.
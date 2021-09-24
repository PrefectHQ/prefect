## Overview

The Prefect Orion REST API can be fully described with an OpenAPI 3.0 compliant document. [OpenAPI](https://swagger.io/docs/specification/about/) is a standard specification for describing [REST APIs](https://technically.dev/posts/apis-for-the-rest-of-us). 

To generate Orion's complete OpenAPI document, run the following commands in an interactive Python session:

```python
from prefect.orion.api.server import app

openapi_doc = app.openapi()
```

This document allows you to generate your own API client, explore the API using an API inspection tool, or write tests to ensure API compliance.

## REST Guidelines

The Orion REST API adheres to the following guidelines:

- Collection names are pluralized (e.g., `/flows`, `/runs`)
- We indicate variable placeholders with colons (e.g., `GET /flows/:id`)
- We use snake case for route names (e.g. `GET /task_runs`)
- We avoid nested resources unless there is no possibility of accessing the child resource outside the parent context. For example, we query `/task_runs` with a flow run filter instead of accessing `/flow_runs/:id/task_runs`.
- **HTTP verbs**:
    - `GET`, `PUT` and `DELETE` requests are always idempotent; `POST` and `PATCH` are not guaranteed to be idempotent
    - `GET` requests can not receive information from the request body
    - `POST` requests can receive information from the request body
    - `POST /collection` creates a new member of the collection
    - `GET /collection` lists all members of the collection
    - `GET /collection/:id` gets a specific member of the collection by ID
    - `DELETE /collection/:id` deletes a specific member of the collection 
    - `PUT /collection/:id` creates or replaces a specific member of the collection
    - `PATCH /collection/:id` partially updates a specific member of the collection
    - `POST /collection/action` is how we implement non-CRUD actions. For example, to set a flow run's state, we use `POST /flow_runs/:id/set_state`.
    - `POST /collection/action` may also be used for read-only queries. This is to allow us to send complex arguments as body arguments (which often can not be done via GET). Examples include `POST /flow_runs/filter`, `POST /flow_runs/count`, and `POST /flow_runs/history`.

## Orion REST API Reference

The following REST API reference was automatically generated using [Swagger UI](https://swagger.io/tools/swagger-ui/).

!!swagger schema.json!!

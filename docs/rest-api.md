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
- **HTTP verbs**:
    - `GET`, `PUT` and `DELETE` operations are always idempotent; `POST` and `PATCH` are not guaranteed to be idempotent
    - `POST` requests receive information only from the request body
    - `POST /collection` creates a new member of the collection
    - `GET /collection` lists all members of the collection
    - `GET /collection/:id` gets a specific member of the collection by ID
    - `DELETE /collection/:id` deletes a specific member of the collection 
    - `PUT /collection/:id` replaces a specific member of the collection
    - `PATCH /collection/:id` partially updates a specific member of the collection
    - `POST /collection/:id/action` is how non-CRUD actions are exposed for specific members of the collection

## Orion REST API Reference

The following REST API reference was automatically generated using [Swagger UI](https://swagger.io/tools/swagger-ui/).

!!swagger schema.json!!

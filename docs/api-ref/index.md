---
description: Prefect APIs enable you to interact programmatically with the REST API and Prefect Cloud.
icon: octicons/book-16
tags:
    - API
    - Prefect API
    - Prefect Cloud
    - REST API
    - development
    - orchestration
---

# API References

Prefect provides several APIs. 

- The [Prefect Python SDK API](/api-ref/python/) is used to build, test, and execute workflows against the Prefect orchestration engine. This is the primary user-facing API.
- The [Prefect REST API](/api-ref/rest-api/) is used for communicating data from clients to the Prefect server so that orchestration can be performed. This API is consumed by clients such as the Prefect Python SDK or the server dashboard.
    -  Prefect Cloud REST API documentation is available at <a href="https://app.prefect.cloud/api/docs" target="_blank">https://app.prefect.cloud/api/docs</a>.
    - The REST API documentation for a locally hosted open-source Prefect server is available at <a href="http://localhost:4200/docs" target="_blank">http://localhost:4200/docs</a> or the `/docs` endpoint of the [`PREFECT_API_URL`](/concepts/settings/#prefect_api_url) you have configured to access the server.
    - The REST API documentation for a locally hosted open-source Prefect server is also available in the [Prefect REST API Reference](/api-ref/rest-api-reference/).
- The [Prefect Server API](/api-ref/server/) is used by the server to work with workflow metadata and enforce orchestration logic. This API is primarily used by Prefect developers.

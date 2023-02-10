---
description: Prefect APIs enable you to interact programmatically with flows, deployments, the REST API, and Prefect Cloud.
tags:
    - API
    - Prefect API
    - Prefect Cloud
    - REST API
    - development
    - orchestration
---

# API Reference

Prefect 2 provides a number of programmatic workflow interfaces. Each API is documented in this section. 

- The Prefect Python API is used to build, test, and execute workflows against the Prefect orchestration engine. This is the primary user-facing API.
- The Prefect Server API is used by the server to work with workflow metadata and enforce orchestration logic. This API is primarily used by Prefect developers.
- The [Prefect REST API](/api-ref/rest-api/) is used for communicating data from clients to the Prefect server so that orchestration can be performed. This API is mainly consumed by clients like the Prefect Python Client or the server dashboard.

!!! note "Prefect REST API interactive documentation"
    Prefect Cloud REST API documentation is available at <a href="https://app.prefect.cloud/api/docs" target="_blank">https://app.prefect.cloud/api/docs</a>.

    The Prefect REST API documentation for a local instance run with with `prefect server start` is available at <a href="http://localhost:4200/docs" target="_blank">http://localhost:4200/docs</a> or the `/docs` endpoint of the [`PREFECT_API_URL`](/concepts/settings/#prefect_api_url) you have configured to access the server.

    The Prefect REST API documentation for locally run open-source Prefect servers is also available in the [Prefect REST API Reference](/api-ref/rest-api-reference/).

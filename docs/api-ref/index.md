---
description: Explore Prefect's auto-generated reference documentation.
tags:
    - API
    - Prefect API
    - Prefect SDK
    - Prefect Cloud
    - REST API
    - development
    - orchestration
---

# API Reference

Prefect auto-generates reference documentation for the following components:

- **[Prefect Python SDK](/api-ref/python/)**: used to build, test, and execute workflows.
- **[Prefect REST API](/api-ref/rest-api/)**: used by both workflow clients as well as the Prefect UI for orchestration and data retrieval
  - Prefect Cloud REST API documentation is available at <a href="https://app.prefect.cloud/api/docs" target="_blank">https://app.prefect.cloud/api/docs</a>.
  - The REST API documentation for a locally hosted open-source Prefect server is available in the [Prefect REST API Reference](/api-ref/rest-api-reference/).
- **[Prefect Server SDK](/api-ref/server/)**: used primarily by the server to work with workflow metadata and enforce orchestration logic. This is only used directly by Prefect developers and contributors.

!!! Note "Self-hosted docs"
    When self-hosting, you can access REST API documentation at the `/docs` endpoint of your [`PREFECT_API_URL`](/concepts/settings/#prefect_api_url) - for example, if you ran `prefect server start` with no additional configuration you can find this reference at <a href="http://localhost:4200/docs" target="_blank">http://localhost:4200/docs</a>.

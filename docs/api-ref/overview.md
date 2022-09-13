---
description: Prefect APIs enable you to interact programmatically with flows, deployments, the Orion API, and Prefect Cloud.
tags:
    - API
    - Orion API
    - Prefect Cloud
    - REST API
    - development
    - orchestration
---

# API Reference

Prefect 2 provides a number of programmatic workflow interfaces. Each API is documented in this section. 

- The Prefect Python API is used to build, test, and execute workflows against the Orion workflow engine. This is the primary user-facing API.
- The Prefect Orion Python API is used by the Orion server to work with workflow metadata and enforce orchestration logic. This API is primarily used by Orion developers.
- The Prefect Orion REST API is used for communicating data from Orion clients to the Orion server so that orchestration can be performed. This API is mainly consumed by Orion clients like the Prefect Python Client or the Orion Dashboard.

---
description: Prefect deployments elevate flows, allowing flow runs to be scheduled and triggered via API. Learn how to easily manage your code and deployments.
tags:
    - orchestration
    - flow runs
    - deployments
    - schedules
    - triggers
    - prefect.yaml
    - infrastructure
    - storage
    - work pool
    - worker
search:
  boost: 2
---
# Deployments

Deployments are server-side representations of flows that contain the crucial metadata needed for remote orchestration. 
They elevate workflows from functions that you call manually to API-managed entities.
Deployments achieve this by storing all of the relevant metadata for _when_, _where_ and _how_ a workflow should run.

Here we will focus largely on the metadata that defines a deployment and how it is used; different ways of creating a deployment populate these fields differently as we will see.

## Overview

Every Prefect deployment references one and only one "entrypoint" flow (though that flow may itself call any number of subflows). Different deployments may reference the same underlying flow, a useful pattern when developing or promoting workflow changes through staged environments.

The complete schema that defines a deployment is as follows:

```python
class Deployment:
    """
    Structure of the schema defining a Deployment
    """

    # required defining data
    name: str 
    flow_id: UUID
    entrypoint: str
    path: str = None

    # workflow scheduling and parametrization
    parameters: dict = None
    parameter_openapi_schema: dict = None
    schedule: Schedule = None
    is_schedule_active: bool = True
    trigger: Trigger = None

    # metadata for bookkeeping
    version: str = None
    description: str = None
    tags: list = None

    # worker-specific fields
    work_pool_name: str = None
    work_queue_name: str = None
    infra_overrides: dict = None
    pull_steps: dict = None

    # agent-specific fields
    infrastructure_document_id: UUID = None
    storage_document_id: UUID = None
``` 

All methods for creating Prefect deployments are interfaces for populating this schema correctly. Let us look at each section in turn.

### Required data 

Deployments universally require both a `name` and a reference to an underlying `Flow`; these fields are self-explanatory. 
In almost all instances of deployment creation, users do not need to concern themselves with the `flow_id` as most interfaces will only need the flow's name. 
Note that the name is not required to be unique across all deployments but is required to be unique for a given flow ID.
As a consequence you will often see references to the deployment's unique identifying name `{FLOW_NAME}/{DEPLOYMENT_NAME}`. 
For example, triggering a run of a deployment from the Prefect CLI can be done via:

<div class="terminal">
```bash
prefect deployment run my-first-flow/my-first-deployment
```
</div>

The other two fields are less obvious:

- **`path`**: the _path_ can generally be interpreted as the runtime working directory for the flow. For example, if a deployment references a workflow defined within a Docker image, the `path` will be the absolute path to the parent directory where that workflow will run anytime the deployment is triggered. This interpretation is more subtle in the case of flows defined in remote filesystems.
- **`entrypoint`**: the _entrypoint_ of a deployment is a relative reference to a function decorated as a flow that exists on some filesystem. It is always specified relative to the `path`. Entrypoints use Python's standard path-to-object syntax (e.g., `path/to/file.py:function_name` or simply `path:object`).

As one should expect, the entrypoint should reference the same flow as the flow ID. 

Note that Prefect assumes that deployments reference flows defined _within Python files_. 
This implies that flows defined within interactive REPLs or notebooks are not currently candidates for Prefect deployments. They are still valid flows that will be monitored by the API anytime they are run, but you must bear the responsibility for triggering them.

!!! info "Deployments do not contain code definitions"
    Deployment metadata references code that exists in potentially diverse locations within your environment; this separation of concerns means that your flow code stays within your storage and execution infrastructure and never lives on the Prefect server or database.

    This is the heart of the Prefect hybrid model: there's a boundary between your proprietary assets and the Prefect backend (including [Prefect Cloud](/cloud/)). 

### Scheduling and parametrization

One of the primary motivations for creating deloyments of flows is to remotely _schedule_ and _trigger_ them. 
And just as flows can be called as functions with different input values, so can deployments be triggered or scheduled with different values through the use of parameters.

The five fields here capture the necessary metadata to perform such actions:

- **`schedule`**: a [schedule object](/concepts/schedules/); most of the convenient interfaces for creating deployments allow users to avoid creating this object themselves. For example, when [updating a deployment schedule in the UI](/concepts/schedules/#creating-schedules-through-the-ui) basic information such as a cron string or interval is all that's required.
- **`trigger`** (Cloud-only): triggers allow you to define event-based rules for running a deployment - for more information see [Automations](/concepts/automations/).
- **`parameter_openapi_schema`**: an [OpenAPI compatible schema](https://swagger.io/specification/) that defines the types and defaults for the flow's parameters; this is used by both the UI and the backend to expose options for creating manual runs as well as type validation.
- **`parameters`**: default values of flow parameters that this deployment will pass on each run. These can always be overwritten through a trigger or when manually creating a custom run.

!!! tip "Scheduling is asynchronous and decoupled" 
    Because deployments are nothing more than metadata, runs can be created at anytime
    As we can see, deployments are nothing more than metadata - they do not contain code, but they do reference it. scheduling then...
    note that pausing a schedule, updating your deployment, and other actions reset your auto scheduled runs.

### Versioning and bookkeeping

Versions, descriptions and tags are essentially omnipresent fields throughout Prefect that can be easy to overlook. However, putting some extra thought into how you use these fields can pay large dividends down the road.

- **`version`**: versions are always set by the client and can be any arbitrary string. We recommend tightly coupling this field on your deployments to your software development lifecycle. For example if you leverage `git` to manage code changes, use either a tag or commit hash in this field. If you don't set a value for the version, Prefect will compute a hash
- **`description`**: the description field of a deployment is a place to provide rich reference material for downstream stakeholders such as intended use and parameter documentation. Markdown formatting will be rendered in the Prefect UI, allowing for section headers, links, tables, and other formatting. If not provided explicitly, Prefect will use the docstring of your flow function as a default value.
- **`tags`**: tags are a mechanism for grouping related work together across a diverse set of objects. Tags set on a deployment will be inherited by that deployment's flow runs. These tags can then be used to filter what runs are displayed on the primary UI dashboard, allowing you to customize different views into your work. In addition, in Prefect Cloud you can easily find objects through searching by tag.

All of these bits of metadata can be leveraged to great effect by injecting them into the processes that Prefect is orchestrating. For example you can use both run ID and versions to organize files that you produce from your workflows, or by associating your flow run's tags with the metadata of a job it orchestrates. 
This metadata is available during execution through [Prefect runtime](/guides/runtime-context/).

!!! warning "Everything has a version"
    Deployments aren't the only entity in Prefect with a version attached; both flows and tasks also have versions that can be set through their respective decorators. These versions will be sent to the API anytime the flow or task is run.
    This allows you to debug your work by cross-referencing across 

### Workers and Work Pools

Advanced 

## Two approaches to deployments

There are two primary ways to categorize deployments

based on whether Prefect is aware of their infrastructure or not.

### Long-lived infrastructure

### Dynamically defined infrastructure

Mention paths and remote filesystems

!!! warning "Agents are no longer recommended"
    Blocks got too messy

## Conclusion

The end.

---
title: Prefect Explained
description: Learn core Prefect concepts.
tags:
    - getting started
    - explanation
    - overview
search:
  boost: 2
---

# Prefect Explained

Prefect is a Pythonic framework for orchestrating and observing workflows.

You install the [`prefect` package](/getting-started/installation/) to gain access to the Prefect Python SDK and CLI commands.
When you install Prefect you gain the ability to run a self-hosted server instance backed by SQLite or PostgreSQL.
Alternatively, you can use the [Prefect Cloud platform](/cloud/) that provides additional features and benefits useful for teams and production workloads.
Both a self-hosted server and Prefect Cloud provide a UI for visualizing and managing your workflows.

Here are the three major concepts you need to know to get started building production workflows with Prefect:

- Flows
- Deployments
- Work pools

## Flows

A Prefect flow is a Python function that defines a workflow and is decorated by `@flow`.
When this function runs, Prefect can track the state of the workflow and visualize it in the UI.
TK screenshot of a flow run.

## Work pools

A [work pool](/concepts/work-pools/) provides presets for infrastructure.
The work pool type could be a local subprocess, a Docker container, a Kubernetes cluster, or serverless cloud infrastructure such as AWS ECS, Google Cloud Run, VertexAI, or Azure Container Instances.
Prefect Cloud provides two special work pool categories: managed execution and push work pools on serverless cloud infrastructure( ECS, Google Cloud Run, or Azure Container Instances).

Work pools exist on the server.

## Deployments

Creating a [deployment](/concepts/deployments/) makes your flow schedulable. The deployment contains metadata needed to run the flow in production.

A deployment specifies a single entrypoint flow function, a deployment name, a work pool, and the location of the flow code to be pulled at runtime.

Flow code storage options include a Docker registry with the flow code baked into an image, git-based storage such as a GitHub repository, or cloud-provider storage such as AWS S3.

Deployments live on the server.

To run a deployment, you can create an ad-hoc run from the UI or CLI, add a programmatic schedule (such as cron), or trigger a run via an [automation](#automations).

## Other Prefect concepts you might find useful

- Tasks
- Workers
- Automations
- Blocks

### Tasks

Functions that are called within a flow can be decorated with `@task` to make them Prefect [tasks](/concepts/tasks/).
Turning a function into a task unlocks a number of Prefect features, including:

- logging
- automatic retries
- caching
- result persistence
- simple parallelization and concurrency

### Workers

Some work pool types require a worker to be running on your infrastructure in order to execute flows.
If you're using Prefect Cloud with a [Prefect managed work pool](/guides/managed-execution/) or a [serverless push work pool](/guides/deployment/push-work-pools/), you don't need to bother with workers.
A worker is a light-weight client-side process that runs on your infrastructure and polls a matching work pool for scheduled deployment runs.
The worker sets up the infrastructure and monitors the flow run.

Workers live on your infrastructure.

### Automations

Prefect Cloud provides automations to create event-driven workflows and notifications.
Automations contain a trigger event and a subsequent action.
Trigger types include events emitted by webhooks, flow runs states, and custom events defined in Python code.

Automations live on Prefect Cloud.

### Blocks

Prefect block types are Python classes that contain configuration and code.
They provide a pre-build web interface for creation and can be created and used in code.

Blocks live on the server.

## Next steps

You've been introduced to core Prefect concepts.

We encourage you to get hands-on practice with the [quickstart](/getting-started/quickstart/) or [tutorial](/tutorial/).
Or go deeper with the concepts in the [concepts docs](/concepts/).

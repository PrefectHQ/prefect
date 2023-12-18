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

You install the [`prefect` package](/getting-started/installation/) to gain access to the Prefect client that contains the Python SDK and CLI commands.

The Prefect client talks to a Prefect server - either the managed [Prefect Cloud platform](/cloud/) or a [self-hosted server instance](/guides/host/) backed by SQLite or PostgreSQL.

Prefect Cloud provides [free and paid plans](https://www.prefect.io/pricing) with additional features useful for teams and production workloads.

Both a self-hosted server and Prefect Cloud provide a UI for visualizing and managing your workflows.

![Cloud Dashboard](/img/ui/cloud-dashboard.png)

Here are the three major concepts you need to know to build a production workflow with Prefect:

- Flows
- Deployments
- Work pools

## Flows

A Prefect [flow](/concepts/flows/) is a Python function that defines a workflow and is decorated by `@flow`.
When this function runs, Prefect can track the state of the workflow and visualize it in the UI.

As shown below, when a flow is referenced as the entrypoint in a deployment it can be scheduled.

![Dependency graph in the UI](/img/ui/dependency-graph.png)

A flow is defined in Python code, stored in the location specified in a deployment, and represented on the server.

## Work pools

A [work pool](/concepts/work-pools/) provides presets for infrastructure.
The work pool type could be a local subprocess, a Docker container, a Kubernetes cluster, or serverless cloud infrastructure such as AWS ECS, Google Cloud Run, VertexAI, or Azure Container Instances.
Prefect Cloud provides two special work pool categories: Prefect managed work pools and push work pools on serverless cloud infrastructure (ECS, Google Cloud Run, or Azure Container Instances).

Work pools are created in the UI or CLI and live on the server.

## Deployments

Creating a [deployment](/concepts/deployments/) makes your flow schedulable.
The deployment contains metadata needed to run the flow in production.

A [deployment specifies](/guides/prefect-deploy/) a single entrypoint flow function, a deployment name, a work pool, and the location of the flow code to be pulled at runtime.

Flow code storage options include a Docker registry with the flow code baked into an image, git-based storage such as a GitHub repository, or cloud-provider storage such as AWS S3.

Deployments are created in Python code with `deploy`, via the CLI interactively with `prefect deploy`, or applied from a `prefect.yaml` file. Deployments live on the server.

To schedule a deployment run, you can create an ad-hoc run from the UI or CLI, add a programmatic schedule (such as cron), or create an [automation](#automations) so that the deployment runs in response to a trigger.

## Other Prefect concepts

The following Prefect-specific concepts are very commonly used, but are not essential to understand for all production workflows.

- Tasks
- Workers
- Automations
- Blocks

### Tasks

Python functions that are called within a flow can be decorated with `@task` to make them Prefect [tasks](/concepts/tasks/).
Turning a function into a task unlocks a number of Prefect features, including:

- logging
- automatic retries
- caching
- result persistence
- simple parallelization and concurrency

Tasks are defined in Python code and represented on the server.
Tasks currently must be called from a flow.

### Workers

Hybrid work pools require a worker to be running on your infrastructure in order to execute flows.
A worker is a light-weight client-side process that runs on your infrastructure and polls a matching work pool for scheduled deployment runs.
The worker sets up the infrastructure and monitors the flow run.

If you're using Prefect Cloud with a [Prefect managed work pool](/guides/managed-execution/) or a [push work pool](/guides/deployment/push-work-pools/), you don't need a worker.

Workers are started in the CLI and live on your infrastructure.

### Automations

Prefect Cloud provides [automations](/concepts/automations/) to create event-driven workflows and notifications.
Automations contain a trigger event and a subsequent action.
Trigger events might be emitted by webhooks, flow runs states, or custom events defined in Python code.
The absence of an event can also be set as a trigger.

![Crating an automation form UI](/img/ui/automations-trigger.png)

Automations are created in the UI and live on Prefect Cloud.

### Blocks

Prefect [block types](/concepts/blocks/) are Python classes that contain configuration and code.
They provide a pre-build web interface for creation and can be created and used in code.

![Create a block UI view](/img/ui/block-library.png)

Blocks can be created from in Python code or in the UI live on the server.

## Next steps

You've been introduced to core Prefect concepts.

We encourage you to get hands-on practice with the [quickstart](/getting-started/quickstart/) or [tutorial](/tutorial/).
Or go deeper with the concepts in the [concepts docs](/concepts/).

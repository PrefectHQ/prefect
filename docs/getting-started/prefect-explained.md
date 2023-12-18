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

To build a production workflow with Prefect you need a Python function that defines the workflow, a deployment that makes the workflow schedulable, and a work pool that specifies the infrastructure on which to run the workflow.

Let's see how Prefect helps you build production workflows by looking at the core concepts.

## Flows

Prefect determines what Python code to run by looking for a function decorated with `@flow` and specified as the entrypoint in a deployment.
When this function runs, Prefect will track the state, share logs, and visualize it in the UI.

![Dependency graph in the UI](/img/ui/dependency-graph.png)

A flow is defined in Python code, retrieved from the location specified in a deployment, and represented on the server.

## Work pools

Production workloads need somewhere to run - generally on a cloud provider.
A [work pool](/concepts/work-pools/) specifies the type of infrastructure and provides presets for workflows.
Prefect provides work pool types that give you the ability to run on your own local subprocess, a Docker container, a Kubernetes cluster, or serverless cloud infrastructure such as AWS ECS, Google Cloud Run, VertexAI, or Azure Container Instances.

Prefect Cloud also provides two work pools where we manage the submission of flow runs and automatically shut down the infrastructure when the workflow is completed.
Prefect managed work pools require no-cloud provider account.
Prefect's push work pools run in your serverless cloud infrastructure (ECS, Google Cloud Run, or Azure Container Instances), but can be auto-provisioned by Prefect and require minimal setup.

Work pools are created in the UI or CLI and live on the server.

## Deployments

Creating a [deployment](/concepts/deployments/) makes your flow schedulable.
The deployment contains all the metadata needed to run the workflow in production.

A [deployment specifies](/guides/prefect-deploy/) a single entrypoint flow function, a deployment name, a work pool, and the location of the flow code to be pulled at runtime.

Flow code storage options include a Docker registry with the flow code baked into an image, git-based storage such as a GitHub repository, or cloud-provider storage such as AWS S3.

Deployments are created in Python code with `deploy`, via the CLI interactively with `prefect deploy`, or applied from a `prefect.yaml` file. Deployments live on the server.

## Running workflows

To schedule a deployment run, you can create an ad-hoc run from the UI or CLI, add a programmatic schedule (such as cron), or create an [automation](#automations) so that the deployment runs in response to a trigger.

That's enough to get started with Prefect, but there are a few more concepts that are useful to know.

## Tasks

Most production workflows are composed of multiple steps.
Each step is commonly defined as its own Python function.

Python functions that are called within a flow can be decorated with `@task` to make them Prefect [tasks](/concepts/tasks/).
Turning a function into a task unlocks a number of Prefect benefits, including:

- logging
- automatic retries
- caching
- result persistence
- simple parallelization and concurrency

Tasks are defined in Python code and represented on the server.
Tasks currently must be called from a flow.

## Workers

Prefect's hybrid execution model allows you to run workflows on your own chosen infrastructure, either locally or on the cloud.
Use a Prefect [worker](/concepts/work-pools/#worker-overview) for hybrid work pools.
A worker is a light-weight client-side process that runs on your infrastructure and polls a matching work pool for scheduled deployment runs.
The worker sets up the infrastructure and monitors the flow run.

If you're using Prefect Cloud with a [Prefect managed work pool](/guides/managed-execution/) or a [push work pool](/guides/deployment/push-work-pools/), you don't need a worker.

Workers are started in the CLI and live on your infrastructure.

## Automations

You might want to run a workflow in response to an event, such as a webhook or a change in state.

Prefect Cloud provides [automations](/concepts/automations/) to create event-driven workflows.
Automations contain a trigger event and a subsequent action.
Trigger events might be emitted by webhooks, flow runs states, or custom events defined in Python code.
The absence of an event can also be set as a trigger.

Automations can also notify of you events via email, Slack, or other channels.

![Crating an automation form UI](/img/ui/automations-trigger.png)

Automations are created in the UI and live on Prefect Cloud.

## Blocks

Many workflows require shared configuration.
Prefect provides blocks to make it easy to share configuration and code across workflows.
Prefect [block types](/concepts/blocks/) are Python classes with a pre-built web interface that can be accessed in Python code.

![Create a block UI view](/img/ui/block-library.png)

Blocks can be created in Python code or in the UI live on the server.

## Prefect Cloud and a self-hosted server instance

The Prefect client talks to a Prefect server - either the managed [Prefect Cloud platform](/cloud/) or a [self-hosted server instance](/guides/host/) backed by SQLite or PostgreSQL.
You can interact with the server via the UI, CLI, or Python code.
See the [API docs](/api-ref/) for more details.

Prefect Cloud provides [free and paid plans](https://www.prefect.io/pricing) with additional features useful for teams and production workloads.

Both a self-hosted server and Prefect Cloud provide a UI for visualizing and managing your workflows.

## Next steps

You've seen how Prefect's core concepts help you build production workflows.

We encourage you to get hands-on practice with the [quickstart](/getting-started/quickstart/) or [tutorial](/tutorial/).
Or go deeper with the concepts in the [concepts docs](/concepts/).

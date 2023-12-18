---
title: Prefect Quickstart
description: Get started with Prefect, the easiest way to orchestrate and observe your data pipelines
tags:
    - getting started
    - quick start
    - overview
search:
  boost: 2
---

# Prefect Explained

Major concepts for a production workflow.

- Flows
- Deployments
- Work pools

## Flows

Python code

## Work pool

Presets for infrastructure

## Deployment

Makes your flow schedulable. Flows can be kicked o

## Other Prefect concepts you might find useful

- Tasks
- Workers
- Work queues
- Automations

### Tasks

Functions that are called within a flow can be decorated with `@task` to make them Prefect tasks.
Making a task unlocks a number of Prefect features, including:

- logging
- automatic retries
- caching
- result persistence
- simple parallelization and concurrency

### Workers

Some work pools require a worker to be running on your infrastructure in order to execute flows.
If you're using Prefect Cloud with a managed execution work pool or a push work pool (ECS, Google Cloud Run, or Azure Container Instances) you don't need to bother with workers.
A worker is a light-weight process that runs on your infrastructure and polls a matching work pool for scheduled deployment runs.
The worker sets up the infrastructure and monitors the flow run.

### Work queues

Work queues can manage priority and concurrency on your infrastructure.
A work pool contains a work queue by default.
You can add multiple work queues. TK link

### Automations

Prefect Cloud provides automations that allow actions to be taken in response to an event or a lack of an event.
Automations contain a trigger and an action.
Automations can be used to build event-driven workflows.
You can set up alerts via automation notifications.

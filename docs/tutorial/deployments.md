---
description: Learn how Prefect flow deployments enable configuring flows for scheduled and remote execution.
tags:
    - orchestration
    - flow runs
    - deployments
    - schedules
    - triggers
    - tutorial
search:
  boost: 2
---
# Deploying Flows

## Why Deployments?

One of the most common reasons to use a tool like Prefect is [scheduling](/concepts/schedules) or [event-based triggering](/concepts/automations/). Up to this point, we’ve demonstrated running Prefect flows as scripts, but this means *you* have been the one triggering flow runs. You can certainly continue to trigger your workflows in this way and use Prefect as a monitoring layer for other schedulers or systems, but you will miss out on many of the other benefits and features that Prefect offers.

A deployed flow enhances a normal flow in many ways:

- a deployment has its own API for triggering work, pausing work, or customizing parameters
- you can remotely configure schedules and automation rules for your deployments
- you can even use Prefect to dynamically provision infrastructure using [workers](/tutorials/workers/)

## What is a Deployment?

Deploying a flow is the act of specifying when, where, and how it will run. This information is encapsulated and sent to Prefect as a [Deployment](/concepts/deployments/) which contains the crucial metadata needed for remote orchestration. Deployments elevate workflows from functions that you call manually to API-managed entities.

Attributes of a deployment include (but are not limited to):

- __Flow entrypoint__: path to your flow function 
- __Schedule__ or __Trigger__: optional schedule or triggering rule for this deployment
- __Tags__: optional text labels for organizing your deployments



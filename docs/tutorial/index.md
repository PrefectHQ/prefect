---
icon: material/graph-outline
description: Learn the basics of creating and running Prefect flows and tasks.
tags:
    - tutorial
    - getting started
    - basics
    - tasks
    - flows
    - subflows
    - deployments
    - workers
    - work pools
search:
  boost: 2
---
# Tutorial Overview

This tutorial provides a step by step walk-through of Prefect core concepts and instructions on how to use them.

By the end of this tutorial you will have:

1. [Created a Flow](/tutorial/flows/)
2. [Added Tasks to It](/tutorial/tasks/)
3. [Created a Work Pool](/tutorial/deployments/)
4. [Deployed a Worker](/tutorial/deployments/)
5. [Deployed the Flow](/tutorial/deployments/)
6. [Run the Flow on the Worker](/tutorial/deployments/)

If you're looking for examples of more advanced operations (like [deploying on Kubernetes](/guides/deployment/helm-worker/)), check out Prefect's [guides](/guides/).

## Prerequisites

1. Before you start, make sure you have Python installed, then install Prefect: `pip install -U prefect`
      1. See the [install guide](/getting-started/installation/) for more detailed instructions.

2. Create a GitHub repository for your tutorial, let's call it `prefect-tutorial`.

3. This tutorial requires a Prefect Server instance, so sign up for a forever free [Prefect Cloud Account](https://app.prefect.cloud/) or, alternatively, self-host a [Prefect Server](/host/).

## What is Prefect?

Prefect orchestrates workflows — it simplifies the creation, scheduling, and monitoring of complex data pipelines. With Prefect, you define workflows as Python code and let it handle the rest.

Prefect also provides error handling, retry mechanisms, and a user-friendly dashboard for monitoring. It's the easiest way to transform any Python function into a unit of work that can be observed and orchestrated.

Just bring your Python code, sprinkle in a few decorators, and go!

### Reference Material
If you've never used Prefect before, check out the [core concepts docs](/concepts/).
Many of these concepts will be introduced in the tutorial, however, the concept docs provide a more comprehensive overview of each concept.

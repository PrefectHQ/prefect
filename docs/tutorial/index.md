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
search:
  boost: 2
---
# Tutorial Overview

This tutorial provides a step by step walk-through of Prefect core concepts and instructions on how to use them.

Specific examples of how to perform more advanced operations can be found in our [guides](/guides/).

## Prerequisites

1. Before you start, install Prefect: `pip install -U prefect`
      1. See the [install guide](/getting-started/installation/) for more detailed instructions.

2. Create a github repository for your tutorial, let's call it `prefect-tutorial`

3. This tutorial requires a Prefect API so sign up for a forever free [Prefect Cloud Account](https://app.prefect.cloud/), use a local Prefect API or a self hosted [Prefect Server](/host/).

## What is Prefect?

Prefect automates and orchestrates data workflows - it simplifies the creation, scheduling, and monitoring of complex pipelines. With Prefect, you define workflows as Python code, specify task dependencies, and let it handle the execution order.

Prefect also provides error handling, retry mechanisms, and a user-friendly dashboard for monitoring. It's the easiest way to transform any Python function into a unit of work that can be observed and orchestrated.

Just bring your Python code, sprinkle in a few decorators, and go!

By the end of this tutorial you will have:

1. [Created a Flow](/tutorial/flows/)
2. [Added Tasks to it](/tutorial/tasks/)
3. [Created a Work Pool](/tutorial/deployments/)
4. [Deployed a Worker](/tutorial/deployments/)
5. [Deployed the Flow](/tutorial/deploying/)
6. [Run the flow on our worker!](/tutorial/deployments/)


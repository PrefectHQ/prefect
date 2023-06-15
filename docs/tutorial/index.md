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

This tutorial provides a step by step walk through of Prefect core concepts and instructions on how to use them. For specific examples of how to perform more advanced tasks, check out our [guides](/guides/).

### Prerequisites

Before you start, install Prefect:

<div class="terminal">
```bash
pip install -U prefect
```
</div>

See the [install guide](/getting-started/installation/) for more detailed instructions.

Create a github repository for your tutorial, let's call it `prefect-tutorial`

This tutorial requires a Prefect API so sign up for a forever free [Prefect Cloud Account](https://app.prefect.cloud/), use a local Prefect API or a self hosted Prefect Server.

## What is Prefect?

Prefect automates and orchestrates data workflows - it simplifies the creation, scheduling, and monitoring of complex pipelines. With Prefect, you define workflows as Python code, specify task dependencies, and let it handle the execution order. Prefect also provides error handling, retry mechanisms, and a user-friendly dashboard for monitoring. t's the easiest way to transform any Python function into a unit of work that can be observed and orchestrated. Just bring your Python code, sprinkle in a few decorators, and go!

1. By the end of this tutorial we will have:
        1. [Created a Flow](/tutorial/first-steps/)
        2. [Added Tasks to it](/tutorial/tasks/)
        3. [Created a Work Pool](/tutorial/execution/)
        4. [Deployed a Worker](/tutorial/execution/)
        5. [Deployed the Flow](/tutorial/deployments/)
        6. [Run the flow on our worker!](/tutorial/deployments/)


### Reference Material
If you've never used Prefect before, let's start by exploring the core concepts:

- [Our Concepts](/concepts/) contain deep dives into Prefect components.
- [Guides](/guides/) provide step by step recipes for common Prefect operations including:
    - [Deploying on Kubernetes](/guides/deployment/helm-worker/)
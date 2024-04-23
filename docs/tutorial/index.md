---
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
# Tutorial: Master workflow automations

This tutorial helps you get started with Prefect and become familiar with developing, deploying, and managing Prefect workflows.

After you build your deployment, you can read other [guides](/guides) to learn how to integrate other services and add more features to your workflows.

## Before you begin

1. Install [Python](https://www.python.org/downloads/).
1. Install Prefect:
    ```bash
    pip install -U prefect
    ```

    For more detailed instructions, see [Installation](/getting-started/installation/).

1. Connect to [Prefect Cloud](https://app.prefect.cloud). You can sign up for a forever free [Prefect Cloud account](/cloud/) or accept your organization's invite to join their Prefect Cloud account. Alternatively, you can use Prefect Cloud and self-host a [Prefect server instance](/host/). If you choose this option, start a local Prefect server instance by running the `prefect server start` command.

1. Create a new account or sign in at [https://app.prefect.cloud/](https://app.prefect.cloud/).
1. Use the `prefect cloud login` CLI command to [authenticate to Prefect Cloud](/cloud/users/api-keys/) from your environment.

    ```bash
    prefect cloud login
    ```

    1. Choose **Log in with a web browser**
    1. Click **Authorize** in the browser window that opens.

## Get started!

Let's begin by learning how to [create your first Prefect flow](/tutorial/flows/).

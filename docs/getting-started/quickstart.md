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

# Quickstart

Prefect is an orchestration and observability platform that empowers developers to build and scale resilient code quickly, turning their scheduled jobs into resilient, recurring workflows.

In this quickstart, you'll see how you can schedule your code, visualize workflows, and monitor your entire system health with Prefect.

Let's get started!

## Setup

Say you have some Python code that runs locally.
The script below fetches statistics about the [main Prefect GitHub repository](https://github.com/PrefectHQ/prefect).

```python
import httpx

def get_repo_info():
    url = "https://api.github.com/repos/PrefectHQ/prefect"
    response = httpx.get(url)
    repo = response.json()
    print("PrefectHQ/prefect repository statistics 🤓:")
    print(f"Stars 🌠 : {repo['stargazers_count']}")

if __name__ == "__main__":
    get_repo_info()
```

How can you make this script repeatable, schedulable, observable, resilient, and capable of running anywhere?

## Step 1: Install Prefect

```bash
pip install -U "prefect"
```

See the [install guide](/getting-started/installation/) for more detailed installation instructions, if needed.

## Step 2: Connect to Prefect's API

Much of Prefect's functionality is backed by an API.
If [self-hosting](/guides/host/), you'll need to start the Prefect webserver and related services yourself, or if you'd rather use a hosted version of the API with a bunch of additional features such as automations, collaborators, and error summaries powered by Marvin AI, sign up for a forever free [Prefect Cloud account](/cloud/).

=== "Cloud"

    1. Sign in with an existing account or create a new account at [https://app.prefect.cloud/](https://app.prefect.cloud/).
    2. If setting up a new account, [create a workspace](/cloud/workspaces/#create-a-workspace) for your account.
    3. Use the `prefect cloud login` CLI command to [log into Prefect Cloud](/cloud/users/api-keys) from your environment.

    <div class="terminal">

    ```bash
    prefect cloud login
    ```

    </div>

=== "Self-hosted"

    1. Open a new terminal window.
    2. Start a local Prefect server instance in your virtual environment.

    <div class="terminal">

    ```bash
    prefect server start
    ``` 

    </div>

## Step 3: Write a flow

The fastest way to get started with Prefect is to add a `@flow` decorator to any Python function and call its `serve` method to create a deployment.
[Flows](/concepts/flows/) are the core observable, deployable units in Prefect and are the primary entrypoint to orchestrated work.
[Deployments](/concepts/deployments/) elevate flows to remotely configurable entities that have their own API, as we will see shortly.

```python hl_lines="2 5"
import httpx
from prefect import flow


@flow
def get_repo_info():
    url = "https://api.github.com/repos/PrefectHQ/prefect"
    response = httpx.get(url)
    repo = response.json()
    print("PrefectHQ/prefect repository statistics 🤓:")
    print(f"Stars 🌠 : {repo['stargazers_count']}")

if __name__ == "__main__":
    # create your first deployment
    repo_info.serve(name="my-first-deployment")
```

## Step 4: Create a deployment

When we run this script, Prefect will automatically create a deployment that you can interact with via the UI and API.
The script will stay running so that it can listen for scheduled or triggered runs of this flow.
Once a run is found, it will be executed within a subprocess.

<div class="terminal">

```bash
python my_flow.py
```

</div>

You should see a link directing you to the deployment page that you can use to begin interacting with your newly created deployment!

For example, you can trigger a run of this deployment by either clicking the "Run" button in the top right of the deployment page in the UI, or by running the following CLI command in your terminal:

<div class="terminal">

```bash
prefect deployment run 'Repo Info/my-first-deployment'  
```

</div>

This command creates a new run for this deployment that is then picked up by the process running `repo_info.serve`.

![Flow run timeline](/img/ui/flow-run-diagram.png)

You should see logs from the flow run in the CLI and the UI that look similar to this:

<div class="terminal">

```bash
09:44:37.947 | INFO    | Flow run 'piquant-sawfly' - Downloading flow code from storage at '/my_path'
09:44:39.385 | INFO    | Flow run 'piquant-sawfly' - Stars 🌠 : 12736
09:44:40.527 | INFO    | Flow run 'piquant-sawfly' - Finished in state Completed('All states completed.')
09:44:43.018 | INFO    | prefect.flow_runs.runner - Process 9867 exited cleanly.
```

</div>

!!! tip "Getting started tips"
    - You can call your flow function directly like any other Python function and its execution will be registered and monitored with the Prefect API and visible in the UI
    - Elevating a flow to a [deployment](/concepts/deployments/) exposes a Prefect-backed API for remotely managing and configuring your workflow with things such as [scheduling rules](/concepts/schedules/), [trigger rules](/cloud/automations/), and cancellation
    - Deployments require that flow functions are defined in static files, and therefore calling the `serve` method on an interactively defined flow will raise an error

## Step 5: Add a schedule

We can add a [schedule](/concepts/schedules/) to our deployment.  We could do this in one of two ways:

- use the Prefect UI to create and attach the schedule
- specify the schedule in code

It's generally best practice to keep your configuration defined within code, so let's update the script above to specify a schedule:

```python
if __name__ == "__main__":
    # create your first scheduled deployment
    repo_info.serve(name="my-first-deployment", cron="0 0 * * *")
```

Once run, this will create a cron schedule for our deployment that instructs it to run at noon every day. When you stop this script, Prefect will automatically pause your deployment's schedule for you.

![Deployment schedule](/img/ui/deployment-cron-schedule.png)

## Next steps

To learn how, try our [tutorial](/tutorial) and [guides](/guides), or go deeper with [concepts](/concepts).

!!! tip "Need help?"
    Get your questions answered by a Prefect Product Advocate! [Book a Meeting](https://calendly.com/prefect-experts/prefect-product-advocates?utm_campaign=prefect_docs_cloud&utm_content=prefect_docs&utm_medium=docs&utm_source=docs)

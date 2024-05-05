---
title: Prefect Quickstart
description: Get started with Prefect, the easiest way to orchestrate and observe your data pipelines
tags:
    - getting started
    - quickstart
    - overview
search:
  boost: 2
---

# Quickstart

Prefect is a workflow orchestration platform for building data pipelines, background jobs, LLM Chains, and more. With Prefect, you can elevate a Python script into a scheduled, observable, resilient, remotely execuateble workflow in a few minutes. Let's get started!

## Setup

Here's a basic script that fetches statistics about the [main Prefect GitHub repository](https://github.com/PrefectHQ/prefect).

```python title="my_gh_workflow.py"
import httpx   # an HTTP client library

def get_repo_info(repo_owner: str, repo_name: str):
    """Get info about a repo"""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
    api_response = httpx.get(url)
    api_response.raise_for_status()
    repo_info = api_response.json()
    return repo_info

def get_contributors(repo_info: dict):
    """Get contributors for a repo"""
    contributors_url = repo_info["contributors_url"]
    response = httpx.get(contributors_url)
    response.raise_for_status()
    contributors = response.json()
    return contributors

def repo_info(repo_owner: str = "PrefectHQ", repo_name: str = "prefect"):
    """Given a repo, logs the number of stargazers and contributors"""
    repo_info = get_repo_info(repo_owner, repo_name)
    print(f"Stars 🌠 : {repo_info['stargazers_count']}")

    contributors = get_contributors(repo_info)
    print(f"Number of contributors 👷: {len(contributors)}")

if __name__ == "__main__":
    repo_info()
```

Copy this script into a file named `my_gh_workflow.py`. Run it locally to ensure your Python environment works. Let's make this script schedulable, observable, resilient, and capable of running anywhere.

## Step 1: Install Prefect

Make sure you have Python installed in a virtual environment. Then install Prefect:

```bash
pip install -U prefect
```

See the [install guide](/getting-started/installation/) for more detailed installation instructions.

## Step 2: Connect to Prefect's API

Much of Prefect's functionality is backed by an API. You can [host Prefect server](/guides/host/) yourself if you'd like, but the easiest way to get started is to use the API hosted by Prefect Cloud:

1. Create a forever-free Prefect Cloud account or sign in at [https://app.prefect.cloud/](https://app.prefect.cloud/)
1. Use the `prefect cloud login` CLI command to log in to Prefect Cloud from your development environment

<div class="terminal">

```bash
prefect cloud login
```

</div>

Choose **Log in with a web browser** and click the **Authorize** button in the browser window that opens.
Your CLI is now authenticated with your Prefect Cloud account through a locally-stored API key that expires in 30 days.

If you have any issues with browser-based authentication, see the [Prefect Cloud docs](/cloud/users/api-keys/) to learn how to authenticate with a manually created API key.

## Step 3: Turn your script into a Prefect flow

In Prefect, workflows are made up of flows and tasks. [Flows](/concepts/flows/) are the primary schedulable, deployable units in Prefect and are the primary entrypoint to orchestrated work. Flows can contain tasks, which are steps within the workflow. Tasks are the smallest unit of observed and orchestrated work in Prefect.

The fastest way to get started with Prefect is to add a `@flow` decorator to the Python function where your script starts and `@task` decorators to other functions that are called:

```python hl_lines="2 5" title="my_gh_workflow.py"
import httpx   # an HTTP client library and dependency of Prefect
from prefect import flow, task

@task(retries=2)
def get_repo_info(repo_owner: str, repo_name: str):
    """Get info about a repo - will retry twice after failing"""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
    api_response = httpx.get(url)
    api_response.raise_for_status()
    repo_info = api_response.json()
    return repo_info

@task
def get_contributors(repo_info: dict):
    """Get contributors for a repo"""
    contributors_url = repo_info["contributors_url"]
    response = httpx.get(contributors_url)
    response.raise_for_status()
    contributors = response.json()
    return contributors

@flow(log_prints=True)
def repo_info(repo_owner: str = "PrefectHQ", repo_name: str = "prefect"):
    """Given a repo, logs the number of stargazers and contributors"""
    repo_info = get_repo_info(repo_owner, repo_name)
    print(f"Stars 🌠 : {repo_info['stargazers_count']}")

    contributors = get_contributors(repo_info)
    print(f"Number of contributors 👷: {len(contributors)}")

if __name__ == "__main__":
    repo_info()
```

Note that we added a `log_prints=True` argument to the `@flow` decorator so that `print` statements within the flow-decorated function will be logged. Now, lets run it again:

<div class="terminal">

```bash
python my_gh_workflow.py
```

</div>

Prefect will automatically track the state of the flow run and log the output where we can see it in the UI and CLI.

<div class="terminal">

```bash
14:28:31.099 | INFO    | prefect.engine - Created flow run 'energetic-panther' for flow 'repo-info'
14:28:31.100 | INFO    | Flow run 'energetic-panther' - View at https://app.prefect.cloud/account/123/workspace/abc/flow-runs/flow-run/xyz
14:28:32.178 | INFO    | Flow run 'energetic-panther' - Created task run 'get_repo_info-0' for task 'get_repo_info'
14:28:32.179 | INFO    | Flow run 'energetic-panther' - Executing 'get_repo_info-0' immediately...
14:28:32.584 | INFO    | Task run 'get_repo_info-0' - Finished in state Completed()
14:28:32.599 | INFO    | Flow run 'energetic-panther' - Stars 🌠 : 13609
14:28:32.682 | INFO    | Flow run 'energetic-panther' - Created task run 'get_contributors-0' for task 'get_contributors'
14:28:32.682 | INFO    | Flow run 'energetic-panther' - Executing 'get_contributors-0' immediately...
14:28:33.118 | INFO    | Task run 'get_contributors-0' - Finished in state Completed()
14:28:33.134 | INFO    | Flow run 'energetic-panther' - Number of contributors 👷: 30
14:28:33.255 | INFO    | Flow run 'energetic-panther' - Finished in state Completed('All states completed.')
```

</div>

You should see similar output in your terminal, with your own randomly generated flow run name and your own Prefect Cloud account URL.

## Step 4: Choose a remote infrastructure location

Let's get this workflow running on infrastructure other than your local machine!
Prefect refers to infrastructure that can run worflows as [work pools](/concepts/work-pools/). 
Prefect can orchestrate workflows that run remotely on many [types of infrastructure](/work-pools/#work-pool-types), but here we'll use a [Prefect Managed work pool](/guides/managed-execution/) so that Prefect can run this flow for us.
We can create a work pool in the UI or from the CLI.
Let's use the CLI:

<div class="terminal">

```bash
prefect work-pool create my-managed-pool --type prefect:managed
```

</div>

You should see a message in the CLI that your work pool was created.
Feel free to check out your new work pool on the **Work Pools** page in the UI.

## Step 5: Deploy your workflow

We now have a flow and a work pool where we can run it. Let's package both of these things, into a [deployment](/concepts/deployments/) so that we can run our workflow remotely.

Deployments elevate flows to remotely configurable entities that have their own API.

Let's make a script to build a deployment with the name *my-first-deployment* and set it to run on a schedule.

```python hl_lines="15-22" title="create_deployment.py"
from prefect import flow

if __name__ == "__main__":
    flow.from_source(
        source="https://github.com/discdiver/demos.git",
        entrypoint="my_gh_workflow.py:repo_info",
    ).deploy(
        name="my-first-deployment",
        work_pool_name="my-managed-pool"
    )
```

Run the script to deploy this flow to `my-managed-pool` in Prefect Cloud.

<div class="terminal">

```bash
python create_deployment.py
```

</div>

You should see a message that your deployment was created, similar to the one below.

<div class="terminal">
```
Successfully created/updated all deployments!
______________________________________________________
|                    Deployments                     |  
______________________________________________________
|    Name                       |  Status  | Details |
______________________________________________________
| repo-info/my-first-deployment | applied  |         |
______________________________________________________

To schedule a run for this deployment, use the following command:

       $ prefect deployment run 'repo-info/my-first-deployment'

You can also run your flow via the Prefect UI: <https://app.prefect.cloud/account/abc/workspace/123/deployments/deployment/xyz>

```
</div>

Head to the **Deployments** page of the UI to check it out.

!!! note "Code storage options"
    You can store your flow code in nearly any location.
    You just need to tell Prefect where to find it.
    In this example, we use a GitHub repository, but you could bake your code into a Docker image or store it in cloud provider storage.
    Read more in [this guide](/guides/prefect-deploy/#creating-work-pool-based-deployments).

You can trigger a manual run of this deployment by either clicking the **Run** button in the top right of the deployment page in the UI, or by running the following CLI command in your terminal:

<div class="terminal">

```bash
prefect deployment run 'repo-info/my-first-deployment'
```

</div>

The deployment is configured to run on a Prefect Managed work pool, so Prefect will automatically spin up the infrastructure to run this flow.
It may take a minute to set up the Docker image in which the flow will run.

After a minute or so, you should see the flow run graph and logs on the Flow Run page in the UI.

![Managed flow run graph and logs](/img/ui/qs-flow-run.png)

## Next steps

You've seen how to move from a Python script to a scheduled, observable, remotely orchestrated workflow with Prefect.

To learn how to run flows on your own infrastructure, customize the Docker image where your flow runs, and gain more orchestration and observation benefits check out the [tutorial](/tutorial/).

!!! tip "Need help?"
    Get your questions answered by a Prefect Product Advocate! [Book a meeting](https://calendly.com/prefect-experts/prefect-product-advocates?utm_campaign=prefect_docs_cloud&utm_content=prefect_docs&utm_medium=docs&utm_source=docs)

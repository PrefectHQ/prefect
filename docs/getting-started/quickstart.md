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

Prefect is an orchestration and observability platform that empowers developers to build and scale resilient code quickly, turning their scheduled jobs into resilient, recurring workflows.

In this quickstart, you'll see how you can schedule your code on remote infrastructure and observe the state of your workflows.
With Prefect, you can go from a Python script to a production-ready workflow that runs remotely in minutes.

Let's get started!

## Setup

Here's a basic script so we have something to work with.
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

How can we make this script schedulable, observable, resilient, and capable of running anywhere?

## Step 1: Install Prefect

```bash
pip install -U "prefect"
```

See the [install guide](/getting-started/installation/) for more detailed installation instructions, if needed.

## Step 2: Connect to Prefect's API

Much of Prefect's functionality is backed by an API.
Sign up for a forever free [Prefect Cloud account](/cloud/) or accept your organization's invite to join their Prefect Cloud account.

1. Create a new account or sign in at [https://app.prefect.cloud/](https://app.prefect.cloud/).
1. Use the `prefect cloud login` CLI command to [log in to Prefect Cloud](/cloud/users/api-keys) from your environment.

<div class="terminal">

```bash
prefect cloud login
```

</div>

Choose **Log in with a web browser** and click **Authorize** button in the browser window that opens.

!!! note "Self-hosted Prefect server instance"
    If you would like to host a Prefect server instance on your own infrastructure, see the [tutorial](/tutorial/) and select the "Self-hosted" tab.
    Note that you will need to both host your own server and run your flows on your own infrastructure.

## Step 3: Turn your function into a Prefect flow

The fastest way to get started with Prefect is to add a `@flow` decorator to your Python function.
[Flows](/concepts/flows/) are the core observable, deployable units in Prefect and are the primary entrypoint to orchestrated work.

```python hl_lines="2 5" title="my_workflow.py"
import httpx
from prefect import flow


@flow(log_prints=True)
def get_repo_info():
    url = "https://api.github.com/repos/PrefectHQ/prefect"
    response = httpx.get(url)
    repo = response.json()
    print("PrefectHQ/prefect repository statistics 🤓:")
    print(f"Stars 🌠 : {repo['stargazers_count']}")

if __name__ == "__main__":
    get_repo_info()
```

Note that we added a `log_prints=True` argument to the `@flow` decorator so that `print` statements within the flow-decorated function will be logged.

<div class="terminal">

```bash
python my_workflow.py
```

</div>

Now when we run this script, Prefect will automatically track the state of the flow run and log the output where we can see it in the UI or CLI.

<div class="terminal">

```bash
15:16:34.705 | INFO    | prefect.engine - Created flow run 'frisky-reindeer' for flow 'get-repo-info'
15:16:34.706 | INFO    | Flow run 'frisky-reindeer' - View at https://app.prefect.cloud/account/abc/flow-runs/flow-run/123
15:16:35.053 | INFO    | Flow run 'frisky-reindeer' - PrefectHQ/prefect repository statistics 🤓:
15:16:35.055 | INFO    | Flow run 'frisky-reindeer' - Stars 🌠 : 13593
15:16:35.744 | INFO    | Flow run 'frisky-reindeer' - Finished in state Completed()
```

</div>

You should see similar output in your terminal, with your own randomly generated flow run name and your own Prefect Cloud account URL.

## Step 4: Choose a remote infrastructure location

Let's get this workflow running on infrastructure other than your local machine!
We can tell Prefect where we want to run our workflow by creating a [work pool](/concepts/work-pools/).

Because we're using Prefect Cloud, we have access to Prefect Managed work pools that provides hosted infrastructure for running our flows.

Let's create a [Prefect Managed work pool](/guides/managed-execution/) so that Prefect can run our flows for us.
We can create a work pool in the UI or from the CLI.
Let's use the CLI:

<div class="terminal">

```bash
prefect work-pool create my-managed-pool --type prefect:managed
```

</div>

You should see a message in the CLI that your work pool was created.
Feel free to check out your new work pool on the **Work Pools** page in the UI.

## Step 4: Make your code schedulable

We have a flow function and we have a work pool where we can run our flow remotely.
Let's package both of these things, along with the location for where to find our flow code, into a [deployment](/concepts/deployments/) so that we can schedule our workflow to run remotely.

Deployments elevate flows to remotely configurable entities that have their own API.

Let's update our script to create a deployment.

```python title="my_workflow.py"
...

if __name__ == "__main__":
    flow.from_source(
        source="https://github.com/discdiver/demo.git",
        entrypoint="my_workflow.py:get_repo_info",
    ).deploy(
        name="my-first-deployment",
        work_pool_name="my-managed-pool",
        cron="0 1 * * *",
    )
```

Run the script to create the deployment on the Prefect Cloud server.
Note that the `cron` argument will schedule the deployment to run at 1am every day.

<div class="terminal">

```bash
python my_workflow.py
```

</div>

You should see a message in the CLI that your deployment was created similar to this one.

<div class="terminal">

```bash
Successfully created/updated all deployments!

                       Deployments                       
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┓
┃ Name                              ┃ Status  ┃ Details ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━┩
│ get-repo-info/my-first-deployment  │ applied │         │
└───────────────────────────────────┴─────────┴─────────┘

To schedule a run for this deployment, use the following command:

        prefect deployment run 'get-repo-info/my-first-deployment'

You can also run your flow via the Prefect UI: <https://app.prefect.cloud/account/abc/workspace/123/deployments/deployment/xyz>

```

</div>

Head to the **Deployments* page of the UI to check it out.

!!! note "Code storage options"
    You can store your flow code in nearly any location.
    You just need to tell Prefect where to find it.
    In this example, we use a GitHub repository, but you could bake your code into a Docker image or store it in cloud provider storage.
    Read more [here]/guides/prefect-deploy/#creating-work-pool-based-deployments).

!!! caution "Push your code to GitHub"
    In the example above, we use an existing GitHub repository.
    If you make changes to the flow code, you will need to push those changes to your own GitHub account and update the `source` argument to point to your repository.

You can trigger a run of this deployment by either clicking the **Run** button in the top right of the deployment page in the UI, or by running the following CLI command in your terminal:

<div class="terminal">

```bash
prefect deployment run 'get_repo_info/my-first-deployment'  
```

</div>

The deployment is configured to run on a Prefect Managed work pool, so Prefect will automatically spin up the infrastructure to run this flow.
It may take a minute to set up the Docker image in which the flow will run.

After a minute or so, you should see logs.

![Managed flow run with metrics](/img/ui/deployment-managed.png)

Click the **Remove** button in the top right of the **Deployment** page so that the workflow is no longer scheduled to run once a day.

## Next steps

You've seen how to move from a Python script to a scheduled, observable, remotely orchestrated workflow with Prefect.

To learn how to run flows on your own infrastructure or see how to customize the Docker image where your flow runs, check out the [tutorial](/tutorial/).

The tutorial also shows you how to gain lots of Prefect orchestration benefits such as:

- automatic retries
- caching
- simple async
- result persistence
- long-running deployment servers
<!-- add event-driven workflows when added to tutorial -->

!!! tip "Need help?"
    Get your questions answered by a Prefect Product Advocate! [Book a Meeting](https://calendly.com/prefect-experts/prefect-product-advocates?utm_campaign=prefect_docs_cloud&utm_content=prefect_docs&utm_medium=docs&utm_source=docs)

Happy orchestrating!

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

### Step 1: Install Prefect

<div class="terminal">
```bash
pip install -U prefect
```
</div>

See the [install guide](/getting-started/installation/) for more detailed installation instructions.

### Step 2: Connect to Prefect's API

Much of Prefect's functionality is backed by an API - if [self-hosting](/guides/host/), you'll need to start the Prefect webserver and related services yourself, or if you'd rather use a hosted version of the API you can sign up for a forever free [Prefect Cloud account](/cloud/).


=== "Self-hosted"

    ```bash
    prefect server start
    ```

=== "Cloud"

    1. Sign in with an existing account or create a new account at [https://app.prefect.cloud/](https://app.prefect.cloud/).
    2. If setting up a new account, [create a workspace](/cloud/workspaces/#create-a-workspace) for your account.
    3. Use the `prefect cloud login` Prefect CLI command to [log into Prefect Cloud](/cloud/users/api-keys) from your environment.

        <div class="terminal">
        ```bash
        prefect cloud login
        ```
        </div>



### Step 3: Create a flow
**The fastest way to get started with Prefect is to add a `@flow` decorator to any python function**.

!!! tip "Rules of Thumb"
    - At a minimum, you need to define at least one [flow](/tutorial/flows/) function.
    - Your flows can be segmented by introducing [task](/tutorial/tasks/) (`@task`) functions, which can be invoked from within these flows.
    - A [task](/concepts/tasks/) represents a discrete unit of Python code, whereas flows are more akin to parent functions accommodating a broad range of workflow logic.
    - [Flows](/concepts/flows) can be called inside of other flows (we call these [subflows](/concepts/flows/#composing-flows)) but a task **cannot** be run inside of another task or from outside the context of a flow.

Here is an example flow named `Repo Info` that contains two tasks:
```python
# my_flow.py
import httpx
from prefect import flow, task

@task(retries=2)
def get_repo_info(repo_owner: str, repo_name: str):
    """ Get info about a repo - will retry twice after failing """
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
    api_response = httpx.get(url)
    api_response.raise_for_status()
    repo_info = api_response.json()
    return repo_info


@task
def get_contributors(repo_info: dict):
    contributors_url = repo_info["contributors_url"]
    response = httpx.get(contributors_url)
    response.raise_for_status()
    contributors = response.json()
    return contributors

@flow(name="Repo Info", log_prints=True)  
def repo_info(
    repo_owner: str = "PrefectHQ", repo_name: str = "prefect"
):
    # call our `get_repo_info` task
    repo_info = get_repo_info(repo_owner, repo_name)
    print(f"Stars 🌠 : {repo_info['stargazers_count']}")

    # call our `get_contributors` task, 
    # passing in the upstream result
    contributors = get_contributors(repo_info)
    print(
        f"Number of contributors 👷: {len(contributors)}"
    )


if __name__ == "__main__":
    # Call a flow function for a local flow run!
    repo_info()
```

### Step 4: Run your flow locally
Call any function that you've decorated with a `@flow` decorator to see a local instance of a flow run.

<div class="terminal">
```bash
python my_flow.py
```
</div> 

<div class="terminal">
```bash
18:21:40.235 | INFO    | prefect.engine - Created flow run 'fine-gorilla' for flow 'Repo Info'
18:21:40.237 | INFO    | Flow run 'fine-gorilla' - View at https://app.prefect.cloud/account/0ff44498-d380-4d7b-bd68-9b52da03823f/workspace/c859e5b6-1539-4c77-81e0-444c2ddcaafe/flow-runs/flow-run/c5a85193-69ea-4577-aa0e-e11adbf1f659
18:21:40.837 | INFO    | Flow run 'fine-gorilla' - Created task run 'get_repo_info-0' for task 'get_repo_info'
18:21:40.838 | INFO    | Flow run 'fine-gorilla' - Executing 'get_repo_info-0' immediately...
18:21:41.468 | INFO    | Task run 'get_repo_info-0' - Finished in state Completed()
18:21:41.477 | INFO    | Flow run 'fine-gorilla' - Stars 🌠 : 12340
18:21:41.606 | INFO    | Flow run 'fine-gorilla' - Created task run 'get_contributors-0' for task 'get_contributors'
18:21:41.607 | INFO    | Flow run 'fine-gorilla' - Executing 'get_contributors-0' immediately...
18:21:42.225 | INFO    | Task run 'get_contributors-0' - Finished in state Completed()
18:21:42.232 | INFO    | Flow run 'fine-gorilla' - Number of contributors 👷: 30
18:21:42.383 | INFO    | Flow run 'fine-gorilla' - Finished in state Completed('All states completed.')
```
</div>


You'll find a link directing you to the flow run page conveniently positioned at the top of your flow logs.

![Flow run timeline](/img/ui/flow-run-diagram.jpg)

Local flow run execution is great for development and testing, but to [schedule flow runs](/concepts/schedules/) or [trigger them based on events](/cloud/automations/), you’ll need to [deploy](/concepts/deployments/) your flows.


### Step 5: Deploy the flow

[Deploying](/tutorial/deployments/) your flows informs the Prefect API of where, how, and when to run your flows.

!!! warning "Always run `prefect deploy` commands from the **root** level of your repo!"

When you run the `deploy` command, Prefect will automatically detect any flows defined in your repository. Select the one you wish to deploy. Then, follow the 🧙 wizard to name your deployment, add an optional [schedule](/concepts/schedules/), create a [work pool](/tutorial/deployments/#why-work-pools-and-workers), optionally configure [remote flow code storage](/concepts/deployments/#the-pull-action), and more!

<div class="terminal">
```bash
prefect deploy
```
</div>

!!! note "It's recommended to save the configuration for the deployment."
    Saving the configuration for your deployment will result in a `prefect.yaml` file populated with your first deployment. You can use this YAML file to edit and [define multiple deployments](/concepts/deployments-ux/) for this repo. 


### Step 5: Start a [worker](/tutorial/deployments/#why-work-pools-and-workers) and [run the deployed flow](/concepts/deployments/#create-a-flow-run-from-a-deployment)

Start a [worker](/concepts/work-pools/#worker-overview) to manage local flow execution. Each worker polls its assigned [work pool](/tutorial/deployments/#why-work-pools-and-workers).

In a new terminal, run:
<div class="terminal">
```bash
prefect worker start --pool '<work-pool-name>'
```
</div>

Now that your worker is running, you are ready to [kick off deployed flow runs from the UI](/concepts/deployments/#create-a-flow-run-with-prefect-ui) or by running:

<div class="terminal">
```bash
prefect deployment run '<flow-name>/<deployment-name>'
```
</div>

Check out this flow run's logs from the Flow Runs page in the UI or from the worker logs. Congrats on your first successfully deployed flow run! 🎉

You've seen:

- how to define your flows and tasks using decorators
- how to deploy a flow
- how to start a worker

## Next Steps

To learn more, try our [tutorial](/tutorial) and [guides](/guides), or go deeper with [concepts](/concepts).

!!! tip "Need help?"
    Get your questions answered by a Prefect Product Advocate! [Book a Meeting](https://calendly.com/prefect-experts/prefect-product-advocates?utm_campaign=prefect_docs_cloud&utm_content=prefect_docs&utm_medium=docs&utm_source=docs)

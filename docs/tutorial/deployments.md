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

This page of the tutorial covers scheduling workflows with Prefect by deploying flows.

!!! note "Reminder to connect to Prefect Cloud or a self-hosted Prefect server instance"
    Some features in this tutorial, such as scheduling, require you to be connected to a Prefect server.
    If using a self-hosted setup, run `prefect server start` to run both the webserver and UI.
    If using Prefect Cloud, make sure you have [successfully authenticated your local environment](/cloud/cloud-quickstart/).

## Deployment benefits

Up to this point, we’ve run Prefect flows as scripts, but this means *you* have been the one triggering and managing flow runs.

By deploying a run with Prefect, you can:

- Automatically trigger runs, cancel active runs, pause scheduled runs, customize parameters, and more.
- Remotely configure schedules and automation rules for your deployments.
- Dynamically provision infrastructure using [workers](/tutorials/workers/).

## What is a deployment?

Deploying a flow specifies where and how it runs for remote orchestration.

## Create deployments

Using our `get_repo_info` flow from the previous sections, we can easily create a deployment for it by calling a single method on the flow object: `flow.serve`:

```python hl_lines="16-17" title="repo_info.py"
import httpx
from prefect import flow


@flow(log_prints=True)
def get_repo_info(repo_name: str = "PrefectHQ/prefect"):
    url = f"https://api.github.com/repos/{repo_name}"
    response = httpx.get(url)
    response.raise_for_status()
    repo = response.json()
    print(f"{repo_name} repository statistics 🤓:")
    print(f"Stars 🌠 : {repo['stargazers_count']}")
    print(f"Forks 🍴 : {repo['forks_count']}")


if __name__ == "__main__":
    get_repo_info.serve(name="my-first-deployment")
```

By running this script, you:

- Create a deployment called "my-first-deployment" for your flow in the Prefect API.
- Continue running workflows to listen for flow runs for this deployment; when a run is found, it *asynchronously executes within a subprocess*.

Because this deployment has no schedule or triggering automation, you need to use the UI or API to create runs for it.
Let's use the CLI (in a separate terminal window) to create a run for this deployment:

<div class="terminal">

```bash
prefect deployment run 'get-repo-info/my-first-deployment'
```

</div>

If you are watching either your terminal or your UI, you should see the newly created run execute successfully!  
Let's take this example further by adding a schedule and additional metadata.

### Additional options

The `serve` method on flows exposes many options for the deployment.
Let's use a few of these keyword options now:

- `cron`: Sets a cron string schedule for the deployment; see [schedules](/concepts/schedules/) for more advanced scheduling options.
- `tags`: Tags this deployment and its runs for bookkeeping and filtering purposes.
- `description`: Documents what this deployment does. By default, the description is set from the docstring of the flow function, but we did not document our flow function.
- `version`: Tracks changes to our deployment. By default, a hash of the file containing the flow is used; popular options include semver tags or git commit hashes.

Let's add these options to our deployment:

```python
if __name__ == "__main__":
    get_repo_info.serve(
        name="my-first-deployment",
        cron="* * * * *",
        tags=["testing", "tutorial"],
        description="Given a GitHub repository, logs repository statistics for that repo.",
        version="tutorial/deployments",
    )
```

When you rerun this script, you see an updated deployment in the UI that is actively scheduling work!  
Stop the script in the CLI using `CTRL+C` and your schedule pauses automatically.

!!! note "`.serve` is a long-running process"
    For remotely triggered or scheduled runs to execute, your script with `flow.serve` must be actively running.

## Running multiple deployments at once

You can handle deployments for multiple flows by adding a few additional method calls and imports:

```python hl_lines="2 18-20" title="multi_flow_deployment.py"
import time
from prefect import flow, serve


@flow
def slow_flow(sleep: int = 60):
    "Sleepy flow - sleeps the provided amount of time (in seconds)."
    time.sleep(sleep)


@flow
def fast_flow():
    "Fastest flow this side of the Mississippi."
    return


if __name__ == "__main__":
    slow_deploy = slow_flow.to_deployment(name="sleeper", interval=45)
    fast_deploy = fast_flow.to_deployment(name="fast")
    serve(slow_deploy, fast_deploy)
```

A few observations:

- The `flow.to_deployment` interface exposes the *exact same* options as `flow.serve`; this method produces a deployment object.
- Register deployments with the API after you call `serve(...)`.
- When serving multiple deployments, the only requirement is that they share a Python environment; you can execute and schedule them independently of each other.

## Hybrid deployments

Prefect's deployments enable a hybrid execution model. This allows you to run workflows in Prefect Cloud or your own server, optimizing resource usage and data privacy. No inbound connections needed.
For more information, see [hybrid model](https://www.prefect.io/security/overview/#hybrid-model).

## Next steps

Congratulations! You now have your first working deployment.

However, if your team has more complex infrastructure requirements or you'd like to have Prefect manage flow execution, you can [deploy flows to a work pool](/tutorial/work-pools/).

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

!!! note "Reminder to start a Prefect API"
    Some features in this tutorial, such as scheduling, require a Prefect server to be running; if using a self-hosted setup, simply run `prefect server start` to run both the webserver and UI; if using Prefect Cloud, make sure you have [successfully configured your local profile](/cloud/cloud-quickstart/).

## Why deployments?

One of the most common reasons to use a tool like Prefect is [scheduling](/concepts/schedules) or [event-based triggering](/concepts/automations/). 
Up to this point, we’ve demonstrated running Prefect flows as scripts, but this means *you* have been the one triggering and managing flow runs. 
You can certainly continue to trigger your workflows in this way and use Prefect as a monitoring layer for other schedulers or systems, but you will miss out on many of the other benefits and features that Prefect offers.

Deploying a flow exposes an API and UI so that you can:

- trigger new runs, [cancel active runs](/concepts/flows/#cancel-a-flow-run), pause scheduled runs, customize parameters, and more
- remotely configure schedules and automation rules for your deployments
- dynamically provision infrastructure using [workers](/tutorials/workers/)

## What is a deployment?

Deploying a flow is the act of specifying when, where, and how it will run. 
This information is encapsulated and sent to Prefect as a [deployment](/concepts/deployments/) that contains the crucial metadata needed for remote orchestration. 
Deployments elevate workflows from functions that you call manually to API-managed entities.

Attributes of a deployment include (but are not limited to):

- __Flow entrypoint__: path to your flow function 
- __Schedule__ or __Trigger__: optional schedule or triggering rule for this deployment
- __Tags__: optional text labels for organizing your deployments

## Create a deployment

Using our `get_repo_info` flow from the previous sections, we can easily create a deployment for it by introducing one simple line of code:

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

Running this script will do two things:

- create a deployment called "my-first-deployment" for your flow in the Prefect API
- stay running to listen for flow runs for this deployment; when a run is found, it will be _asynchronously executed within a subprocess_

!!! warning "Deployments must be defined in static files"
    Flows can be defined and run interactively, that is, within REPLs or Notebooks.
    Deployments, on the other hand, require that your flow definition be in a known file (which can be located on a remote filesystem in certain setups).  

Because this deployment has no schedule or triggering automation, you will need to use the UI or API to create runs for it. 
Let's use the CLI (in a separate terminal window) to see what happens:
<div class="terminal">
```bash
prefect deployment run 'get-repo-info/my-first-deployment'
```
</div>

If you are watching either your terminal or your UI, you should see the newly created run execute successfully!  
Let's take this example further by adding a schedule and additional metadata.


### Additional options

The `serve` method on flows exposes many options for your deployment.
Let's use a few of these options now:

- `cron`: a keyword that allows us to set a cron string schedule for the deployment; see [schedules](/concepts/schedules/) for more advanced scheduling options
- `tags`: a keyword that allows us to tag this deployment and its runs for bookkeeping and filtering purposes
- `description`: a keyword that allows us to document what this deployment does; by default the description is set from the docstring of the flow function, but we did not document our flow
- `version`: a keyword that allows us to track changes to our deployment; by default a hash of the file containing the flow is used; popular options include semver tags or git commit hashes

Setting these fields is simple:
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

When you rerun this script, you will find an updated deployment in the UI that is actively scheduling work!  Stop the script using `CTRL+C` and your schedule will be automatically paused.

!!! note "`.serve` is a long-running process"
    In order for remotely triggered or scheduled runs to be executed, your script with `flow.serve` must be actively running.

## Running multiple deployments at once

This method is useful for creating deployments for single flows, but what if we have two or more flows?  This only requires a few additional method calls and imports to get up and running:

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

A few observations are in order:

- the `flow.to_deployment` interface exposes the _exact same_ options as `flow.serve`; this method produces a deployment object
- the deployments are only registered with the API once `serve(...)` is called
- when serving multiple deployments, the only requirement is that they share a Python environment; they can be executed and scheduled independently of each other

You should spend some time experimenting with this setup; a few next steps for exploration include:

- pausing and unpausing the schedule for the "sleeper" deployment
- use the UI to submit ad-hoc runs for the "sleeper" deployment with different values for `sleep`
- use the UI to cancel an active run for the "sleeper" deployment (good luck cancelling the "fast" one 😉)

!!! tip "Security Note"
    Another implication of Prefect's deployment interface is our hybrid execution model. Whether you use Prefect Cloud or host a Prefect server instance yourself, you'll always be able to run work flows in the environments best suited to their execution. This model allows you efficient use of your infrastructure resources while maintaining the privacy of your code and data.
    There is no ingress required. 
    For more information [read more about our hybrid model](https://www.prefect.io/security/overview/#hybrid-model).

## Next steps

Congratulations! You now have your first working deployment. 

### Running flows on dynamic or managed infrastructure

Deploying flows through the `serve` method is the most straight forward way to start scheduling flows with Prefect. However, if your team has complex infrastructure requirements or you'd like to use prefect [managed execution](/guides/managed-execution/) an alternative option involves deploying flows to a [work pool](/concepts/work-pools/).

### Docker tutorials 📖

To see how to host your served flow in a Docker container, head to our [Docker guide](/guides/docker/).

Alternatively, to execute each flow run within its own _dedicated_ Docker container (or other ephemeral [infrastructure](/concepts/work-pools/#worker-types)) learn how to use a Prefect worker by heading to the [worker and work pools tutorial page](/tutorial/workers/).

For a deeper understanding of the trade-offs between the serve and worker approaches or how you might mix and match both methods, refer to our [deployment concept page](/concepts/deployments/#two-approaches-to-deployments).

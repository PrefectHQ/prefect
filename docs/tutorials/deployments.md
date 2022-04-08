---
description: Learn how to create Prefect flow deployments and run them with work queues and agents.
tags:
    - Orion
    - work queues
    - agents
    - orchestration
    - flow runs
    - deployments
    - schedules
    - tutorial
---

# Deployments

In the tutorials leading up to this one, you've been able to explore Prefect capabilities like flows, tasks, retries, caching, using task runners to execute tasks sequentially, concurrently, or even in parallel. But so far, you've run flows as scripts. 

[Deployments](/concepts/deployments/) take your flows to the next level: adding the information needed for scheduling flow runs or triggering a run via an API call. Deployments elevate workflows from functions that you call manually to API-managed entities.


## Components of a deployment

You need just a few ingredients to turn a flow definition into a deployment:

- A flow
- A deployment specification

That's it. To create flow runs based on the deployment, you need a few more pieces:

- Prefect Orion server
- A work queue
- An agent

These all come with Prefect. You just have to configure them and set them to work.

## From flow to deployment

As noted earlier, the first ingredient of a deployment is a flow. You've seen a few of these already, and perhaps have written a few if you've been following the tutorials. 

Let's start with a simple example:

```python
from prefect import flow, task, get_run_logger

@task
def log_message(name):
    logger = get_run_logger()
    logger.info(f"Hello {name}!")
    return

@flow(name="leonardo_dicapriflow")
def leonardo_dicapriflow(name: str):
    log_message(name)
    return

leonardo_dicapriflow("Leo")
```

Save this in a file `leo_flow.py` and run it as a Python script. You'll see output like this:

<div class="termy">
```
$ python leo_flow.py
12:14:30.012 | INFO    | prefect.engine - Created flow run 'certain-cormorant' for flow 'leonardo_dicapriflow'
12:14:30.013 | INFO    | Flow run 'certain-cormorant' - Using task runner 'ConcurrentTaskRunner'
12:14:30.090 | INFO    | Flow run 'certain-cormorant' - Created task run 'log_message-dd6ef374-0' for task 'log_message'
12:14:30.143 | INFO    | Task run 'log_message-dd6ef374-0' - Hello Leo!
12:14:30.191 | INFO    | Task run 'log_message-dd6ef374-0' - Finished in state Completed(None)
12:14:30.459 | INFO    | Flow run 'certain-cormorant' - Finished in state Completed('All states completed.')
```
</div>

Like our previous flow examples, this is still a script that you have to run locally. Let's take this script and turn it into a deployment by creating a deployment specification.

## Deployment specifications

A [deployment specification](/concepts/deployments/#deployment-specifications) includes the settings that will be used to create a deployment in the Orion database. It consists of the following pieces of required information:

- The deployment `name`
- The `flow_location`: the path to a flow definition

You can additionally include the following pieces of optional information:

- `tags` to attach to the runs generated from this deployment
- `parameters` whose values will be passed to the flow function when it runs
- a `schedule` for auto-generating flow runs

To create the deployment specification, import `DeploymentSpec`, then define a `DeploymentSpec` object as either Python or YAML code. Save this in a new `leo_deployment.py` file. 

```python
from prefect.deployments import DeploymentSpec

DeploymentSpec(
    name="leonardo-deployment",
    flow_location="./leo_flow.py",
    tags=['tutorial','test'],
    parameters={'name':'Leo'}
)
```

Note that we moved the value passed as the `name` parameter to  `parameters=` in the deployment specification.

Also, in the flow definition `leo_flow.py`, comment out or remove the last line `leonardo_dicapriflow("Leo")`, the call to the flow function. We don't need that anymore, because Prefect will call it directly with the specified `parameters` when it executes the deployment.

```python hl_lines="14"
from prefect import flow, task, get_run_logger

@task
def log_message(name):
    logger = get_run_logger()
    logger.info(f"Hello {name}!")
    return

@flow(name="leonardo_dicapriflow")
def leonardo_dicapriflow(name: str):
    log_message(name)
    return

# leonardo_dicapriflow("Leo")
```

## Creating the deployment

Now that you have a `leo_flow.py` flow definition and a `leo_deployment.py` deployment specification, you can use the Prefect CLI to create the deployment.

Use the `prefect deployment create` command to create the deployment with the Orion server, specifying the name of the file that contains the deployment specification:

<div class="termy">
```
$ prefect deployment create leo_deployment.py
Loading deployments from python script at 'leo_deployment.py'...
Created deployment 'leonardo-deployment' for flow 'leonardo_dicapriflow'
```
</div>

Now your deployment has been created by the Orion API and is ready to orchestrate future `leonardo_dicapriflow` flow runs.

To demonstrate that your deployment exists, list all of the current deployments:

<div class="termy">
```
$ prefect deployment ls
leonardo_dicapriflow/leonardo-deployment
```
</div>

Use `prefect deployment inspect` to display details for a specific deployment.

<div class='termy'>
```
$ prefect deployment inspect leonardo_dicapriflow/leonardo-deployment
Deployment(
    id='e642fa3e-2b6b-4815-bb5e-ef2df9afb31f',
    created='31 minutes ago',
    updated='31 minutes ago',
    name='leonardo-deployment',
    flow_id='1ef983a8-e3b9-464d-93b6-fd9fa902b689',
    flow_data=DataDocument(encoding='blockstorage'),
    parameters={'name': 'Leo'},
    tags=['tutorial', 'test'],
    flow_runner=FlowRunnerSettings()
)
```
</div>

Now that the deployment is created, you can interact with it in multiple ways. For example, you can use the Prefect CLI to execute a local flow run for the deployment.

<div class="termy">
```
$ prefect deployment execute leonardo_dicapriflow/leonardo-deployment
12:17:42.331 | INFO    | prefect.engine - Created flow run 'tan-lion' for flow 'leonardo_dicapriflow'
12:17:42.331 | INFO    | Flow run 'tan-lion' - Using task runner 'ConcurrentTaskRunner'
12:17:42.403 | INFO    | Flow run 'tan-lion' - Created task run 'log_message-718c3f46-0' for task 'log_message'
12:17:42.449 | INFO    | Task run 'log_message-718c3f46-0' - Hello Leo!
12:17:42.493 | INFO    | Task run 'log_message-718c3f46-0' - Finished in state Completed(None)
12:17:42.771 | INFO    | Flow run 'tan-lion' - Finished in state Completed('All states completed.')
```
</div>

When you executed the deployment, you referenced it by name in the format "<flow name>/<deployment name>". When you create new deployments in the future, remember that while a flow may be referenced by multiple deployments, each must have a unique name.

You can also see your deployment in the [Orion UI](/ui/overview/). Start the server: 

```bash
prefect orion start
```

Open the UI at [http://127.0.0.1:4200/](http://127.0.0.1:4200/) and click **Deployments** to see any deployments you've created. You may need to click the **Show all deployments** button to see deployments with no schedule like the one you just created. (The default [filters](/ui/filters/) display deployments with scheduled runs.)

![Deployments are listed on the Deployments page of the Orion UI](/img/tutorials/my-first-deployment.png)

Note that you can't **Quick Run** the deployment from the UI yet. As mentioned at the beginning of this tutorial, we still need two more items to run orchestrated deployments: a work queue and an agent. We'll set those up next.

## Work queues and agents

[Work queues and agents](/concepts/work-queues/) are the mechanisms by which the Orion API orchestrates deployment flow runs.

Work queues let you organize flow runs into queues for execution. Agents pick up work from queues and execute the flows.

There is no default global work queue or agent, so to orchestrate runs of `leonardo_dicapriflow` we need to configure a work queue and agent. 

### Create a work queue

Open a new terminal session and run the following command to create a work queue called `tutorial_queue`:

```bash
prefect work-queue create tutorial_queue
```

Orion API creates the work queue and returns the ID of the queue. Note this ID, you'll use it in a moment to create an agent that polls for work from this queue.

<div class='termy'>
```
$ prefect work-queue create tutorial_queue
UUID('3461754d-e411-4155-9bc7-a0145b6974a0')
```
</div>

Run `prefect work-queue ls` to see a list of available work queues.

```bash
$ prefect work-queue ls
                                         Work Queues
┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━┳━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                      ID ┃ … ┃ Con… ┃ Filter                                               ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━╇━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 3461754d-e411-4155-9bc… │ … │ None │ {"tags": null, "deployment_ids": null, "flow_runner… │
└─────────────────────────┴───┴──────┴──────────────────────────────────────────────────────┘
                                 (**) denotes a paused queue
```

Note that you can provide optional [work queue configuration flags](/concepts/work-queues/#work-queue-configuration) to filter which deployments are allocated to a specific work queue by criteria such as tags, flow runners, or even specific deployments. The `tutorial_queue` work queue you just created will queue any available scheduled deployments.

### Run an agent

Now that you have a work flow to allocate work, run an agent to pick up work from that queue.

In the terminal, run the `prefect agent start` command, passing the ID of the `tutorial_queue` work queue you just created (it will be different from the example shown here).

```bash
prefect agent start '3461754d-e411-4155-9bc7-a0145b6974a0'
```

That starts up an agent. Leave this running for the rest of the tutorial.

```bash 
$ prefect agent start '3461754d-e411-4155-9bc7-a0145b6974a0'
Starting agent with ephemeral API...

  ___ ___ ___ ___ ___ ___ _____     _   ___ ___ _  _ _____
 | _ \ _ \ __| __| __/ __|_   _|   /_\ / __| __| \| |_   _|
 |  _/   / _|| _|| _| (__  | |    / _ \ (_ | _|| .` | | |
 |_| |_|_\___|_| |___\___| |_|   /_/ \_\___|___|_|\_| |_|


Agent started!
```

## Run an orchestrated deployment

With a work flow and agent in place, you can create a flow run for `leonardo_dicapriflow` directly from the UI.

Go back to the Prefect Orion UI and click the **Quick Run** button next the deployment.

![Create a quick run for the deployment](/img/tutorials/quick-run.png)

You'll see the flow run in the **Run History** pane of the UI.

![The deployment flow run is shown in the UI run history](/img/tutorials/deployment-run.png)

If you switch over to the terminal session where your agent is running, you'll see that the agent picked up the flow run and executed it.

```bash
❯ prefect agent start '3461754d-e411-4155-9bc7-a0145b6974a0'
Starting agent with ephemeral API...

  ___ ___ ___ ___ ___ ___ _____     _   ___ ___ _  _ _____
 | _ \ _ \ __| __| __/ __|_   _|   /_\ / __| __| \| |_   _|
 |  _/   / _|| _|| _| (__  | |    / _ \ (_ | _|| .` | | |
 |_| |_|_\___|_| |___\___| |_|   /_/ \_\___|___|_|\_| |_|


Agent started!
14:18:22.684 | INFO    | prefect.agent - Submitting flow run '1a466895-368f-4ecc-94ba-c735e8d6f4bc'
14:18:22.718 | INFO    | prefect.flow_runner.subprocess - Opening subprocess for flow run '1a466895-368f-4ecc-94ba-c735e8d6f4bc'...
14:18:22.730 | INFO    | prefect.agent - Completed submission of flow run '1a466895-368f-4ecc-94ba-c735e8d6f4bc'
14:18:29.767 | INFO    | prefect.flow_runner.subprocess - Subprocess for flow run '1a466895-368f-4ecc-94ba-c735e8d6f4bc' exited cleanly.
```

Back in the UI, click **Flow Runs**. You'll see the flow run for the deployment, showing the 'tutorial' and 'test' tags specified in the deployment specification.

![The flow run for the deployment is shown in the UI](/img/tutorials/dep-flow-runs.png)

Click the flow run to see details. In the flow run logs, you can see that the flow run logged a "Hello Leo!" message as expected.

![The flow run logs show the expected Hello Leo! log message](/img/tutorials/dep-flow-logs.png)

## Cleaning up

You're welcome to leave the work queue and agent running to experiment and to handle local development.

To terminate the agent, simply go to the terminal session where it's running and end the process with either `Ctrl+C` or by terminating the terminal session.

To pause a work queue, run the Prefect CLI command `prefect work-queue pause`, passing the work queue ID.

To delete a work queue, run the command `prefect work-queue delete`, passing the work queue ID.

<div class='termy'>
```
$ prefect work-queue delete '3461754d-e411-4155-9bc7-a0145b6974a0'
Deleted work queue 3461754d-e411-4155-9bc7-a0145b6974a0
```
</div>

<!-- The REST API

We can additionally use the REST API directly; to facilitate this, we will demonstrate how this works with the convenient Python Orion Client:

```python
from prefect.client import get_client

async with get_client() as client:
    deployment = await client.read_deployment_by_name("Addition Machine/my-first-deployment")
    flow_run = await client.create_flow_run_from_deployment(deployment)
```

Note that the return values of these methods are full model objects. -->

!!! tip "Additional Reading"
    To learn more about the concepts presented here, check out the following resources:

    - [Deployment Specs](/api-ref/prefect/deployments/)
    - [Deployments](/concepts/deployments/)
    - [Schedules](/concepts/schedules/)

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

In the tutorials leading up to this one, you've been able to explore Prefect capabilities like flows, tasks, retries, caching, and so on. But so far, you've run flows as scripts. 

[Deployments](/concepts/deployments/) take your flows to the next level: adding the information needed for scheduling flow runs or triggering a flow run via an API call. Deployments elevate workflows from functions that you call manually to API-managed entities.

## Components of a deployment

You need just a few ingredients to turn a flow definition into a deployment:

- A flow
- A deployment specification

That's it. To create flow runs based on the deployment, you need a few more pieces:

- Prefect orchestration engine, either [Prefect Cloud](/ui/cloud/) or a local Prefect Orion server started with `prefect orion start`.
- Remote [storage](/concepts/storage/) for flow deployments and results.
- A [work queue and agent](/concepts/work-queues/).

These all come with Prefect. You just have to configure them and set them to work. You'll see how to configure each component during this tutorial.

## From flow to deployment

As noted earlier, the first ingredient of a deployment is a flow script. You've seen a few of these already, and perhaps have written a few if you've been following the tutorials. 

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

<div class="terminal">
```
$ python leo_flow.py
12:14:30.012 | INFO    | prefect.engine - Created flow run 'certain-cormorant' for flow 
'leonardo_dicapriflow'
12:14:30.013 | INFO    | Flow run 'certain-cormorant' - Using task runner 'ConcurrentTaskRunner'
12:14:30.090 | INFO    | Flow run 'certain-cormorant' - Created task run 'log_message-dd6ef374-0' 
for task 'log_message'
12:14:30.143 | INFO    | Task run 'log_message-dd6ef374-0' - Hello Leo!
12:14:30.191 | INFO    | Task run 'log_message-dd6ef374-0' - Finished in state Completed(None)
12:14:30.459 | INFO    | Flow run 'certain-cormorant' - Finished in state Completed('All states 
completed.')
```
</div>

Like previous flow examples, this is still a script that you have to run locally. 

In the rest of this tutorial, you'll turn this into a deployment that can create flow runs. You'll create the deployment by doing the following: 

- Creating a deployment specification for this flow.
- Using the Prefect CLI and the deployment specification to create a deployment on the server.
- Inspecting the deployment with the CLI and UI.
- Starting ad hoc flow runs based on the deployment.

## Deployment specifications

A [deployment specification](/concepts/deployments/#deployment-specifications) includes the settings that will be used to create a deployment in the Prefect database and to create flow runs based on the flow code and deployment settings. A deployment specification consists of the following pieces of required information:

- The `name` of the deployment
- The `flow` name or the path to the flow definition

You can additionally include the following optional information:

- `tags`, which are used to filter flow runs in the UI and work queues
- `parameters`, whose values will be passed to the flow function when the flow run begins
- a `schedule`, which lets the Prefect API auto-generate flow runs

A deployment specification is a definition of a `Deployment` object. You can create this in the same code file as the flow code, but it's a common pattern to create a separate Python file that contains one or more deployment specifications. 

To create the deployment specification, import `Deployment`, then define a `Deployment` object as either Python or [YAML code](/concepts/deployments/#deployment-specifications-as-code). 

Here's an example of a deployment specification for the flow you created earlier in `leo_flow.py`. We'll also use a [`FlowScript`](/concepts/deployments/#deployment-object) to pass the name of the flow function and the location of the flow script. 

Save the following deployment specification code in a new `leo_deployment.py` file. 

```python
from prefect.deployments import Deployment
from prefect.deployments import FlowScript

Deployment(
    name="leonardo-deployment",
    flow="./leo_flow.py",
    tags=['tutorial','test'],
    parameters={'name':'Leo'}
)
```

Note that this deployment specification moves the 'Leo' value passed as the `name` parameter to a `parameters=` setting in the deployment specification. As you'll see later, one way to use deployments is to create separate deployment specifications for the same flow code, but each deployment specification passes different parameters for different use cases.

Also, in the flow definition `leo_flow.py` that you created earlier, comment out or remove the last line `leonardo_dicapriflow("Leo")`, the call to the flow function. You don't need that anymore because Prefect will call it directly with the specified `parameters` when it executes the deployment.

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

## Running Prefect Orion

For this tutorial, you'll use a local Prefect Orion server. Open a separate terminal and start the Prefect Orion server with the `prefect orion start` CLI command:

<div class='terminal'>
```bash
$ prefect orion start
Starting...

 ___ ___ ___ ___ ___ ___ _____    ___  ___ ___ ___  _  _
| _ \ _ \ __| __| __/ __|_   _|  / _ \| _ \_ _/ _ \| \| |
|  _/   / _|| _|| _| (__  | |   | (_) |   /| | (_) | .` |
|_| |_|_\___|_| |___\___| |_|    \___/|_|_\___\___/|_|\_|

Configure Prefect to communicate with the server with:

    prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api

Check out the dashboard at http://127.0.0.1:4200
```
</div>

Note the message to set `PREFECT_API_URL` so that you're coordinating flows with this API instance.

Open another terminal and run this command to set the API URL:

<div class='terminal'>
```
$ prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api
Set variable 'PREFECT_API_URL' to 'http://127.0.0.1:4200/api'
Updated profile 'default'
```
</div>

## Configuring storage

Now configure remote [storage](/concepts/storage/) for flow and task run data. 

This is an important step for coordinating flows with deployments. When you create a deployment, the Prefect Orion orchestration engine saves a pickled version of your flow code in the storage environment you specify. Later, any flow runs created from the deployment retrieve the flow code from your storage and save task results to that storage, regardless of the environment in which the flow run executes. That flow code and result data is always under your control.

This means, however, that you need to have access to a storage location such as an S3 bucket, and create a storage definition on the Prefect server. (As an advanced configuration, you can also define storage in the deployment specification. See the [Deployments](/concepts/deployments/) documentation for details.)

Before doing this next step, make sure you have the information to connect to and authenticate with a remote data store. In this example we're connecting to an AWS S3 bucket, but you could also use Azure Blob Storage, Google Cloud Storage, or File Storage using any file system supported by `fsspec`.

Run the `prefect storage create` command. In this case we choose the S3 Storage option and supply the bucket name and AWS IAM access keys.

<div class='terminal'>
```
$ prefect storage create
Found the following storage types:
0) Azure Blob Storage
    Store data in an Azure blob storage container.
1) File Storage
    Store data as a file on local or remote file systems.
2) Google Cloud Storage
    Store data in a GCS bucket.
3) KV Server Storage
    Store data by sending requests to a KV server.
4) Local Storage
    Store data in a run's local file system.
5) S3 Storage
    Store data in an AWS S3 bucket.
6) Temporary Local Storage
    Store data in a temporary directory in a run's local file system.
Select a storage type to create: 5
You've selected S3 Storage. It has 6 option(s).
BUCKET: the-curious-case-of-benjamin-bucket
AWS ACCESS KEY ID (optional): XXXXXXXXXXXXXXXXXXXX
AWS SECRET ACCESS KEY (optional): XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
AWS SESSION TOKEN (optional):
PROFILE NAME (optional):
REGION NAME (optional):
Choose a name for this storage configuration: benjamin-bucket
Validating configuration...
Registering storage with server...
Registered storage 'benjamin-bucket' with identifier '0f536aaa-216f-4c72-9c31-f3272bcdf977'.
You do not have a default storage configuration. Would you like to set this as your default storage? [Y/n]: y
Set default storage to 'benjamin-bucket'.
```
</div>

We set this storage as the default that Prefect will use for flow runs. Any flow runs can use the persistent S3 storage for flow code, task results, and flow results rather than relying on local storage that will disappear when the container shuts down.

This is important for deployments because it means you can run the deployed flow in any environment that has access to your storage!

## Creating the deployment

Now that you have a `leo_flow.py` flow definition and a `leo_deployment.py` deployment specification, you can use the Prefect CLI to create the deployment on the server.

Use the `prefect deployment create` command to create the deployment on the Prefect Orion server, specifying the name of the file that contains the deployment specification:

<div class="terminal">
```
$ prefect deployment create leo_deployment.py
Loading deployments from python script at 'leo_deployment.py'...
Retrieving flow from script at 'leo_flow.py'...
Packaging flow for deployment 'leonardo_dicapriflow/leonardo-deployment'...
Registering deployment 'leonardo_dicapriflow/leonardo-deployment' with the server...
Created deployment 'leonardo_dicapriflow/leonardo-deployment'
(279f9124-6745-485c-a8a4-46e1581abb08).
Created 1 deployment!
Created 1 deployments!
```
</div>

Now your deployment has been created by the Prefect API and is ready to orchestrate future `leonardo_dicapriflow` flow runs.

To demonstrate that your deployment exists, list all of the current deployments:

<div class="terminal">
```
$ prefect deployment ls
                                     Deployments
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Name                                       ┃ ID                                   ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Kikis Delivery Flow/kikis-adhoc-deployment │ 1f89458d-407d-47fb-91ba-939ee458fb18 │
│ leonardo_dicapriflow/leonardo-deployment   │ 279f9124-6745-485c-a8a4-46e1581abb08 │
└────────────────────────────────────────────┴──────────────────────────────────────┘
```
</div>

Use `prefect deployment inspect` to display details for a specific deployment.

<div class='terminal'>
```
$ prefect deployment inspect 'leonardo_dicapriflow/leonardo-deployment'
{
    'id': '279f9124-6745-485c-a8a4-46e1581abb08',
    'created': '2022-04-27T21:34:12.233964+00:00',
    'updated': '2022-04-27T21:36:24.096406+00:00',
    'name': 'leonardo-deployment',
    'flow_id': '8a24efd8-b343-4b49-a94b-012729e644ce',
    'flow_data': {
        'encoding': 'blockstorage',
        'blob': '{"data": "\\"5f781e1f-f18a-4edd-b76b-ed6dd7a608c8\\"", "block_id":
"840a2de4-8721-4500-bc8b-604cab79fc2e"}'
    },
    'schedule': None,
    'is_schedule_active': True,
    'parameters': {'name': 'Leo'},
    'tags': ['tutorial', 'test'],
    'flow_runner': {'type': 'universal', 'config': {'env': {}}}
}
```
</div>

## Run the deployment locally

Now that you've created the deployment, you can interact with it in multiple ways. For example, you can use the Prefect CLI to execute a local flow run for the deployment.

<div class="terminal">
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

When you executed the deployment, you referenced it by name in the format "flow_name/deployment_name". When you create new deployments in the future, remember that while a flow may be referenced by multiple deployments, each deployment must have a unique name.

You can also see your flow in the [Prefect UI](/ui/overview/). Open the Prefect UI at [http://127.0.0.1:4200/](http://127.0.0.1:4200/). You'll see your deployment's flow run in the UI.

![Deployments are listed on the Deployments page of the Prefect UI](/img/tutorials/my-first-deployment.png)

Note that you can't **Quick Run** the deployment from the UI yet. As mentioned at the beginning of this tutorial, you still need two more items to run orchestrated deployments: a work queue and an agent. You'll set those up next.

## Work queues and agents

[Work queues and agents](/concepts/work-queues/) are the mechanisms by which the Prefect API orchestrates deployment flow runs.

Work queues let you organize flow runs into queues for execution. Agents pick up work from queues and execute the flows.

There is no default global work queue or agent, so to orchestrate runs of `leonardo_dicapriflow` you need to configure a work queue and agent. 

### Create a work queue

Open a new terminal session and run the following command to create a work queue called `tutorial_queue`:

<div class='terminal'>
```bash
prefect work-queue create --tag tutorial tutorial_queue
```
</div>

Note that this command specifically creates a "tutorial" tag on the work queue, meaning the `tutorial_queue` work queue will only serve deployments that include a "tutorial" tag. This is a good practice to make sure flow runs for a given deployment run only in the correct environments, based on the tags you apply.

The Prefect API creates the work queue and returns the ID of the queue. Note this ID, you'll use it in a moment to create an agent that polls for work from this queue.

<div class='terminal'>
```
$ prefect work-queue create --tag tutorial tutorial_queue
UUID('3461754d-e411-4155-9bc7-a0145b6974a0')
```
</div>

Run `prefect work-queue ls` to see a list of available work queues.

<div class='terminal'>
```bash
$ prefect work-queue ls
                                 Work Queues
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
┃                                   ID ┃ Name           ┃ Concurrency Limit ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
│ 3461754d-e411-4155-9bc7-a0145b6974a0 │ tutorial_queue │ None              │
└──────────────────────────────────────┴────────────────┴───────────────────┘
                         (**) denotes a paused queue
```
</div>

Note that you can provide additional, optional [work queue configuration flags](/concepts/work-queues/#work-queue-configuration) to filter which deployments are allocated to a specific work queue by criteria such as tags, flow runners, or even specific deployments. 

You can also create, edit, and manage work queues through [Prefect UI Work Queues](/ui/work-queues/) page.

### Run an agent

Now that you have a work queue to allocate flow runs, you can run an agent to pick up flow runs from that queue.

In the terminal, run the `prefect agent start` command, passing the ID of the `tutorial_queue` work queue you just created (it will be different from the example shown here).

<div class='terminal'>
```bash
prefect agent start '3461754d-e411-4155-9bc7-a0145b6974a0'
```
</div>

That starts up an agent. Leave this running for the rest of the tutorial.

<div class='terminal'>
```bash 
$ prefect agent start '3461754d-e411-4155-9bc7-a0145b6974a0'
Starting agent with ephemeral API...

  ___ ___ ___ ___ ___ ___ _____     _   ___ ___ _  _ _____
 | _ \ _ \ __| __| __/ __|_   _|   /_\ / __| __| \| |_   _|
 |  _/   / _|| _|| _| (__  | |    / _ \ (_ | _|| .` | | |
 |_| |_|_\___|_| |___\___| |_|   /_/ \_\___|___|_|\_| |_|


Agent started! Looking for work from queue '3461754d-e411-4155-9bc7-a0145b6974a0'...
```
</div>

Remember that:

- The deployment specification included a "tutorial" tag.
- The `tutorial_queue` work queue is defined to serve deployments with a "tutorial" tag.
- The agent is configured to pick up work from `tutorial_queue`, so it will only execute flow runs for deployments with a "tutorial" tag.

!!! note "Reference work queues by name or ID"
    You can reference a work queue by either ID or by name when starting an agent to pull work from a queue. For example: `prefect agent start 'tutorial_queue'`.

    Note, however, that you can edit the name of a work queue after creation, which may cause errors for agents referencing a work queue by name.

## Run an orchestrated deployment

With a work queue and agent in place, you can create a flow run for `leonardo_dicapriflow` directly from the UI.

In the Prefect UI, select the **Deployments** page. You'll see a list of all deployments that have been created in this Prefect Orion instance.

![The Deployments page displays a list of deployments created in Prefect](/img/tutorials/orion-deployments.png)

Now select **kikis-adhoc-deployment** to see details for the deployment you just created.

![Viewing details of a single deployment](/img/tutorials/deployment-details.png)

You can start a flow run for this deployment from the UI by selecting the **Run** button. The Prefect Orion engine routes the flow run request to the work queue, the agent picks up the new work from the queue and initiates the flow run. 

If you switch over to the terminal session where your agent is running, you'll see that the agent picked up the flow run and executed it.

<div class='terminal'>
```bash
09:29:49.422 | INFO    | Flow run 'capable-cormorant' - Using task runner 'ConcurrentTaskRunner'
09:29:49.531 | INFO    | Flow run 'capable-cormorant' - Created task run 'log_message-2143d244-0' for task 'log_message'
09:29:49.559 | INFO    | Task run 'log_message-2143d244-0' - Hello Kiki!
09:29:49.938 | INFO    | Task run 'log_message-2143d244-0' - Finished in state Completed()
09:29:50.315 | INFO    | Flow run 'capable-cormorant' - Finished in state Completed('All states completed.')
09:29:50.754 | INFO    | prefect.flow_runner.subprocess - Subprocess for flow run '32ee5937-c5d4-44c8-aa9e-c7ca924790ef' exited cleanly.
```
</div>

Go back the the **Flow Runs** page in the UI and you'll see the flow run you just initiatied ran and was observed by the API.

![The deployment flow run is shown in the UI run history](/img/tutorials/deployment-run.png)

Click the flow run to see details. In the flow run logs, you can see that the flow run logged a "Hello Leo!" message as expected.

![The flow run logs show the expected Hello Leo! log message](/img/tutorials/dep-flow-logs.png)

## Next steps

So far you've seen a simple example of a single deployment for a single flow. But a common and useful pattern is to create multiple deployments for a flow. By using tags, parameters, and schedules effectively, you can have a single flow definition that serves multiple purposes or can be configured to run in different environments.

For example, you can extend the earlier example by creating a second deployment for `leo_flow.py` that logs different greetings by passing different parameters.

```python
from prefect.deployments import Deployment
from prefect.deployments import FlowScript

Deployment(
    name="leonardo-deployment",
    flow=FlowScript(path="./leo_flow.py", name="leonardo_dicapriflow"),
    tags=['tutorial','test'],
    parameters={'name':'Leo'}
)

Deployment(
    name="marvin-deployment",
    flow=FlowScript(path="./leo_flow.py", name="leonardo_dicapriflow"),
    tags=['tutorial','dev'],
    parameters={'name':'Marvin'}
)
```

If you run `prefect deployment create leo_deployment.py` again with this code, it won't change `leonardo_deployment`, but it will create a new `marvin-deployment`.

- Running `leonardo_deployment` logs the message "Hello Leo!".
- Running `marvin-deployment` logs the message "Hello Marvin!".

Both deployments can use the `tutorial_queue` work queue because they have "tutorial" tags. But if you created a new work queue that served deployments with, say, a "dev" tag, only `marvin-deployment` would be served by that queue and its agents.

## Cleaning up

You're welcome to leave the work queue and agent running to experiment and to handle local development.

To terminate the agent, simply go to the terminal session where it's running and end the process with either `Ctrl+C` or by terminating the terminal session.

To pause a work queue, run the Prefect CLI command `prefect work-queue pause`, passing the work queue ID.

To delete a work queue, run the command `prefect work-queue delete`, passing the work queue ID.

<div class='terminal'>
```
$ prefect work-queue delete '3461754d-e411-4155-9bc7-a0145b6974a0'
Deleted work queue 3461754d-e411-4155-9bc7-a0145b6974a0
```
</div>

To terminate the Prefect API server, go to the terminal session where it's running and end the process with either `Ctrl+C` or by terminating the terminal session.

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

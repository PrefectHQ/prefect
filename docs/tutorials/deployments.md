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

- A flow script

That's it. To create flow runs based on the deployment, you need a few more pieces:

- Prefect orchestration engine, either [Prefect Cloud](/ui/cloud/) or a local Prefect Orion server started with `prefect orion start`.
- A [work queue and agent](/concepts/work-queues/).

These all come with Prefect. You just have to configure them and set them to work. You'll see how to configure each component during this tutorial.

Optionally, you can configure [storage](/concepts/storage/) for packaging and saving your flow code, dependencies and requirements, parameters, and infrastructure. All of these will be covered in more advanced tutorials.

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
```bash
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

- Creating deployment manifest and deployment YAML file that specify your flow details and deployment settings.
- Applying the deployment YAML settings to create a deployment on the server.
- Inspecting the deployment with the CLI and Prefect UI.
- Starting an ad hoc flow run based on the deployment.

## Edit the flow

In the flow definition `leo_flow.py` that you created earlier, comment out or remove the last line `leonardo_dicapriflow("Leo")`, the call to the flow function. You don't need that anymore because Prefect will call it directly with the specified parameters when it executes the deployment.

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

## Build a deployment

To create a deployment from an existing flow script, there are just a few steps:

1. Use the `prefect deployment build` Prefect CLI command to build a deployment manifest and a deployment YAML file. These describe the files and settings needed to create your deployment.
1. If you needed to add customizations to the manifest or the deployment YAML file, you would do so now. 
1. Use the `prefect deployment apply` Prefect CLI command to create the deployment on the API based on the settings in the deployment manifest and deployment YAML.

What you need for the first step, building the deployment artifacts, is:

- The path and filename of the flow script
- The name of the flow function that is the entrypoint to the flow
- A name for the deployment

So to build deployment files for `leo_flow.py`, we'll use the command:

<div class="terminal">
```bash
$ prefect deployment build ./leo_flow.py:leonardo_dicapriflow -n leo-deployment -t test
```
</div>

What did we do here? Let's break down the command:

- `prefect deployment build` is the Prefect CLI command that enables you to prepare the settings for a deployment.
-  `./leo_flow.py:leonardo_dicapriflow` specifies the location of the flow script file and the name of the entrypoint flow function, separated by a colon.
- `-n leo-deployment` is an option to specify a name for the deployment.
- `-t test` specifies a tag for the deployment. Tags enable filtering deployment flow runs in the UI and on work queues. 

Note that you may specify multiple tags by providing a `-t tag` parameter for each tag you want applied to the deployment.

The command outputs two files: `leonardo_dicapriflow-manifest.json` contains workflow-specific information such as the code location, the name of the entrypoint flow, and flow parameters. `leonardo_dicapriflow-deployment.yaml` contains details about the deployment for this flow.

<div class="terminal">
```bash
Found flow 'leonardo_dicapriflow'
Manifest created at
'/Users/terry/test/testflows/leo_flow/leonardo_dicapriflow-manifest.json'.
Deployment YAML created at '/Users/terry/test/testflows/leo_flow/leonardo_dicapriflow-deployment.yaml'.
```
</div>

## Configure the deployment

Note that our flow needs a `name` parameter, but we didn't specify one when building the deployment files.

Open the `leonardo_dicapriflow-deployment.yaml` file and add the parameter as `parameters: {'name':'Leo'}`:

```yaml hl_lines="9"
###
### A complete description of a Prefect Deployment for flow 'leonardo_dicapriflow'
###
name: leo-deployment
description: null
tags:
- test
schedule: null
parameters: {'name':'Leo'}
infrastructure:
  type: process
  env: {}
  labels: {}
  name: null
  command:
  - python
  - -m
  - prefect.engine
  stream_output: true
###
### DO NOT EDIT BELOW THIS LINE
###
flow_name: leonardo_dicapriflow
manifest_path: leonardo_dicapriflow-manifest.json
storage:
  type: local
  basepath: /Users/terry/test/testflows/leo_flow
parameter_openapi_schema:
  title: Parameters
  type: object
  properties:
    name:
      title: name
      type: string
  required:
  - name
  definitions: null
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
```bash
$ prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api
Set variable 'PREFECT_API_URL' to 'http://127.0.0.1:4200/api'
Updated profile 'default'
```
</div>

## Creating the deployment

Okay, let's get down to creating that deployment on the server we just started.

To review, we have three files that make up the artifacts for this particular deployment (there could be more if we had supporting libraries or modules, configuration, and so on).

- The flow code in `leo_flow.py`
- The manifest `leonardo_dicapriflow-manifest.json`
- The deployment settings `leonardo_dicapriflow-deployment.yaml`

Now use the `prefect deployment apply` command to create the deployment on the Prefect Orion server, specifying the name of the `leonardo_dicapriflow-deployment.yaml` file.

<div class="terminal">
```bash
$ prefect deployment apply leonardo_dicapriflow-deployment.yaml
Successfully loaded 'leo-deployment'
Deployment '3d2f55a2-46df-4857-ab6f-6cc80ce9cf9c' successfully created.
```
</div>

Now your deployment has been created by the Prefect API and is ready to create future `leonardo_dicapriflow` flow runs through the API.

To demonstrate that your deployment exists, list all of the current deployments:

<div class="terminal">
```bash
$ prefect deployment ls
                                Deployments
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Name                                ┃ ID                                   ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Testing/test-deployment             │ 66b3fdea-cd3a-4734-b3f2-65f6702ff260 │
│ leonardo_dicapriflow/leo-deployment │ 3d2f55a2-46df-4857-ab6f-6cc80ce9cf9c │
└─────────────────────────────────────┴──────────────────────────────────────┘
```
</div>

Use `prefect deployment inspect` to display details for a specific deployment.

<div class='terminal'>
```bash
$ prefect deployment inspect leonardo_dicapriflow/leo-deployment
{
    'id': '3d2f55a2-46df-4857-ab6f-6cc80ce9cf9c',
    'created': '2022-07-27T00:50:09.624876+00:00',
    'updated': '2022-07-27T00:50:09.618444+00:00',
    'name': 'leo-deployment',
    'description': None,
    'flow_id': 'f873de7b-092b-47e1-8ec7-cede232d88be',
    'schedule': None,
    'is_schedule_active': True,
    'parameters': {'name': 'Leo'},
    'tags': ['test'],
    'parameter_openapi_schema': {
        'title': 'Parameters',
        'type': 'object',
        'properties': {'name': {'title': 'name', 'type': 'string'}},
        'required': ['name']
    },
    'manifest_path': 'leonardo_dicapriflow-manifest.json',
    'storage_document_id': '31fe2cf5-5e3f-4dfc-982b-8bf2406ae992',
    'infrastructure_document_id': 'b253ee61-0e11-4b71-ac28-110d2c9decb0',
    'infrastructure': {
        'type': 'process',
        'env': {},
        'labels': {},
        'name': None,
        'command': ['python', '-m', 'prefect.engine'],
        'stream_output': True
    }
}
```
</div>

## Work queues and agents

Note that you can't **Run** the deployment from the UI yet. As mentioned at the beginning of this tutorial, you still need two more items to run orchestrated deployments: a work queue and an agent. You'll set those up next.

[Work queues and agents](/concepts/work-queues/) are the mechanisms by which the Prefect API orchestrates deployment flow runs in remote execution environments.

Work queues let you organize flow runs into queues for execution. Agents pick up work from queues and execute the flows.

There is no default global work queue or agent, so to orchestrate runs of `leonardo_dicapriflow` you need to configure a work queue and agent. 

Next, create a work queue that can distribute your new deployment to agents for execution, and a local agent to pick up the flow run for your 'leonardo_dicapriflow/leonardo-deployment' deployment. 

In the Prefect UI, you can create a work queue by selecting the **Work Queues** page, then creating a new work queue. 

However, we can also use a Prefect CLI convenience command: starting your agent with a set of tags will automatically create a work queue for you that serves deployments with those tags. This is handy for quickly standing up a test environment, for example.

In your terminal, run the `prefect agent start` command, passing a `-t test` option that creates a work queue for `test` tags. Remember, we configured this same tag on the deployment at an earlier step.

<div class="terminal">
```bash
$ prefect agent start -t test
Starting agent connected to http://127.0.0.1:4200/api...

  ___ ___ ___ ___ ___ ___ _____     _   ___ ___ _  _ _____
 | _ \ _ \ __| __| __/ __|_   _|   /_\ / __| __| \| |_   _|
 |  _/   / _|| _|| _| (__  | |    / _ \ (_ | _|| .` | | |
 |_| |_|_\___|_| |___\___| |_|   /_/ \_\___|___|_|\_| |_|


Agent started! Looking for work from queue 'Agent queue test'...
```
</div>

Remember that:

- We specified the `test` tag when building the deployment files.
- The 'Agent queue test' work queue is defined to serve deployments with a `test` tag.
- The agent is configured to pick up work from the 'Agent queue test' work queue, so it will only execute flow runs for deployments with a `test` tag.

!!! note "Reference work queues by name or ID"
    You can reference a work queue by either ID or by name when starting an agent to pull work from a queue. For example: `prefect agent start 'tutorial_queue'`.

    Note, however, that you can edit the name of a work queue after creation, which may cause errors for agents referencing a work queue by name.

## Run the deployment locally

Now that you've created the deployment, agent, and associated work queue, you can interact with it in multiple ways. For example, you can use the Prefect CLI to run a local flow run for the deployment.

<div class="terminal">
```bash
$ prefect deployment run leonardo_dicapriflow/leo-deployment
Created flow run 'crazy-fossa' for flow 'leonardo_dicapriflow'
```
</div>

If you switch over to the terminal session where your agent is running, you'll see that the agent picked up the flow run and executed it.

<div class="terminal">
```bash
Loading flow from deployed location...
21:03:10.220 | INFO    | Flow run 'crazy-fossa' - Starting 'ConcurrentTaskRunner'; submitted tasks will be run concurrently...
21:03:10.387 | INFO    | Flow run 'crazy-fossa' - Created task run 'log_message-3e2d0b0c-0' for task 'log_message'
21:03:10.387 | INFO    | Flow run 'crazy-fossa' - Executing 'log_message-3e2d0b0c-0' immediately...
21:03:10.413 | INFO    | Task run 'log_message-3e2d0b0c-0' - Hello Leo!
21:03:10.484 | INFO    | Task run 'log_message-3e2d0b0c-0' - Finished in state Completed()
21:03:10.514 | INFO    | Flow run 'crazy-fossa' - Finished in state Completed('All states completed.')
Flow run completed!
```
</div>

When you executed the deployment, you referenced it by name in the format "flow_name/deployment_name". When you create new deployments in the future, remember that while a flow may be referenced by multiple deployments, each deployment must have a unique name.

You can also see your flow in the [Prefect UI](/ui/overview/). Open the Prefect UI at [http://127.0.0.1:4200/](http://127.0.0.1:4200/). You'll see your deployment's flow run in the UI.

![Deployment flow run on the Flow Runs page of the Prefect UI](/img/tutorials/my-first-deployment.png)

## Run a deployment from the UI

With a work queue and agent in place, you can also create a flow run for `leonardo_dicapriflow` directly from the UI.

In the Prefect UI, select the **Deployments** page. You'll see a list of all deployments that have been created in this Prefect Orion instance.

![The Deployments page displays a list of deployments created in Prefect](/img/tutorials/orion-deployments.png)

Now select **leonardo_dicapriflow/leonardo-deployment** to see details for the deployment you just created.

![Viewing details of a single deployment](/img/tutorials/deployment-details.png)

You can start a flow run for this deployment from the UI by selecting the **Run** button. The Prefect Orion engine routes the flow run request to the work queue, the agent picks up the new work from the queue and initiates the flow run. 

As before, the flow run will be picked up by the agent, and you should be able to see it run in the agent process.

<div class='terminal'>
```bash
21:26:47.911 | INFO    | prefect.agent - Submitting flow run '210ed779-9b95-4226-8a17-060e7942d046'
21:26:48.010 | INFO    | prefect.infrastructure.process - Opening process 'mustard-akita'...
21:26:48.031 | INFO    | prefect.agent - Completed submission of flow run '210ed779-9b95-4226-8a17-060e7942d046'
21:26:49.973 | INFO    | Flow run 'mustard-akita' - Starting 'ConcurrentTaskRunner'; submitted tasks will be run concurrently...
21:26:50.127 | INFO    | Flow run 'mustard-akita' - Created task run 'log_message-3e2d0b0c-0' for task 'log_message'
21:26:50.128 | INFO    | Flow run 'mustard-akita' - Executing 'log_message-3e2d0b0c-0' immediately...
21:26:50.157 | INFO    | Task run 'log_message-3e2d0b0c-0' - Hello Leo!
21:26:50.186 | INFO    | Task run 'log_message-3e2d0b0c-0' - Finished in state Completed()
21:26:50.223 | INFO    | Flow run 'mustard-akita' - Finished in state Completed('All states completed.')
21:26:50.495 | INFO    | prefect.infrastructure.process - Process 'mustard-akita' exited cleanly.
```
</div>

Go back the the **Flow Runs** page in the UI and you'll see the flow run you just initiatied ran and was observed by the API.

![The deployment flow run is shown in the UI run history](/img/tutorials/deployment-run.png)

Click the flow run to see details. In the flow run logs, you can see that the flow run logged a "Hello Leo!" message as expected.

![The flow run logs show the expected Hello Leo! log message](/img/tutorials/dep-flow-logs.png)

## Next steps

So far you've seen a simple example of a single deployment for a single flow. But a common and useful pattern is to create multiple deployments for a flow. By using tags, parameters, and schedules effectively, you can have a single flow definition that serves multiple purposes or can be configured to run in different environments.

## Cleaning up

You're welcome to leave the work queue and agent running to experiment and to handle local development.

To terminate the agent, simply go to the terminal session where it's running and end the process with either `Ctrl+C` or by terminating the terminal session.

You can pause or delete a work queue on the Prefect UI **Work Queues** page.

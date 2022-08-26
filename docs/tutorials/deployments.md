---
description: Learn how to create Prefect flow deployments and run them with agents and work queues.
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
- An [agent and work queue](/concepts/work-queues/).

These all come with Prefect. You just have to configure them and set them to work. You'll see how to configure each component during this tutorial.

Optionally, you can configure [storage](/concepts/storage/) for packaging and saving your flow code and dependencies. 

## Setting up

First, create a new folder that will contain all of the files and dependencies needed by your flow deployment. This is a best practice for developing and deploying flows.

<div class="terminal">
```bash
$ mkdir prefect-tutorial
$ cd prefect-tutorial
```
</div>

You may organize your flow scripts and dependencies in any way that suits for team's needs and standards. For this tutorial, we'll keep files within this directory.

## From flow to deployment

As noted earlier, the first ingredient of a deployment is a flow script. You've seen a few of these already, and perhaps have written a few, if you've been following the tutorials. 

Let's start with a simple example. This flow contains a single flow function `log_flow()`, and a single task `log_task` that logs messages based on a parameter input and your installed Prefect version:

```python
import prefect
from prefect import flow, task, get_run_logger

@task
def log_task(name):
    logger = get_run_logger()
    logger.info("Hello %s!", name)
    logger.info("Prefect Version = %s 🚀", prefect.__version__)

@flow()
def log_flow(name: str):
    log_task(name)

log_flow("Marvin")
```

Save this in a file `log_flow.py` and run it as a Python script. You'll see output like this:

<div class="terminal">
```bash
$ python log_flow.py
22:00:16.419 | INFO    | prefect.engine - Created flow run 'vehement-eagle' for flow 'log-flow'
22:00:16.570 | INFO    | Flow run 'vehement-eagle' - Created task run 'log_task-82fbd1c0-0' for task 'log_task'
22:00:16.570 | INFO    | Flow run 'vehement-eagle' - Executing 'log_task-82fbd1c0-0' immediately...
22:00:16.599 | INFO    | Task run 'log_task-82fbd1c0-0' - Hello Marvin!
22:00:16.600 | INFO    | Task run 'log_task-82fbd1c0-0' - Prefect Version = 2.1.0 🚀
22:00:16.626 | INFO    | Task run 'log_task-82fbd1c0-0' - Finished in state Completed()
22:00:16.659 | INFO    | Flow run 'vehement-eagle' - Finished in state Completed('All states completed.')
```
</div>

Like previous flow examples, this is still a script that you have to run locally. 

In the this tutorial, you'll use this flow script to create a deployment on the Prefect API. With a deployment, you can trigger ad-hoc flow runs. You could also schedule automatic flow runs that run on remote infrastructure. 

You'll create the deployment for this flow by doing the following: 

- Build a deployment YAML file that specifies settings for flow runs.
- Copy the flow script to a specified storage location from which it can be retrieved for API-triggered flow runs.
- Apply the deployment YAML settings to create a deployment on the Prefect API.
- Inspect the deployment with the Prefect CLI and Prefect UI.
- Start an ad hoc flow run based on the deployment.

## Edit the flow

In the flow definition `log_flow.py` that you created earlier, comment out or remove the last line `log_flow("Marvin")`, the call to the flow function. You don't need that anymore because Prefect will call it directly with the specified parameters when it executes your deployment.

```python hl_lines="14"
import prefect
from prefect import flow, task, get_run_logger

@task
def log_task(name):
    logger = get_run_logger()
    logger.info("Hello %s!", name)
    logger.info("Prefect Version = %s 🚀", prefect.__version__)

@flow()
def log_flow(name: str):
    log_task(name)

# log_flow("Marvin")
```

## Deployment creation steps

To create a deployment from an existing flow script, there are just a few steps:

1. Use the `prefect deployment build` Prefect CLI command to build a deployment definition YAML file that settings needed to create your deployment and execute flow runs from it. This step also uploads your flow script and any supporting files to storage, if you've specified storage for the deployment.
1. Optionally, you can edit the deployment YAML file to include additional settings that are not easily specified via CLI flags. 
1. Use the `prefect deployment apply` Prefect CLI command to create the deployment with the Prefect Orion server based on the settings in the deployment YAML file.

!!! tip "Ignoring files with `.prefectignore`"
    `prefect deployment build` automatically uploads your flow script and any supporting files in the same folder to storage, if you've specified storage for the deployment.

    To exclude files from being uploaded, you can create a `.prefectignore` file in the folder alongside your flow script. `.prefectignore` enables you to specify files that should be ignored by the deployment creation process. The syntax follows [`.gitignore`](https://git-scm.com/docs/gitignore) patterns.

    `.prefectignore` is preconfigured with common artifacts from Python, environment managers, operating system, and other applications that you probably don't want included in flows uploaded to storage. 

    It's also a good flow development practice to store flow files and their dependencies in a folder structure that helps ensure only the files needed to execute flow runs are uploaded to storage.

## Build a deployment definition

What you need for the first step, building the deployment artifacts, is:

- The path and filename of the flow script.
- The name of the flow function that is the entrypoint to the flow.
- A name for the deployment.

!!! note "Entrypoint flow function"
    What do we mean by "entrypoint" flow function?

    A flow script file may contain definitions for multiple flow (`@flow`) and task (`@task`) functions. The entrypoint flow is the flow function that is called to _begin the workflow_, and other task and flow functions may be called from that entrypoint flow to complete your workflow. 

You can provide additional settings &mdash; we'll demonstrate that in a future step &mdash; but this is the minimum required information to create a deployment.

To build deployment files for `log_flow.py`, use the following command:

<div class="terminal">
```bash
$ prefect deployment build ./log_flow.py:log_flow -n log-simple -q test
```
</div>

What did we do here? Let's break down the command:

- `prefect deployment build` is the Prefect CLI command that enables you to prepare the settings for a deployment.
-  `./log_flow.py:log_flow` specifies the location of the flow script file and the name of the entrypoint flow function, separated by a colon.
- `-n log-simple` specifies a name for the deployment.
- `-q test` specifies a work queue for the deployment. Work queues direct scheduled runs to agents.

You can pass other option flags. For example, you may specify multiple tags by providing a `-t tag` parameter for each tag you want applied to the deployment. Options are described in the [Deployments](/concepts/deployments/#deployment-build-options) documentation or via the `prefect deployment build --help` command.

What happens when you run `prefect deployment build`? 

<div class="terminal">
```bash
$ prefect deployment build ./log_flow.py:log_flow -n log-simple -q test
Found flow 'log-flow'
Default '.prefectignore' file written to
/Users/terry/prefect-tutorial/.prefectignore
Deployment YAML created at
'/Users/terry/prefect-tutorial/log_flow-deployment.yaml'.
```
</div>

First, the `prefect deployment build` command checks that a valid flow script and entrypoint flow function exist before continuing.

Next, since we don't have one already in the folder, the command writes a `.prefectignore` file to the same location as the flow script. 

If we had specified storage flow the flow, the command would next have uploaded files to the storage location. Since we did not specify storage, the deployment references the local files. We'll cover differences between using local storage and configuring a [remote storage block](/concepts/storage/) in a later step.

Finally, it writes a `log_flow-deployment.yaml` file, which contains details about the deployment for this flow.

You can list the contents of the folder to see what we have at this step in the deployment process:

<div class="terminal">
```bash
~/prefect-tutorial $ ls -a
./                        .prefectignore            log_flow-deployment.yaml
../                       __pycache__/              log_flow.py
```
</div>

## Configure the deployment

Note that the flow needs a `name` parameter, but we didn't specify one when building the `deployment.yaml` file. To make sure flow runs based on this deployment have a default `name` parameter, we'll add one to the deployment definition.

Open the `log_flow-deployment.yaml` file and edit the parameters to include a default as `parameters: {'name':'Marvin'}`:

```yaml hl_lines="10"
###
### A complete description of a Prefect Deployment for flow 'log-flow'
###
name: log-simple
description: null
version: 450637a8874a5dd3a81039a89e90c915
# The work queue that will handle this deployment's runs
work_queue_name: test
tags: []
parameters: {'name':'Marvin'}
schedule: null
infra_overrides: {}
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
flow_name: log-flow
manifest_path: null
storage: null
path: /Users/terry/test/dplytest/prefect-tutorial
entrypoint: log_flow.py:log_flow
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

Note that the YAML configuration includes the ability to add a description, a default work queue, tags, a schedule, and more. 

## Run a Prefect Orion server

For this tutorial, you'll use a local Prefect Orion server. Open another terminal session and start the Prefect Orion server with the `prefect orion start` CLI command:

<div class='terminal'>
```bash
$ prefect orion start

 ___ ___ ___ ___ ___ ___ _____    ___  ___ ___ ___  _  _
| _ \ _ \ __| __| __/ __|_   _|  / _ \| _ \_ _/ _ \| \| |
|  _/   / _|| _|| _| (__  | |   | (_) |   /| | (_) | .` |
|_| |_|_\___|_| |___\___| |_|    \___/|_|_\___\___/|_|\_|

Configure Prefect to communicate with the server with:

    prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api

View the API reference documentation at http://127.0.0.1:4200/docs

Check out the dashboard at http://127.0.0.1:4200



INFO:     Started server process [84832]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:4200 (Press CTRL+C to quit)
```
</div>

Note the message to set `PREFECT_API_URL` so that you're coordinating flows with this API instance.

Go back to your first terminal session and run this command to set the API URL:

<div class='terminal'>
```bash
$ prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api
Set variable 'PREFECT_API_URL' to 'http://127.0.0.1:4200/api'
Updated profile 'default'
```
</div>

## Apply the deployment

Okay, let's get down to creating that deployment on the server we just started.

To review, we have three files that make up the artifacts for this particular deployment (there could be more if we had supporting libraries or modules, configuration, and so on).

- The flow code in `log_flow.py`
- The ignore file `.prefectignore`
- The deployment definition in `log_flow-deployment.yaml`

Now we can _apply_ the settings in `log_flow-deployment.yaml` to create the deployment object on the Prefect Orion server API &mdash; or on a [Prefect Cloud workspace](/ui/cloud-getting-started/) if you had configured the Prefect Cloud API as your backend. 

Use the `prefect deployment apply` command to create the deployment on the Prefect Orion server, specifying the name of the `log_flow-deployment.yaml` file.

<div class="terminal">
```bash
$ prefect deployment apply log_flow-deployment.yaml
Successfully loaded 'log-simple'
Deployment 'log-flow/log-simple' successfully created with id
'517fd294-2bd3-4738-9515-0c68092ce35d'.

To execute flow runs from this deployment, start an agent that pulls work from the the 'test'
work queue:
$ prefect agent start -q 'test'
```
</div>

Now your deployment has been created by the Prefect API and is ready to create future `log_flow` flow runs through the API.

To demonstrate that your deployment exists, list all of the current deployments:

<div class="terminal">
```bash
$ prefect deployment ls
                                Deployments
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Name                                ┃ ID                                   ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ hello-flow/example-deployment       │ 60a6911e-1125-4a33-b37f-3ba16b86837d │
│ leonardo_dicapriflow/leo-deployment │ 3d2f55a2-46df-4857-ab6f-6cc80ce9cf9c │
│ log-flow/log-simple                 │ 517fd294-2bd3-4738-9515-0c68092ce35d │
└─────────────────────────────────────┴──────────────────────────────────────┘
```
</div>

Use `prefect deployment inspect` to display details for a specific deployment.

<div class='terminal'>
```bash
$ prefect deployment inspect log-flow/log-simple
{
    'id': '517fd294-2bd3-4738-9515-0c68092ce35d',
    'created': '2022-08-22T20:06:54.719808+00:00',
    'updated': '2022-08-22T20:06:54.717511+00:00',
    'name': 'log-simple',
    'version': '450637a8874a5dd3a81039a89e90c915',
    'description': None,
    'flow_id': 'da22db55-0a66-4f2a-ae5f-e0b898529a8f',
    'schedule': None,
    'is_schedule_active': True,
    'infra_overrides': {},
    'parameters': {'name': 'Marvin'},
    'tags': [],
    'work_queue_name': 'test',
    'parameter_openapi_schema': {
        'title': 'Parameters',
        'type': 'object',
        'properties': {'name': {'title': 'name', 'type': 'string'}},
        'required': ['name']
    },
    'path': '/Users/terry/test/dplytest/prefect-tutorial',
    'entrypoint': 'log_flow.py:log_flow',
    'manifest_path': None,
    'storage_document_id': None,
    'infrastructure_document_id': '219341e5-0edb-474e-9df4-6c92122e56ce',
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

## Agents and work queues

Note that you can't **Run** the deployment from the UI yet. As mentioned at the beginning of this tutorial, you still need two more items to run orchestrated deployments: an agent and a work queue. You'll set those up next.

[Agents and work queues](/concepts/work-queues/) are the mechanisms by which the Prefect API orchestrates deployment flow runs in remote execution environments.

Work queues let you organize flow runs into queues for execution. Agents pick up work from queues and execute the flows.

There is no default global agent, so to orchestrate runs of `log_flow` you need to configure one. 

In the Prefect UI, you can create a work queue by selecting the **Work Queues** page, then creating a new work queue. However, you don't need to manually create a work queue because it was created automatically when you created your deployment. If you hadn't created your deployment yet, it would be created when you start your agent. 

Open an additional terminal session, then run the `prefect agent start` command, passing a `-q test` option that tells it to pull work from the `test` work queue. Remember, we configured the deployment to use this work queue at an earlier step.

<div class="terminal">
```bash
$ prefect agent start -q test
Starting agent connected to http://127.0.0.1:4200/api...

  ___ ___ ___ ___ ___ ___ _____     _   ___ ___ _  _ _____
 | _ \ _ \ __| __| __/ __|_   _|   /_\ / __| __| \| |_   _|
 |  _/   / _|| _|| _| (__  | |    / _ \ (_ | _|| .` | | |
 |_| |_|_\___|_| |___\___| |_|   /_/ \_\___|___|_|\_| |_|


Agent started! Looking for work from queue(s): test...
```
</div>

Remember that:

- We specified the `test` work queue when building the deployment files.
- The agent is configured to pick up work from the `test` work queue, so it will execute flow runs from the `log-flow/log-simple` deployment (and any others that also point at this queue).

## Run the deployment locally

Now that you've created the deployment, agent, and associated work queue, you can interact with it in multiple ways. For example, you can use the Prefect CLI to run a local flow run for the deployment.

<div class="terminal">
```bash
$ prefect deployment run log-flow/log-simple
Created flow run 'talented-jackdaw' (b0ba3195-912d-4a2f-8645-d939747655c3)
```
</div>

If you switch over to the terminal session where your agent is running, you'll see that the agent picked up the flow run and executed it.

<div class="terminal">
```bash
16:18:28.281 | INFO    | prefect.agent - Submitting flow run 'b0ba3195-912d-4a2f-8645-d939747655c3'
16:18:28.340 | INFO    | prefect.infrastructure.process - Opening process 'talented-jackdaw'...
16:18:28.349 | INFO    | prefect.agent - Completed submission of flow run 'b0ba3195-912d-4a2f-8645-d939747655c3'
16:18:30.282 | INFO    | Flow run 'talented-jackdaw' - Created task run 'log_task-99465d2b-0' for task 'log_task'
16:18:30.283 | INFO    | Flow run 'talented-jackdaw' - Executing 'log_task-99465d2b-0' immediately...
16:18:30.325 | INFO    | Task run 'log_task-99465d2b-0' - Hello Marvin!
16:18:30.325 | INFO    | Task run 'log_task-99465d2b-0' - Prefect Version = 2.1.1 🚀
16:18:30.354 | INFO    | Task run 'log_task-99465d2b-0' - Finished in state Completed()
16:18:30.432 | INFO    | Flow run 'talented-jackdaw' - Finished in state Completed('All states completed.')
16:18:30.654 | INFO    | prefect.infrastructure.process - Process 'talented-jackdaw' exited cleanly.
```
</div>

Note that we referenced the deployment by name in the format "flow_name/deployment_name". When you create new deployments in the future, remember that while a flow may be referenced by multiple deployments, each deployment must have a unique name.

You can also see your flow in the [Prefect UI](/ui/overview/). Open the Prefect UI at [http://127.0.0.1:4200/](http://127.0.0.1:4200/). You'll see your deployment's flow run in the UI.

![Deployment flow run on the Flow Runs page of the Prefect UI](/img/tutorials/my-first-deployment.png)

## Run a deployment from the UI

With a work queue and agent in place, you can also create a flow run for `leonardo_dicapriflow` directly from the UI.

In the Prefect UI, select the **Deployments** page. You'll see a list of all deployments that have been created in this Prefect Orion instance.

![The Deployments page displays a list of deployments created in Prefect](/img/tutorials/orion-deployments.png)

Now select **log-flow/log-simple** to see details for the deployment you just created.

![Viewing details of a single deployment](/img/tutorials/deployment-details.png)

Select **Parameters** to see the default parameters you specified in the deployment definition.

![Viewing deployment parameters](/img/tutorials/deployment-parameters.png)

You can start a flow run for this deployment from the UI by selecting the **Run** button, which gives you options to:

- Create a flow run with the default settings
- Create a flow run with custom settings

![Deployment run options in the UI](/img/tutorials/deployment-run-options.png)

If you choose a **Custom** flow run, you can configure details including:

- Flow run name
- A description of the run
- Tags
- Scheduled start time
- Custom parameters

![Configuring custom flow run settings](/img/tutorials/custom-flow-run.png)

Let's change the `name` parameter for the next flow run. Under **Parameters**, select **Custom**.

Change the value for the `name` parameter to some other value. We used "Trillian".

![Configuring custom flow run settings](/img/tutorials/custom-parameter.png)

Select **Save** to save any changed values, then select **Run** to create the custom flow run.

The Prefect Orion engine routes the flow run request to the work queue, the agent picks up the new work from the queue and initiates the flow run. 

As before, the flow run will be picked up by the agent, and you should be able to see it run in the agent process.

<div class='terminal'>
```bash
16:44:42.110 | INFO    | prefect.agent - Submitting flow run 'ceb0782a-1538-4dce-a32c-831d8d1cf0f6'
16:44:42.163 | INFO    | prefect.infrastructure.process - Opening process 'upsilon2-belfalas-manifold'...
16:44:42.172 | INFO    | prefect.agent - Completed submission of flow run 'ceb0782a-1538-4dce-a32c-831d8d1cf0f6'
16:44:45.166 | INFO    | Flow run 'upsilon2-belfalas-manifold' - Created task run 'log_task-99465d2b-0' for task 'log_task'
16:44:45.167 | INFO    | Flow run 'upsilon2-belfalas-manifold' - Executing 'log_task-99465d2b-0' immediately...
16:44:45.193 | INFO    | Task run 'log_task-99465d2b-0' - Hello Trillian!
16:44:45.193 | INFO    | Task run 'log_task-99465d2b-0' - Prefect Version = 2.1.1 🚀
16:44:45.219 | INFO    | Task run 'log_task-99465d2b-0' - Finished in state Completed()
16:44:45.251 | INFO    | Flow run 'upsilon2-belfalas-manifold' - Finished in state Completed('All states completed.')
16:44:45.480 | INFO    | prefect.infrastructure.process - Process 'upsilon2-belfalas-manifold' exited cleanly.
```
</div>

Go back the the **Flow Runs** page in the UI and you'll see the flow run you just initiatied ran and was observed by the API.

![The deployment flow run is shown in the UI run history](/img/tutorials/deployment-run.png)

Select the flow run to see details. In the flow run logs, you can see that the flow run logged a "Hello Trillian!" message as expected.

![The flow run logs show the expected Hello Trillian! log message](/img/tutorials/dep-flow-logs.png)

## Next steps

So far you've seen a simple example of a single deployment for a single flow. But a common and useful pattern is to create multiple deployments for a flow. By using tags, parameters, and schedules effectively, you can have a single flow definition that serves multiple purposes or can be configured to run in different environments.

## Cleaning up

You're welcome to leave the work queue and agent running to experiment and to handle local development.

To terminate the agent, simply go to the terminal session where it's running and end the process with either `Ctrl+C` or by terminating the terminal session.

You can pause or delete a work queue on the Prefect UI **Work Queues** page.

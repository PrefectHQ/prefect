---
description: Learn how to run Prefect flows in Docker containers using the Docker flow runner.
tags:
    - Docker
    - containers
    - orchestration
    - flow runners
    - DockerFlowRunner
    - tutorial
---

# Running flows in Docker

Prefect integrates with Docker via the [flow runner interface](/concepts/flow-runners/). The [DockerFlowRunner](/api-ref/prefect/flow-runners/#prefect.flow_runners.DockerFlowRunner) runs Prefect flows using [Docker containers](https://www.docker.com/resources/what-container).

In this tutorial we'll work through the steps you'll need to: 

- Create a simple flow that runs in a Docker container and logs a message.
- Create a deployment for the flow so you can run the flow via API.
- Configure the API URL, a work queue, and an agent to run deployments.

## Requirements

To run a deployed flow in a Docker container, you'll need the following:

- [Docker Engine](https://docs.docker.com/engine/) installed and running on the same machine as your agent.
- A remote [Storage](/concepts/storage/) configuration, not Local Storage or Temporary Local Storage.
- You must run a standalone Orion API server (`prefect orion start`).

[Docker Desktop](https://www.docker.com/products/docker-desktop) works fine for local testing if you don't already have Docker Engine configured in your environment.

You'll need to configure a remote store such as S3, Google Cloud Storage, or Azure Blob Storage. See the [Storage](/concepts/storage/) documentation for details. 

## A simple Docker deployment

We'll create a simple flow that simply logs a message, indicating that it ran in the Docker container. We'll include the [deployment specification](/concepts/deployments/#deployment-specifications) alongside the flow code. 

Save the following script to the file `docker-deployment.py`:

```python
from prefect import flow, get_run_logger
from prefect.deployments import DeploymentSpec
from prefect.flow_runners import DockerFlowRunner

@flow
def my_docker_flow():
    logger = get_run_logger()
    logger.info("Hello from Docker!")

DeploymentSpec(
    name="docker-example",
    flow=my_docker_flow,
    flow_runner=DockerFlowRunner()
)
```

Now use the Prefect CLI to create the deployment, passing the file containing the flow code and deployment specification, `docker-deployment.py`:

<div class='termy'>
```
$ prefect deployment create ./docker-deployment.py
Loading deployments from python script at 'docker-deployment.py'...
Created deployment 'docker-example' for flow 'my-docker-flow'
```
</div>

In future when we reference the deployment, we'll use the format "flow name/deployment name" &mdash; in this case, `my-docker-flow/docker-example`.

## Run Orion server

In a separate terminal, start the Prefect Orion server with the `prefect orion start` CLI command:

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

Note the message to set `PREFECT_API_URL` so that we're orchestrating flows with this API instance.

Open another terminal and run the command to set the API URL:

<div class='termy'>
```
$ prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api
Set variable 'PREFECT_API_URL' to 'http://127.0.0.1:4200/api'
Updated profile 'default'
```
</div>

## Configure storage

Now that we can communicate with the Orion API, lets configure [storage](/concepts/storage/) for flow and task run data. 

Before doing this next step, make sure you have the information to connect to and authenticate with a remote data store. In this example we're connecting to an AWS S3 bucket, but you could also Google Cloud Storage or Azure Blob Storage.

Run the `prefect storage create` command. In this case we choose the S3 option and supply the bucket name and AWS IAM access key.

<div class='termy'>
```
$ prefect storage create
Found the following storage types:
0) Azure Blob Storage
    Store data in an Azure blob storage container
1) Google Cloud Storage
    Store data in a GCS bucket
2) KV Server Storage
    Store data by sending requests to a KV server
3) Local Storage
    Store data in a run's local file system
4) S3 Storage
    Store data in an AWS S3 bucket
5) Temporary Local Storage
    Store data in a temporary directory in a run's local file system
Select a storage type to create: 4
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

We set this storage as the default that Orion will use for flows running in the Docker container. Any flow runs can use the persistent S3 storage for flow code, task results, and flow results rather than relying on local storage that will disappear when the container shuts down.

## Create a work queue and agent

Work queues organize work that agents can pick up to execute. Work queues can be configured to make available deployments based on criteria such as tags, flow runners, or even specific deployments. Agents are configured to poll for work from specific work queues. To learn more, see the [Work Queues & Agents](/concepts/work-queues/) documentation.

To run orchestrated deployments, you'll need to set up at least one work queue and agent. For this project we'll configure a work queue that works with any deployment and an agent that gets work from that queue.

In the terminal, use the `prefect work-queue create` command to create a work queue called "tut-work-queue". We don't pass any other options, so this work queue passes any scheduled flow runs to a waiting agent.

<div class='termy'>
```
$ prefect work-queue create tut-work-queue
UUID('00b05597-aeae-44d8-9b17-56dad9438333')
```
</div>

Note that the command returns the ID of the work queue (yours will be a different ID). Copy the ID: we need to provide this ID when we create an agent.

If you don't remember the ID of a work queue, use the `prefect work-queue ls` CLI command to list the available work queues.

Now use the `prefect agent start` command, passing the ID of the work queue you just created, to start an agent that polls for flow runs from that work queue.

```bash
$ prefect agent start '00b05597-aeae-44d8-9b17-56dad9438333'
Starting agent connected to http://127.0.0.1:4200/api...

  ___ ___ ___ ___ ___ ___ _____     _   ___ ___ _  _ _____
 | _ \ _ \ __| __| __/ __|_   _|   /_\ / __| __| \| |_   _|
 |  _/   / _|| _|| _| (__  | |    / _ \ (_ | _|| .` | | |
 |_| |_|_\___|_| |___\___| |_|   /_/ \_\___|___|_|\_| |_|


Agent started!
```

Now we're ready to run our deployed flow in Docker!

## Run the Docker deployment

Go back to the original terminal session, then use the `prefect deployment run` command to create a flow run for the `my-docker-flow/docker-example` deployment:

<div class='termy'>
```
$ prefect deployment run my-docker-flow/docker-example
Created flow run 'hulking-poodle' (d17584f1-9c7e-457d-89a3-8f8fac0e507b)
```
</div>

Look in the terminal session running the agent: you'll see the agent submit the flow run, then the flow runner create the container and execute the flow commands. You'll see a different flow run name and ID.

<div class='termy'>
```
17:14:54.901 | INFO    | prefect.agent - Submitting flow run 'd17584f1-9c7e-457d-89a3-8f8fac0e507b'
17:14:55.079 | INFO    | prefect.flow_runner.docker - Flow run 'hulking-poodle' has container settings = {'image': 'prefecthq/prefect:dev-python3.8', 'network': None, 'command': ['python', '-m', 'prefect.engine', 'd17584f1-9c7e-457d-89a3-8f8fac0e507b'], 'environment': {'PREFECT_API_URL': 'http://host.docker.internal:4200/api'}, 'auto_remove': False, 'labels': {'io.prefect.flow-run-id': 'd17584f1-9c7e-457d-89a3-8f8fac0e507b'}, 'extra_hosts': None, 'name': 'hulking-poodle', 'volumes': []}
17:14:55.512 | INFO    | prefect.agent - Completed submission of flow run 'd17584f1-9c7e-457d-89a3-8f8fac0e507b'
17:14:55.547 | INFO    | prefect.flow_runner.docker - Flow run container 'hulking-poodle' has status 'running'
22:14:58.870 | INFO    | Flow run 'hulking-poodle' - Using task runner 'ConcurrentTaskRunner'
22:14:59.685 | INFO    | Flow run 'hulking-poodle' - Finished in state Completed(None)
Hello from Docker!
17:15:00.193 | INFO    | prefect.flow_runner.docker - Flow run container 'hulking-poodle' has status 'exited'
```
</div>

Open the Prefect Orion UI at [http://127.0.0.1:4200](http://127.0.0.1:4200) and go to the **Logs** tab of your flow run. You should see the "Hello from Docker!" log message created by the flow running in the Docker container!

![Log messages from the deployment flow run.](/img/tutorials/docker-flow-log.png)

## Cleaning up

When you're finished, just close the Prefect Orion UI tab in your browser, and close the terminal sessions running the Prefect Orion server and agent.

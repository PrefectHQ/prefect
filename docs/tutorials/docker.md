---
description: Learn how to build Prefect deployments that create flow runs in Docker containers.
tags:
    - Docker
    - containers
    - orchestration
    - infrastructure
    - deployments
    - tutorial
---

# Running flows with Docker

In the [Deployments](/tutorials/deployments/) and [Storage and Infrastructure](/tutorials/storage/) tutorials, we looked at creating configuration that enables creating flow runs via the API and with code that was uploaded to a remotely accessible location.  

In this tutorial, we'll further configure the deployment so flow runs are executed in a Docker container. We'll run our Docker instance locally, but you can extend this tutorial to run it on remote machines. 

In this tutorial we'll: 

- Configure a Docker Container infrastructure block that enables creating flow runs in a container.
- Build and apply a new `log_flow.py` deployment that uses the new infrastructure block.
- Create a flow run from this deployment that spins up a Docker container and executes, logging a message.

## Prerequisites

To run a deployed flow in a Docker container, you'll need the following:

- We'll use the flow script and deployment from the [Deployments](/tutorials/deployments/) tutorial. 
- We'll also use the remote storage block created in the [Storage and Infrastructure](/tutorials/storage/) tutorial.
- You must run a standalone Prefect Orion API server (`prefect orion start`) or use Prefect Cloud.
- You'll need [Docker Engine](https://docs.docker.com/engine/) installed and running on the same machine as your agent.

[Docker Desktop](https://www.docker.com/products/docker-desktop) works fine for local testing if you don't already have Docker Engine configured in your environment.

!!! note "Run Prefect Orion server"
    This tutorial assumes you're already running a Prefect Orion server with `prefect orion start`, as described in the [Deployments](/tutorials/deployments/#run-a-prefect-orion-server) tutorial. 
    
    If you shut down the server from a previous tutorial, you can start it again by opening another terminal session and starting the Prefect Orion server with the `prefect orion start` CLI command.

## Create an infrastructure block

Most users will find it easiest to configure new infrastructure blocks through the Prefect Orion or Prefect Cloud UI. 

You can see any previously configured storage blocks by opening the Prefect UI and navigating to the **Blocks** page. To create a new infrastructure block, select the **+** button on this page. Prefect displays a page of available block types. Select **run-infrastructure** from the **Capability** list to filter just the infrastructure blocks.

![Viewing a list of infrastructure block types in the Prefect UI](/img/tutorials/infrastructure-blocks.png)

Use these base blocks to create your own infrastructure blocks containing the settings needed to run flows in your environment.

For this tutorial, find the **Docker Container** block, then select **Add +** to see the options for a Docker infrastructure block.

![Viewing a list of infrastructure block types in the Prefect UI](/img/tutorials/docker-infrastructure.png)

To configure this Docker Container block to run the `log_flow.py` deployment, we just need to add two pieces of information.

First, give the block a **Block Name**. We used "log-tutorial".

Second, we need to make sure the container includes any additional files, libraries, or configuration to run `log_flow.py`. By default, Prefect uses a preconfigured container that includes installations of Python and Prefect.

In the [Storage and Infrastructure](/tutorials/storage/) tutorial, recall that we needed to `pip install s3fs` the library for an S3 storage block. You'll need to include the same command in the configuration of the Docker Container infrastructure block. When the agent spins up a container for a flow run, it will know to install the `s3fs` package before starting the flow run.

As a convenience, we can use the [`EXTRA_PIP_PACKAGES` environment variable](/concepts/infrastructure/#installing-extra-dependencies-at-runtime) to install dependencies at runtime. If defined, `pip install ${EXTRA_PIP_PACKAGES}` is executed before the flow run starts.

In the **Env (Optional)** box, enter the following to specify that the `s3fs` package should be installed. Note that we use JSON formatting to specify the environment variable (key) and packages to install (value).

```json
{
  "EXTRA_PIP_PACKAGES": "s3fs"
}
```
If you defined a different type of storage block, such as Azure or GCS, you'll need to specify the relevant storage library. See the [Prerequisites section of the Storage tutorial](/tutorials/storage/#prerequisites) for details.

![Configuring a new Docker Container infrastructure block in the Prefect UI](/img/tutorials/docker-tutorial-block.png)

## Using infrastructure blocks with deployments

To use an infrastructure block when building a deployment, the process is similar to using a storage block. You can specify a custom infrastructure block to the `prefect deployment build` command with the `-ib` or `--infra-block` options, passing the type and name of the block in the in the format `type/name`, with `type` and `name` separated by a forward slash. 

- `type` is the type of storage block, such as `docker-container`, `kubernetes-job`, or `process`.
- `name` is the name you specified when creating the block.

The `prefect deployment build` command also supports specifying a built-in infrastructure type prepopulated with defaults by using the `--infra` or `-i` options and passing the name of the infrastructure type: `docker-container`, `kubernetes-job`, or `process`.

## Build a deployment with Docker infrastructure

To demonstrate using an infrastructure block, we'll create a new variation of the deployment for the `log_flow` example from the [deployments tutorial](/tutorials/deployments/). For this deployment, we'll include the following options to the `prefect deployment build` command:

- Use the storage block created in the [Storage and Infrastructure](/tutorials/storage/) tutorial by passing `-sb s3/log-test` or `--storage-block s3/log-test`.
- Use the infrastructure block created earlier by passing `-ib docker-container/log-tutorial` or `--infra-block docker-container/log-tutorial`.

<div class="terminal">
```bash
$ prefect deployment build ./log_flow.py:log_flow -n log-flow-docker -sb s3/log-test -ib docker-container/log-tutorial -q test -o log-flow-docker-deployment.yaml
Found flow 'log-flow'
Successfully uploaded 4 files to s3://bucket-full-of-sunshine/flows/test
Deployment YAML created at
'/Users/terry/prefect-tutorial/log-flow-docker-deployment.yaml'.
```
</div>

What did we do here? Let's break down the command:

- `prefect deployment build` is the Prefect CLI command that enables you to prepare the settings for a deployment.
-  `./log_flow.py:log_flow` specifies the location of the flow script file and the name of the entrypoint flow function, separated by a colon.
- `-n log-flow-docker` specifies a name for the deployment. For ease of identification, the name includes a reference to the Docker infrastructure.
- `-sb s3/log-test` specifies a storage block by type and name. If you used a different storage block type or block name, your command may be different.
- `-ib docker-container/log-tutorial` specifies an infrastructure block by type and name.
- `-q test` specifies a work queue for the deployment. Work queues direct scheduled runs to agents.
- `-o log-flow-docker-deployment.yaml` specifies the name for the deployment YAML file. We do this to create a new deployment file rather than overwriting the previous one.

## Apply the deployment

Now we can apply the deployment YAML to create the deployment on the API.

<div class="terminal">
```bash
$ prefect deployment apply log-flow-docker-deployment.yaml
Successfully loaded 'log-flow-docker'
Deployment 'log-flow/log-flow-docker' successfully created with id
'a52fe285-d646-4e57-affd-257acf92782a'.

To execute flow runs from this deployment, start an agent that pulls work from the 'test'
work queue:
$ prefect agent start -q 'test'
```
</div>

Open the Prefect UI at [http://127.0.0.1:4200/](http://127.0.0.1:4200/) and select the **Deployments** page. You'll see a list of all deployments that have been created in this Prefect Orion instance, including the new `log-flow/log-flow-docker` deployment.

![Viewing the new Docker deployment in the Prefect UI](/img/tutorials/docker-deployment.png)

## Edit the deployment in the UI

`log_flow` expects a runtime parameter for its greeting, and we didn't provide one as part of this deployment yet. We could edit `log-flow-docker-deployment.yaml` to add a parameter and apply the edited YAML to update the deployment on the API.

Instead, let's edit the deployment through the Prefect UI. Select **log-flow/log-flow-docker** to see the deployment's details.

![Viewing the Docker deployment details in the Prefect UI](/img/tutorials/docker-deployment-details.png)

Select the menu next to **Run**, then select **Edit** to edit the deployment.

Scroll down to the **Parameters** section and provide a value for the `name` parameter. We used "Ford Prefect" here. 

![Editing the Docker deployment details in the Prefect UI](/img/tutorials/edit-docker-deployment.png)

Select **Save** to save these changes to the deployment.

## Create a flow run in Docker

When you create flow runs from this deployment, the agent pulls the default Prefect Docker container, `pip installs` the prerequisites we specified, retrieves the flow script from remote storage, and starts the Prefect engine to execute the flow run.

Let's create a flow run for this deployment. The flow run will execute in a Docker container on your local machine.

!!! note "Run a Prefect agent"
    This tutorial assumes you're already running a Prefect agent with `prefect agent start`, as described in the [Deployments](/tutorials/deployments/#agents-and-work-queues) tutorial. 
    
    If you shut down the agent from a previous tutorial, you can start it again by opening another terminal session and starting the agent with the `prefect agent start -q test` CLI command. This agent pulls work from the `test` work queue created previously.

    Note also that the `PREFECT_API_URL` setting should be configured to point to the URL of your Prefect Orion server or Prefect Cloud.

    If you're running the agent in the same environment or machine as your server, it should already be set. If not, run this command to set the API URL to point at the Prefect Orion instance just started:

    <div class='terminal'>
    ```bash
    $ prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api
    Set variable 'PREFECT_API_URL' to 'http://127.0.0.1:4200/api'
    Updated profile 'default'
    ```
    </div>

    You can check the settings for your environment with the `prefect config view` CLI command.

    <div class='terminal'>
    ```bash
    # View current configuration
    $ prefect config view
    PREFECT_PROFILE='default'
    PREFECT_API_URL='http://127.0.0.1:4200/api' (from profile)
    ```
    </div>

On the deployment details page, select **Run**, then select **Now with defaults**. This creates a new flow run using the default parameters and other settings.

![Running the Docker deployment from the Prefect UI](/img/tutorials/run-docker-deployment.png)

Go to the terminal session running the Prefect agent. You should see logged output showing:

- The agent submitting the flow run.
- The Docker container being created.
- Installation of the storage library.
- The task run creating log messages.
- The flow run completing.
- The Docker container closing down.

<div class='terminal'>
```bash
23:19:52.252 | INFO    | prefect.agent - Submitting flow run '2d520993-3697-4105-987f-70398e2a65fe'
23:19:52.449 | INFO    | prefect.infrastructure.docker-container - Creating Docker container 'woodoo-peacock'...
23:19:53.034 | INFO    | prefect.agent - Completed submission of flow run '2d520993-3697-4105-987f-70398e2a65fe'
23:19:53.065 | INFO    | prefect.infrastructure.docker-container - Docker container 'woodoo-peacock' has status 'running'
+pip install s3fs
Collecting s3fs
  Downloading s3fs-2022.7.1-py3-none-any.whl (27 kB)
...
03:20:02.773 | INFO    | Flow run 'woodoo-peacock' - Created task run 'log_task-99465d2b-0' for task 'log_task'
03:20:02.774 | INFO    | Flow run 'woodoo-peacock' - Executing 'log_task-99465d2b-0' immediately...
03:20:02.808 | INFO    | Task run 'log_task-99465d2b-0' - Hello Ford Prefect!
03:20:02.808 | INFO    | Task run 'log_task-99465d2b-0' - Prefect Version = 2.2.0 🚀
03:20:02.837 | INFO    | Task run 'log_task-99465d2b-0' - Finished in state Completed()
03:20:02.869 | INFO    | Flow run 'woodoo-peacock' - Finished in state Completed('All states completed.')
23:20:03.410 | INFO    | prefect.infrastructure.docker-container - Docker container 'woodoo-peacock' has status 'exited'
```
</div>

In the Prefect Orion UI, go to the **Flow Runs** page and select the flow run. You should see the "Hello Ford Prefect!" log message created by the flow running in the Docker container!

![Log messages from the deployment flow run.](/img/tutorials/docker-flow-log.png)

## Cleaning up

When you're finished, just close the Prefect Orion UI tab in your browser, and close the terminal sessions running the Prefect Orion server and agent.

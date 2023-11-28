---
description: Run an worker and flows in the cloud with Azure Container Instances.
tags:
    - Docker
    - containers
    - workers
    - cloud
search:
  boost: 2
---

# Run a worker with Azure Container Instances

Microsoft Azure Container Instances (ACI) provides a convenient and simple service for quickly spinning up a Docker container that can host a Prefect Worker and execute flow runs.

## Prerequisites

To follow this quickstart, you'll need the following:

- A [Prefect Cloud account](/ui/cloud-quickstart/)
- A Prefect Cloud [API key](/ui/cloud-api-keys/) (Prefect Cloud organizations may use a [service account](/ui/service-accounts/) API key)
- A [Microsoft Azure account](https://portal.azure.com/)
- Azure CLI [installed](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) and [authenticated](https://learn.microsoft.com/en-us/cli/azure/authenticate-azure-cli)

## Set up an ACI work pool

Create an ACI work pool in Prefect using the following command:
<div class='terminal'>
```bash
prefect work-pool create --type azure-container-instance my-aci-pool
```
</div>

## Create a resource group

Like most Azure resources, ACI applications must live in a resource group. This example creates a resource group called `prefect-workers` in the `eastus` region:

<div class='terminal'>
```bash
az group create --name prefect-workers --location eastus
```
</div>

Feel free to change the group name or location to match your use case. You can also run `az account list-locations -o table` to see all available resource group locations for your account.

## Create the container instance

Prefect provides [pre-configured Docker images](/concepts/infrastructure/#docker-images) you can use to quickly stand up a container instance. These Docker images include Python and Prefect. For example, the image `prefecthq/prefect:2-latest` includes the latest release version of Prefect and Python.

To create the container instance, use the `az container create` command. This example shows the syntax, but you'll need to provide the correct values for `[ACCOUNT-ID]`,`[WORKSPACE-ID]`, `[API-KEY]`, and any dependencies you need to `pip install` on the instance. These options are discussed below.

<div class='terminal'>
```bash
az container create \
--resource-group prefect-workers \
--name prefect-worker-example \
--image prefecthq/prefect:2-latest \
--secure-environment-variables PREFECT_API_URL='https://api.prefect.cloud/api/accounts/[ACCOUNT-ID]/workspaces/[WORKSPACE-ID]' PREFECT_API_KEY='[API-KEY]' \
--command-line "/bin/bash -c 'pip install adlfs s3fs requests pandas; prefect worker start --install-policy always --with-healthcheck -p my-aci-pool'"
```
</div>

# TODO io107 remove
az container create \
--resource-group prefect-workers \
--name prefect-worker-example \
--image prefecthq/prefect:2-latest \
--secure-environment-variables PREFECT_API_URL='https://api.prefect.cloud/api/accounts/57e885cb-9468-420b-9dd1-f4907ac08f2a/workspaces/23c97e1c-69df-46e6-b283-aa00f179875e' PREFECT_API_KEY='pnu_2pPAp0uEDGViYjfPvATlTSL9nfYKv94l3ELG' \
--command-line "/bin/bash -c 'pip install adlfs s3fs requests pandas; prefect worker start --install-policy always --with-healthcheck -p my-aci-pool'"

When the container instance is running, go to Prefect Cloud and select the [**Work Pools** page](/ui/work-pools/). Select **my-aci-pool**, then select the **Queues** tab to see work queues configured on this work pool. When the container instance is running and the worker has started, the `default` work queue displays "Healthy" status. This work queue and worker are ready to execute deployments configured to run on the `default` queue.

![Prefect Cloud UI indicates a healthy work queue in the default work pool](/img/ui/healthy-work-queue.png)

!!! info "Workers and queues"
    The worker running in this container instance can now pick up and execute flow runs for any deployment configured to use the `default` queue on the `my-aci-pool` work pool.

### Container create options

Let's break down the details of the `az container create` command used here. 

The `az container create command` creates a new ACI container.

`--resource-group prefect-workers` tells Azure which resource group the new container is created in. Here, the examples uses the `prefect-workers` resource group created earlier.

`--name prefect-worker-example` determines the container name you will see in the Azure Portal. You can set any name you’d like here to suit your use case, but container instance names must be unique in your resource group.

`--image prefecthq/prefect:2-latest` tells ACI which Docker images to run. The script above pulls a public Prefect image from Docker Hub.
You can also build custom images and push them to a public container registry so ACI can access them. Or you can push your image to a private Azure Container Registry and use it to create a container instance.

`--secure-environment-variables` sets environment variables that are only visible from inside the container. They do not show up when viewing the container’s metadata. You'll populate these environment variables with a few pieces of information to [configure the execution environment](/ui/cloud-local-environment/#manually-configure-prefect-api-settings) of the container instance so it can communicate with your Prefect Cloud workspace:

- A Prefect Cloud [`PREFECT_API_KEY`]/concepts/settings/#prefect_api_key) value specifying the API key used to authenticate with your Prefect Cloud workspace. (Prefect Cloud organizations may use a [service account](/ui/service-accounts/) API key.)
- The [`PREFECT_API_URL`](/concepts/settings/#prefect_api_url) value specifying the API endpoint of your Prefect Cloud workspace.

`--command-line` lets you override the container’s normal entry point and run a command instead. The script above uses this section to install the `adlfs` pip package so it can read flow code from Azure Blob Storage, along with `s3fs`, `pandas`, and `requests`. It then runs the Prefect worker, in this case using the `my-aci-pool` work pool we created above and the `default` work queue. If you want to use a different work pool or queue, make sure to change these values appropriately.

## Create a deployment

Following the example of the [Flow deployments](/tutorial/deployments/) tutorial, let's create a deployment that can be executed by the agent on this container instance.

In an environment where you have [installed Prefect](/getting-started/installation/), create a new folder called `health_test`, and within it create a new file called `health_flow.py` containing the following code.


```python
import prefect
from prefect import task, flow
from prefect import get_run_logger


@task
def say_hi():
    logger = get_run_logger()
    logger.info("Hello from the Health Check Flow! 👋")


@task
def log_platform_info():
    import platform
    import sys
    from prefect.server.api.server import SERVER_API_VERSION

    logger = get_run_logger()
    logger.info("Host's network name = %s", platform.node())
    logger.info("Python version = %s", platform.python_version())
    logger.info("Platform information (instance type) = %s ", platform.platform())
    logger.info("OS/Arch = %s/%s", sys.platform, platform.machine())
    logger.info("Prefect Version = %s 🚀", prefect.__version__)
    logger.info("Prefect API Version = %s", SERVER_API_VERSION)


@flow(name="Health Check Flow")
def health_check_flow():
    hi = say_hi()
    log_platform_info(wait_for=[hi])
```

# TODO io107 https://docs.prefect.io/latest/guides/upgrade-guide-agents-to-workers/#whats-different
Now create a deployment for this flow script, making sure that it's configured to use the `test` queue on the `default-agent-pool` work pool.

```bash
prefect deployment build --infra process --storage-block azure/flowsville/health_test --name health-test --pool default-agent-pool --work-queue test --apply health_flow.py:health_check_flow
```

Once created, any flow runs for this deployment will be picked up by the agent running on this container instance.

!!! note "Infrastructure and storage"
    This Prefect deployment example was built using the [`Process`](/concepts/infrastructure/#process) infrastructure type and Azure Blob Storage. 

    You might wonder why your deployment needs process infrastructure rather than [`DockerContainer`](/concepts/infrastructure/#dockercontainer) infrastructure when you are deploying a Docker image to ACI.

    A Prefect deployment’s infrastructure type describes how you want Prefect workers to run flows for the deployment. With `DockerContainer` infrastructure, the agent will try to use Docker to spin up a new container for each flow run. Since you’ll be starting your own container on ACI, you don’t need Prefect to do it for you. Specifying process infrastructure on the deployment tells Prefect you want to agent to run flows by starting a process in your ACI container.

    You can use any storage type as long as you've configured a block for it before creating the deployment.

## Cleaning up

Note that ACI instances may incur usage charges while running, but must be running for the worker to pick up and execute flow runs.

To stop a container, use the `az container stop` command:

<div class='terminal'>
```bash
az container stop --resource-group prefect-workers --name prefect-worker-example
```
</div>

To delete a container, use the `az container delete` command:

<div class='terminal'>
```bash
az container delete --resource-group prefect-workers --name prefect-worker-example
```
</div>
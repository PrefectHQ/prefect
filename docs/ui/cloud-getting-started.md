---
description: Get started using Prefect Cloud, including creating a workspace and running a flow deployment.
tags:
    - UI
    - dashboard
    - Prefect Cloud
    - accounts
    - teams
    - workspaces
    - tutorial
    - getting started
---

# Getting Started with Prefect Cloud

The following sections will get you set up and using Prefect Cloud, using these steps:

1. [Sign in or register](#sign-in-or-register) a Prefect Cloud account.
2. [Create workspaces](#create-a-workspace) for your account.
3. [Create an API key](#create-an-api-key) to authorize a local execution environment.
4. [Configure Orion settings](#configure-orion-for-cloud) to use Prefect Cloud.
5. [Configure storage](#configure-storage).
6. [Run a flow](#run-a-flow-with-cloud) and view flow results in Prefect Cloud.

## Sign in or register

To sign in with an existing account or register an account, go to [https://beta.prefect.io/](https://beta.prefect.io/).

You can create an account with:

- Google account
- GitHub account
- Email and password

## Create a workspace

A workspace is an isolated environment within Prefect Cloud for your flows and deployments. You can use workspaces to organize or compartmentalize your workflows. For example, you can create separate workspaces to isolate development, staging, and production environments; or to provide separation between different teams.

When you register a new account, you'll be prompted to create a workspace.  

![Creating a new Prefect Cloud account.](/img/ui/cloud-new-login.png)

Select **Create Workspace**. You'll be prompted to provide a name and description for your workspace.

![Creating a new workspace in the Cloud UI.](/img/ui/cloud-workspace-details.png)

Select **Save** to create the workspace. 

![Viewing a workspace dashboard in the Prefect Cloud UI.](/img/ui/cloud-new-workspace-full.png)

If you change your mind, you can select **Workspace Settings** to modify the workspace details or to delete it. 

!!! warning "Deleting a workspace"
    Deleting a workspace removes any flows, deployments, and storage created on that workspace.

## Create an API key

API keys enable you to authenticate an a local environment to work with Prefect Cloud. See [Configure execution environment](#configure-execution-environment) for details on how API keys are configured in your execution environment.

To create an API key, select the account icon at the bottom-left corner of the UI and select **Settings**. This displays your account profile.

Select the **API Keys** tab. This displays a list of previously generated keys and lets you create new API keys or delete keys.

![Viewing and editing API keys in the Cloud UI.](/img/ui/cloud-api-keys.png)

Select the **+** button to create a new API key. You're prompted to provide a name for the key and, optionally, an expiration. Select **Create API Key** to generate the key.

![Creating an API key in the Cloud UI.](/img/ui/cloud-new-api-key.png)

Note that API keys cannot be revealed again in the UI after you generate them, so copy the key to a secure location.

## Configure execution environment

Now configure a local execution environment to use Prefect Cloud as the API server for flow runs.

First, [Install Prefect](/getting-started/installation/) in the environment in which you want to execute flow runs.

Next, use the Prefect CLI `prefect cloud login` command to log into Prefect Cloud from your environment, using the [API key](#create-an-api-key) generated previously.

<div class="terminal">
```bash
$ prefect cloud login --key xxx_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```
</div>

The command prompts you to choose a workspace if you haven't given one (you can specify a workspace with the `-w` or `--workspace` option).

<div class="terminal">
```bash
$ prefect cloud login --key xxx_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
┏━━━━━━━━━━━━━━━━━━━━━━┓
┃  Select a Workspace: ┃
┡━━━━━━━━━━━━━━━━━━━━━━┩
│ > prefect/workinonit │
└──────────────────────┘
Successfully logged in and set workspace to 'prefect/workinonit' in profile 'default'.
```
</div>

The command then sets `PREFECT_API_KEY` and `PREFECT_API_URL` for the current profile.

Now you're ready to run flows locally and have the results displayed in the Prefect Cloud UI.

The `prefect cloud logout` CLI command unsets those settings in the current profile, logging the environment out of interaction with Prefect Cloud.

### Manually configuring Cloud settings

Note that you can also manually configure the settings to interact with Prefect Cloud using an account ID, workspace ID, and API key.

<div class="terminal">
```bash
$ prefect config set PREFECT_API_URL="https://beta.prefect.io/api/accounts/[ACCOUNT-ID]/workspaces/[WORKSPACE-ID]"
$ prefect config set PREFECT_API_KEY="[API-KEY]"
```
</div>

When you're in a Prefect Cloud workspace, you can copy the API URL directly from the page URL.

In this example, we configured `PREFECT_API_URL` and `PREFECT_API_KEY` in the default profile. You can use `prefect profile` CLI commands to create settings profiles for different configurations. For example, you could have a "cloud" profile configured to use the Prefect Cloud API URL and API key, and another "local" profile for local development using a local Prefect API server started with `prefect orion start`. See [Settings](/concepts/settings/) for details.

## Configure storage 

When using Prefect Cloud, we recommend configuring remote storage for persisting flow and task data. See [Storage](/concepts/storage/) for details.

By default, Prefect uses local file system storage to persist flow code and flow and task results. For local development and testing this may be adequate. Be aware, however, that local storage is not guaranteed to persist data reliably between flow or task runs, particularly when using container-based environments such as Docker or Kubernetes, or running tasks with distributed computing tools like Dask and Ray.

Before doing this next step, make sure you have the information needed to connect to and authenticate with a remote data store. In this example we're connecting to an AWS S3 bucket, but you could also Google Cloud Storage or Azure Blob Storage.

In the same terminal you just used to log into Prefect Cloud, run the `prefect storage create` command. In this case we choose the `S3 Storage` option and supply the bucket name and AWS IAM access key ID and secret access key. You should use the details of a service and authentication method that you have previously configured.

<div class='terminal'>
```bash
$ prefect storage create
Found the following storage types:
0) Azure Blob Storage
    Store data in an Azure blob storage container.
1) File Storage
    Store data as a file on local or remote file systems.
2) Google Cloud Storage
    Store data in a GCS bucket.
3) Local Storage
    Store data in a run's local file system.
4) S3 Storage
    Store data in an AWS S3 bucket.
5) Temporary Local Storage
    Store data in a temporary directory in a run's local file system.
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

Note that the storage parameters differ between storage types. See the [Storage](/concepts/storage/) documentation for details on parameters for storage types.

## Run a flow with Prefect Cloud

Okay, you're all set to run a local flow with Prefect Cloud. Notice that everything works just like running local flows with the Prefect API server, but because you configured `PREFECT_API_URL` and `PREFECT_API_KEY`, your flow runs show up in Prefect Cloud!

In your local environment, where you configured the previous steps, create a file named `basic_flow.py` with the following contents:

```python
from prefect import flow, get_run_logger

@flow(name="Testing")
def basic_flow():
    logger = get_run_logger()
    logger.warning("The fun is about to begin")

if __name__ == "__main__":
    basic_flow()
```

Now run `basic_flow.py`.

<div class="terminal">
```
$ python basic_flow.py
21:40:12.904 | INFO    | prefect.engine - Created flow run 'perfect-cat' for flow 'Testing'
21:40:12.904 | INFO    | Flow run 'perfect-cat' - Using task runner 'ConcurrentTaskRunner'
21:40:13.176 | WARNING | Flow run 'perfect-cat' - The fun is about to begin
21:40:13.555 | INFO    | Flow run 'perfect-cat' - Finished in state Completed()
```
</div>

Go to the dashboard for your workspace in Prefect Cloud. You'll see the flow run results right there in Prefect Cloud!

![Viewing local flow run results in the Cloud UI.](/img/ui/cloud-flow-run.png)

Prefect Cloud now automatically tracks any flow runs in a local execution environment logged into Prefect Cloud.

## Run a flow from a deployment

[Deployments](/concepts/deployments/) are flow runs packaged in a way that let you run them directly from the Prefect Cloud UI, either ad-hoc runs or via a schedule.

To run a flow from a deployment with Prefect Cloud, you'll need to:

- Add a `DeploymentSpec` to your flow definition
- Create the deployment using the Prefect CLI
- Configure a [work queue](/ui/work-queues/) that can allocate your deployment's flow runs to agents
- Start an agent in your execution environment
- Run your deployment to create a flow run

### Create a deployment specification

Go back to your flow code in `basic_flow.py` and update it to look like this, removing the guarded call to `basic_flow()` and replacing it with a `DeploymentSpec` providing some basic settings for the deployment.

```python
from prefect import flow, get_run_logger

@flow(name="Testing")
def basic_flow():
    logger = get_run_logger()
    logger.warning("The fun is about to begin")

from prefect.deployments import DeploymentSpec

DeploymentSpec(
    flow=basic_flow,
    name="Test Deployment",
    tags=['tutorial','test'], 
)
```

### Create the deployment

In the terminal, use the `prefect deployment create` command to create the deployment on Prefect Cloud, specifying the name of the `basic_flow.py` file that contains the flow code and deployment specification:

<div class="terminal">
```
$ prefect deployment create basic_flow.py
Loading deployment specifications from python script at 'basic_flow.py'...
Creating deployment 'Test Deployment' for flow 'Testing'...
Deploying flow script from '/Users/terry/test/testflows/basic_flow.py' using S3 Storage...
Created deployment 'Testing/Test Deployment'.
View your new deployment with:

    prefect deployment inspect 'Testing/Test Deployment'
Created 1 deployments!
```
</div>

Now your deployment has been created and is ready to orchestrate future `Testing` flow runs.

To demonstrate that your deployment exists, go back to Prefect Cloud and select the **Deployments** page. You'll see the 'Testing/Test Deployment' deployment was created.

!['Testing/Test Deployment' appears in the Prefect Cloud Deployments page](/img/ui/cloud-test-deployment.png)

### Create a work queue

Next create the work queue that can distribute your new deployment to agents for execution. 

In Prefect Cloud, select the **Work Queues** page, then select the **+** button to create a new work queue. Fill out the form as shown here, noting in particular to create the `test` tag on the queue. Note that this matches the `tags=['tutorial','test']` tag created on the deployment specification.

![Creating a work queue for test flows in Prefect Cloud](/img/ui/cloud-test-work-queue.png)

Select **Submit** to create the queue. 

When you go back to the **Work Queues** page, you'll see your new queue in the list.

![Viewing the new work queue for test flows in Prefect Cloud](/img/ui/cloud-test-queues.png)

### Run an agent

Now that you have a work queue to allocate flow runs, you can run an agent to pick up flow runs from that queue.

In your terminal, run the `prefect agent start` command, passing the name of the `test-queue` work queue you just created.

<div class="terminal">
```
$ prefect agent start 'test-queue'
Starting agent connected to https://api-beta.prefect.io/api/accounts/...

  ___ ___ ___ ___ ___ ___ _____     _   ___ ___ _  _ _____
 | _ \ _ \ __| __| __/ __|_   _|   /_\ / __| __| \| |_   _|
 |  _/   / _|| _|| _| (__  | |    / _ \ (_ | _|| .` | | |
 |_| |_|_\___|_| |___\___| |_|   /_/ \_\___|___|_|\_| |_|


Agent started! Looking for work from queue 'test-queue'...
```
</div>

### Run a flow

Now create a flow run from your deployment. You'll start the flow run from the Prefect Cloud UI, see it run by the agent in your local execution environment, and then see the result back in Prefect Cloud.

Go back to Prefect Cloud and select the **Deployments** page, then select **Test Deployment** in the 'Testing/Test Deployment' deployment name. You'll see a page showing details about the deployment.

![Overview of the test deployment in Prefect Cloud](/img/ui/cloud-test-deployment-details.png)

To start an ad-hoc flow run, select the **Run** button from Prefect Cloud.

In the local terminal session where you started the agent, you can see that the agent picks up the flow run and executes it.

<div class="terminal">
```
$ prefect agent start 'test-queue'
Starting agent connected to https://api-beta.prefect.io/api/accounts/...

  ___ ___ ___ ___ ___ ___ _____     _   ___ ___ _  _ _____
 | _ \ _ \ __| __| __/ __|_   _|   /_\ / __| __| \| |_   _|
 |  _/   / _|| _|| _| (__  | |    / _ \ (_ | _|| .` | | |
 |_| |_|_\___|_| |___\___| |_|   /_/ \_\___|___|_|\_| |_|


Agent started! Looking for work from queue 'test-queue'...
22:38:06.072 | INFO    | prefect.agent - Submitting flow run '7a9e94d4-7a97-4188-a539-b8594874eb86'
22:38:06.169 | INFO    | prefect.flow_runner.subprocess - Opening subprocess for flow run '7a9e94d4-7a97-4188-a539-b8594874eb86'...
22:38:06.180 | INFO    | prefect.agent - Completed submission of flow run '7a9e94d4-7a97-4188-a539-b8594874eb86'
22:38:09.918 | INFO    | Flow run 'crystal-hog' - Using task runner 'ConcurrentTaskRunner'
22:38:10.225 | WARNING | Flow run 'crystal-hog' - The fun is about to begin
22:38:10.868 | INFO    | Flow run 'crystal-hog' - Finished in state Completed()
22:38:11.797 | INFO    | prefect.flow_runner.subprocess - Subprocess for flow run '7a9e94d4-7a97-4188-a539-b8594874eb86' exited cleanly.
```
</div>

In Prefect Cloud, select the **Flow Runs** page and notice that your flow run appears on the dashboard. (Your flow run name will be different, but the rest of the details should be similar to what you see here.)

![Viewing the flow run based on the test deployment in Prefect Cloud](/img/ui/cloud-test-flow-run.png)

To learn more, see the [Deployments tutorial](/tutorials/deployments/#work-queues-and-agents) for a hands-on example.
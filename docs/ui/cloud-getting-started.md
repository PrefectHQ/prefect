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

# Getting Started with Prefect Cloud <span class="badge cloud"></span>

The following sections will get you set up and using Prefect Cloud, using these steps:

1. [Sign in or register](#sign-in-or-register) a Prefect Cloud account.
1. [Create workspaces](#create-a-workspace) for your account.
1. [Create an API key](#create-an-api-key) to authorize a local execution environment.
1. [Configure a local execution environment](#configure-a-local-execution-environment) to use Prefect Cloud.
1. [Run a flow](#run-a-flow-with-prefect-cloud) locally and view flow run execution in Prefect Cloud.
1. [Run a flow from a deployment](#run-a-flow-from-a-deployment), enabling remote execution of flow runs.

## Sign in or register

To sign in with an existing account or register an account, go to [https://app.prefect.cloud/](https://app.prefect.cloud/).

You can create an account with:

- Google account
- Microsoft (GitHub) account
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

![Editing workspace settings in the Prefect Cloud UI](/img/ui/cloud-workspace-settings.png)

!!! warning "Deleting a workspace"
    Deleting a workspace removes any flows, deployments, and storage created on that workspace.

## Create an API key

API keys enable you to authenticate an a local environment to work with Prefect Cloud. See [Configure execution environment](#configure-execution-environment) for details on how API keys are configured in your execution environment.

To create an API key, select the account icon at the bottom-left corner of the UI and select your account name. This displays your account profile.

Select the **API Keys** tab. This displays a list of previously generated keys and lets you create new API keys or delete keys.

![Viewing and editing API keys in the Cloud UI.](/img/ui/cloud-api-keys.png)

Select the **+** button to create a new API key. You're prompted to provide a name for the key and, optionally, an expiration date. Select **Create API Key** to generate the key.

![Creating an API key in the Cloud UI.](/img/ui/cloud-new-api-key.png)

Note that API keys cannot be revealed again in the UI after you generate them, so copy the key to a secure location.

## Configure a local execution environment

Configure a local execution environment to use Prefect Cloud as the API server for flow runs. In other words, "log in" to Prefect Cloud from a local environment where you want to run a flow.

First, [Install Prefect](/getting-started/installation/) in the environment in which you want to execute flow runs.

Next, use the `prefect cloud login` Prefect CLI command to log into Prefect Cloud from your environment, using the [API key](#create-an-api-key) generated previously.

<div class="terminal">
```bash
$ prefect cloud login --key xxx_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```
</div>

If this is your first time logging in with this API key, you will be prompted to make a new profile as well as select a workspace (you can specify a workspace with the `-w` or `--workspace` option).

<div class="terminal">
```bash
$ prefect cloud login --key xxx_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
┏━━━━━━━━━━━━━━━━━━━━━━┓
┃  Select a Workspace: ┃
┡━━━━━━━━━━━━━━━━━━━━━━┩
│ > prefect/workinonit │
└──────────────────────┘
Creating a profile for this Prefect Cloud login. Please specify a profile name: my-cloud-profile
Logged in to Prefect Cloud using profile 'my-cloud-profile'.
Workspace is currently set to 'prefect/workinonit'. The workspace can be changed using `prefect cloud workspace set`.
```
</div>

The command sets `PREFECT_API_KEY` and `PREFECT_API_URL` for the new profile.

Now you're ready to run flows locally and have the results displayed in the Prefect Cloud UI.

You can log out of Prefect Cloud by switching to a different profile.

!!! tip "Interactive login"
    The `prefect cloud login` command, used on its own, provides an interactive login experience. Using this command, you may log in with either an API key or through a browser.

    <div class="terminal">
    ```bash
    $ prefect cloud login
    ? How would you like to authenticate? [Use arrows to move; enter to select]
      Log in with a web browser
    > Paste an authentication key
    Paste your authentication key:
    ? Which workspace would you like to use? [Use arrows to move; enter to select]
    > prefect/workinonit
      g-gadflow/g-workspace
    Authenticated with Prefect Cloud! Using workspace 'prefect/workinonit'.
    ```
    </div>

### Changing workspaces

If you need to change which workspace you're syncing with, use the `prefect cloud workspace set` Prefect CLI command while logged in, passing the account handle and workspace name.

<div class="terminal">
```bash
$ prefect cloud workspace set --workspace "prefect/workinonit"
```
</div>

If no workspace is provided, you will be prompted to select one.

**Workspace Settings** also shows you the `prefect cloud workspace set` Prefect CLI command you can use to sync a local execution environment with a given workspace.

You may also use the `prefect cloud login` command with the `--workspace` or `-w` option to set the current workspace.

<div class="terminal">
```bash
$ prefect cloud login --workspace "prefect/workinonit"
```
</div>

### Manually configuring Cloud settings

Note that you can also manually configure the `PREFECT_API_URL` and `PREFECT_API_KEY` settings to interact with Prefect Cloud by using an account ID, workspace ID, and API key.

<div class="terminal">
```bash
$ prefect config set PREFECT_API_URL="https://api.prefect.cloud/api/accounts/[ACCOUNT-ID]/workspaces/[WORKSPACE-ID]"
$ prefect config set PREFECT_API_KEY="[API-KEY]"
```
</div>

When you're in a Prefect Cloud workspace, you can copy the `PREFECT_API_URL` value directly from the page URL.

In this example, we configured `PREFECT_API_URL` and `PREFECT_API_KEY` in the default profile. You can use `prefect profile` CLI commands to create settings profiles for different configurations. For example, you could have a "cloud" profile configured to use the Prefect Cloud API URL and API key, and another "local" profile for local development using a local Prefect API server started with `prefect orion start`. See [Settings](/concepts/settings/) for details.

!!! note "Environment variables"
    You can also set `PREFECT_API_URL` and `PREFECT_API_KEY` as you would any other environment variable. See [Overriding defaults with environment variables](/concepts/settings/#overriding-defaults-with-environment-variables) for more information.

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

[Deployments](/concepts/deployments/) are flows packaged in a way that let you run them directly from the Prefect Cloud UI, either ad-hoc runs or via a schedule.

To run a flow from a deployment with Prefect Cloud, you'll need to:

- Create a flow script
- Create the deployment using the Prefect CLI
- Start an agent in your execution environment
- Run your deployment to create a flow run

### Configure storage 

For the Prefect Cloud quickstart, we'll use local storage. You don't need to set up any remote storage to complete this tutorial. 

When using Prefect Cloud in production, we recommend configuring remote storage. Storage is used to make flow scripts available when creating flow runs via API in remote execution environments. Storage is also used for persisting flow and task data. See [Storage](/concepts/storage/) for details.

By default, Prefect uses local file system storage to persist flow code and flow and task results. For local development and testing this may be adequate. Be aware, however, that local storage is not guaranteed to persist data reliably between flow or task runs, particularly when using container-based environments such as Docker or Kubernetes, or when executing tasks with distributed computing tools like Dask and Ray.

### Create a deployment

Let's go back to your flow code in `basic_flow.py`. In a terminal, run the `prefect deployment build` Prefect CLI command to build a manifest JSON file and deployment YAML file that you'll use to create the deployment on Prefect Cloud.

<div class="terminal">
```bash
$ prefect deployment build ./basic_flow.py:basic_flow -n test-deployment -q test
```
</div>

What did we do here? Let's break down the command:

- `prefect deployment build` is the Prefect CLI command that enables you to prepare the settings for a deployment.
-  `./basic_flow.py:basic_flow` specifies the location of the flow script file and the name of the entrypoint flow function, separated by a colon.
- `-n test-deployment` is an option to specify a name for the deployment.
- `-q test` specifies a work queue for the deployment. The deployment's runs will be sent to any agents monitoring this work queue.

The command outputs `basic_flow-deployment.yaml`, which contains details about the deployment for this flow.

### Create the deployment

In the terminal, use the `prefect deployment apply` command to apply the settings contained in the manifest and `deployment.yaml` to create the deployment on Prefect Cloud.

Run the following Prefect CLI command.

<div class="terminal">
```bash
$ prefect deployment apply basic_flow-deployment.yaml
Successfully loaded 'test-deployment'
Deployment '66b3fdea-cd3a-4734-b3f2-65f6702ff260' successfully created.
```
</div>

Now your deployment has been created and is ready to orchestrate future `Testing` flow runs.

To demonstrate that your deployment exists, go back to Prefect Cloud and select the **Deployments** page. You'll see the 'Testing/Test Deployment' deployment was created.

!['Testing/Test Deployment' appears in the Prefect Cloud Deployments page](/img/ui/cloud-test-deployment.png)

### Create a work queue and agent

Next, we start an agent that can pick up the flow run from your 'Testing/Test Deployment' deployment. Remember that when we created the deployment, it was configured to send work to a work queue called `test`. This work queue was automatically created when we created the deployment. In Prefect Cloud, you can view your work queues and create new ones manually by selecting the **Work Queues** page.

In your terminal, run the `prefect agent start` command, passing a `-q test` option that tells it to look for work in the `test` work queue.

<div class="terminal">
```

$ prefect agent start -q test

Starting agent connected to https://api.prefect.cloud/api/accounts/...

  ___ ___ ___ ___ ___ ___ _____     _   ___ ___ _  _ _____
 | _ \ _ \ __| __| __/ __|_   _|   /_\ / __| __| \| |_   _|
 |  _/   / _|| _|| _| (__  | |    / _ \ (_ | _|| .` | | |
 |_| |_|_\___|_| |___\___| |_|   /_/ \_\___|___|_|\_| |_|


Agent started! Looking for work from queue 'test'...
```
</div>

!!! tip "`PREFECT_API_URL` setting for agents"
    `PREFECT_API_URL` must be set for the environment in which your agent is running. 

    In this case, we're running the agent in the same environment we logged into Prefect Cloud earlier. However, if you want the agent to communicate with Prefect Cloud from a remote execution environment such as a VM or Docker container, you must configure `PREFECT_API_URL` in that environment.

### Run a flow

Now create a flow run from your deployment. You'll start the flow run from the Prefect Cloud UI, see it run by the agent in your local execution environment, and then see the result back in Prefect Cloud.

Go back to Prefect Cloud and select the **Deployments** page, then select **Test Deployment** in the 'Testing/Test Deployment' deployment name. You'll see a page showing details about the deployment.

![Overview of the test deployment in Prefect Cloud](/img/ui/cloud-test-deployment-details.png)

To start an ad-hoc flow run, select the **Run** button from Prefect Cloud.

In the local terminal session where you started the agent, you can see that the agent picks up the flow run and executes it.

<div class="terminal">
```
$ prefect agent start -q test
Starting agent connected to https://api.prefect.cloud/api/accounts/...

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

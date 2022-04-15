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
6. [Run a flow](#run-a-flow-with-cloud) and display the flow run in Prefect Cloud.

## Sign in or register

To sign in with an existing account or register an account, go to [http://beta.prefect.io/](http://beta.prefect.io/).

You can create an account with:

- Google account
- GitHub account
- Email and password

## Create a workspace

A workspace is an isolated environment within Prefect Cloud for your flows and deployments. Workspaces could be used in any way you like to organize or compartmentalize your workflows. For example, you could use separate workspaces to isolate dev, staging, and prod environments, or to provide separation between different teams.

When you register a new account, you'll be prompted to create a workspace.  

![Creating a new Prefect Cloud account.](/img/ui/cloud-new-login.png)

Click **Create Workspace**. You'll be prompted to provide a name and description for your workspace.

![Creating a new workspace in the Cloud UI.](/img/ui/cloud-workspace-details.png)

Click **Create** to create the workspace. 

![Viewing a list of available workspaces in the Cloud UI.](/img/ui/cloud-workspace-list.png)

Click **Edit Workspace**. This lets you edit details about the workspace or delete the workspace. 

It also provide the Prefect CLI command that configures Prefect to orchestrate flow runs with this workspace. Copy this command and run it in the environment in which you'll be running flows so they'll show up in your workspace.

![Editing a workspace.](/img/ui/cloud-edit-workspace.png)

Click the Prefect logo: this always returns to your workspace list. Then click on a workspace name to view the dashboard for that workspace.

![Viewing a workspace dashboard in the Prefect Cloud UI.](/img/ui/cloud-workspace-dashboard.png)

## Create an API key

API keys enable you to authenticate an a local environment to work with Prefect Cloud. See [Configuring Orion for Cloud](#configuring-orion-for-cloud) for details on how API keys are configured in your execution environment.

To create an API key, click the account icon at the bottom-left corner of the UI, then click **Profile**. This displays your account profile.

![Viewing an account profile in the Cloud UI.](/img/ui/cloud-edit-profile.png)

Click the **API Keys** tab. This displays a list of previously generated keys and lets you create new API keys or delete keys.

![Editing and creating API keys in the Cloud UI.](/img/ui/cloud-api-keys.png)

Click **Create** to create a new API key. You're prompted to provide a name for the key. Click **Confirm** to generate the key.

Note that API keys cannot be revealed again in the UI after you generate them, so copy the key to a secure location.

## Configure Orion for Cloud

Your next step is to configure a local execution environment to use Prefect Cloud as the API server for local flow runs.

First, [Install Orion](/getting-started/installation/) in the environment in which you want to execute flow runs.

Next, use the Prefect CLI `prefect cloud login` command to log into Prefect Cloud from your environment, using the [API key](#create-an-api-key) generated previously.

```bash
$ prefect cloud login --key xxx_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

It will prompt you to choose a workspace if you haven't given one (you can specify a workspace with the `-w` or `--workspace` option).

```bash
$ prefect cloud login --key xxx_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃              Select a Workspace: ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ > tprefectio/tp-workspace        │
└──────────────────────────────────┘
Successfully logged in and set workspace to 'tprefectio/tp-workspace' in profile:
'default'.
```

It then sets `PREFECT_API_KEY` and `PREFECT_API_URL` for the current profile.

Now you're ready to run flows locally and have the results displayed in the Prefect Cloud UI.

The `prefect cloud logout` CLI command unsets those settings in the current profile, logging the environment out of interaction with Prefect Cloud.

### Manually configuring Cloud settings

Note that you can also manually configure the settings to interact with Prefect Cloud using an account ID, workspace ID, and API key.

```BASH
$ prefect config set PREFECT_API_URL="https://beta.prefect.io/api/accounts/[ACCOUNT-ID]/workspaces/[WORKSPACE-ID]"
$ prefect config set PREFECT_API_KEY="[API-KEY]"
```

When you're in a Prefect Cloud workspace, you can copy the API URL directly from the page URL, or copy the entire command string from the **Workspace Details** page.

In this example, we configured `PREFECT_API_URL` and `PREFECT_API_KEY` in the default profile. You can use `prefect profile` CLI commands to create settings profiles for different configurations. For example, you could have a profile configured to use the Cloud API URL and API key, and another profile for local development using a local Orion API server. See [Settings](/concepts/settings/) for details.

## Configure storage 

When using Prefect Cloud, we recommend configuring global storage for persisting flow and task data. See [Storage](/concepts/storage/) for details.

By default, Prefect uses local file system storage to persist flow code and flow and task results. For local development and testing this may be adequate. Be aware, however, that local storage is not guaranteed to persist data reliably between flow or task runs, particularly when using containers or distributed computing environments like Dask and Ray.

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

<div class='termy'>
```
$ python basic_flow.py
11:31:46.135 | INFO    | prefect.engine - Created flow run 'delicate-woodpecker' for flow 'Testing'
11:31:46.135 | INFO    | Flow run 'delicate-woodpecker' - Using task runner 'ConcurrentTaskRunner'
11:31:46.748 | WARNING | Flow run 'delicate-woodpecker' - The fun is about to begin
11:31:47.643 | INFO    | Flow run 'delicate-woodpecker' - Finished in state Completed(None)
```
</div>

Go to the dashboard for your workspace in Prefect Cloud. You'll see the flow run results right there in Prefect Cloud!

![Viewing local flow run results in the Cloud UI.](/img/ui/cloud-flow-run.png)

To run deployments using the API or directly from the Prefect Cloud UI, you'll need to configure [work queues](/ui/work-queues/) and agents. See the [Work Queues & Agents](/concepts/work-queues/) documentation for details, and the [Deployments tutorial](/tutorials/deployments/#work-queues-and-agents) for a hands-on example.
---
description: Using Prefect Cloud, including account creation, team and workspace management, and running flows.
tags:
    - UI
    - dashboard
    - Cloud
    - accounts
    - teams
    - workspaces
---

# Prefect Cloud

Prefect Cloud is a hosted UI for your flows and deployments. Prefect Cloud provides all the capabilities of the [Orion UI](/ui/overview/), plus additional features available only for Cloud accounts. This includes:

- Flow run summaries
- Deployed flow details
- Scheduled flow runs
- Warnings for late or failed runs
- Task run details 
- Radar flow and task dependency visualizer 
- Logs

Features only available on Prefect Cloud include:

- User accounts
- Workspaces

## Sign in or register

To sign in with an existing account or register an account, go to [http://api-beta.prefect.io/](http://api-beta.prefect.io/).

You can create an account with:

- Google account
- GitHub account
- Email and password

## Create a workspace

If you register a new account, you'll be prompted to create a new workspace. Workspaces enable you to organize work, keeping workflows for different projects, teams, or clients in their own spaces.

![](/img/ui/cloud-new-login.png)

Click **Create Workspace**. You'll be prompted to provide a name and description for your first workspace.

![](/img/ui/cloud-workspace-details.png)

Click **Create** to create the workspace. 

![](/img/ui/cloud-workspace-list.png)

Click **Edit Workspace**. This lets you edit details about the workspace or delete the workspace. 

It also provide the Prefect CLI command that configures Prefect to orchestrate flow runs with this workspace. Copy this command and run it in the environment in which you'll be running flows so they'll show up in your workspace.

![](/img/ui/cloud-edit-workspace.png)

Click the Prefect logo: this always returns to your workspace list. Then click on a workspace name to view the dashboard for that workspace.

![](/img/ui/cloud-workspace-dashboard.png)

## Create an API token

API tokens enable you to authenticate an a local environment to work with Prefect Cloud. See [Configuring Orion for Cloud](#configuring-orion-for-cloud) for details on how API keys are configured in your execution environment.

To create an API token, click the account icon at the bottom-left corner of the UI, then click **Profile**. This displays your account profile.

![](/img/ui/cloud-edit-profile.png)

Click the **API Keys** tab. This displays a list of previously generated keys and lets you create new API keys or delete keys.

![](/img/ui/cloud-api-keys.png)

Click **Create** to create a new API key. You're prompted to provide a name for the key. Click **Confirm** to generate the key.

Note that API keys cannot be revealed again in the UI after you generate them, so copy the key to a secure location.


## Configuring Orion for Cloud

Your next step is to configure a local execution environment to use Cloud as the API server for local flow runs.

1. [Install Orion](/getting-started/installation/) in the environment in which you want to execute flow runs.

2. In that environment, use the Prefect CLI to configure the Orion API URL, substituting your account and workspace IDs where indicated. When you're in a Prefect Cloud workspace, you can copy the accounts and workspaces strings directly from the page URL.

```bash
$ prefect config set PREFECT_API_URL="https://api-beta.prefect.io/api/accounts/<ACCOUNT ID>/workspaces/<WORKSPACE ID>"
```

3. Use the Prefect CLI to configure your API key, using an API key.

```bash
$ prefect config set PREFECT_API_KEY="<API KEY>"
```

Now you're ready to run flows locally and have the results displayed in the Cloud UI.

In this example, we configured `PREFECT_API_URL` and `PREFECT_API_KEY` in the default profile. You can use `prefect config` CLI commands to create settings profiles for different configuration. For example, you could have a profile configured to use the Cloud API URL and API key, and another profile for local development using a local Orion API server. See [Settings](/concepts/settings/) for details.

## Configure storage 

When using Prefect Cloud, we recommend configuring global storage for persisting flow and task data. See [Storage](/concepts/storage/) for details.

By default, Orion uses local file system storage to persist data like task results, cache keys, and so on. For local development and testing this may be adequate. Be aware, however, that local storage is not guaranteed to persist data reliably between flow or task runs, particularly when using containers or distributed computing environments like Dask and Ray.

## Run a flow with Cloud
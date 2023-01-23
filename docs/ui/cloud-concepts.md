---
description: Get started using Prefect Cloud, including creating a workspace and running a flow deployment.
icon: material/cloud-outline
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

# Prefect Cloud Concepts <span class="badge cloud"></span>

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

Note that the **Owner** setting applies only to users who are members of Prefect Cloud organizations who have permission to create workspaces within the organization.

Select **Save** to create the workspace. If you change your mind, select **Edit** from the options menu to modify the workspace details or to delete it. 

![Viewing a workspace dashboard in the Prefect Cloud UI.](/img/ui/cloud-new-workspace.png)

The **Workspace Settings** page for your new workspace displays the commands to install Prefect and log into Prefect Cloud in a local execution environment.

## Log into Prefect Cloud from a terminal

Configure a local execution environment to use Prefect Cloud as the API server for flow runs. In other words, "log in" to Prefect Cloud from a local environment where you want to run a flow.

1. Open a new terminal session.
2. [Install Prefect](/getting-started/installation/) in the environment in which you want to execute flow runs.

<div class="terminal">
```bash
$ pip install -U prefect
```
</div>

3. Use the `prefect cloud login` Prefect CLI command to log into Prefect Cloud from your environment.

<div class="terminal">
```bash
$ prefect cloud login
```
</div>

The `prefect cloud login` command, used on its own, provides an interactive login experience. Using this command, you may log in with either an API key or through a browser.

<div class="terminal">
```bash
$ prefect cloud login
? How would you like to authenticate? [Use arrows to move; enter to select]
> Log in with a web browser
    Paste an authentication key
Paste your authentication key:
? Which workspace would you like to use? [Use arrows to move; enter to select]
> prefect/terry-prefect-workspace
    g-gadflow/g-workspace
Authenticated with Prefect Cloud! Using workspace 'prefect/terry-prefect-workspace'.
```
</div>

## Configure a local execution environment

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

## Create an API key

API keys enable you to authenticate an a local environment to work with Prefect Cloud. See [Configure execution environment](#configure-execution-environment) for details on how API keys are configured in your execution environment.

To create an API key, select the account icon at the bottom-left corner of the UI and select your account name. This displays your account profile.

Select the **API Keys** tab. This displays a list of previously generated keys and lets you create new API keys or delete keys.

![Viewing and editing API keys in the Cloud UI.](/img/ui/cloud-api-keys.png)

Select the **+** button to create a new API key. You're prompted to provide a name for the key and, optionally, an expiration date. Select **Create API Key** to generate the key.

![Creating an API key in the Cloud UI.](/img/ui/cloud-new-api-key.png)

Note that API keys cannot be revealed again in the UI after you generate them, so copy the key to a secure location.

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





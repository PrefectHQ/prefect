---
description: Configure a local execution environment to access Prefect Cloud.
tags:
    - Prefect Cloud
    - API keys
    - configuration
    - agents
    - workers
---

# Configure a Local Execution Environment

In order to create flow runs in a local or remote execution environment and use either Prefect Cloud or a Prefect server as the backend API server, you must: 

- Configure the execution environment with the location of the API. 
- Authenticate with the API, either by logging in or providing a valid API key (Prefect Cloud only).

## Log into Prefect Cloud from a terminal <span class="badge cloud"></span>

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
    Paste an API key
Paste your authentication key:
? Which workspace would you like to use? [Use arrows to move; enter to select]
> prefect/terry-prefect-workspace
    g-gadflow/g-workspace
Authenticated with Prefect Cloud! Using workspace 'prefect/terry-prefect-workspace'.
```
</div>

You can also log in by providing a [Prefect Cloud API key](/ui/cloud-api-keys/).

### Change workspaces

If you need to change which workspace you're syncing with, use the `prefect cloud workspace set` Prefect CLI command while logged in, passing the account handle and workspace name.

<div class="terminal">
```bash
$ prefect cloud workspace set --workspace "prefect/my-workspace"
```
</div>

If no workspace is provided, you will be prompted to select one.

**Workspace Settings** also shows you the `prefect cloud workspace set` Prefect CLI command you can use to sync a local execution environment with a given workspace.

You may also use the `prefect cloud login` command with the `--workspace` or `-w` option to set the current workspace.

<div class="terminal">
```bash
$ prefect cloud login --workspace "prefect/my-workspace"
```
</div>

## Manually configure Prefect API settings

You can also manually configure the `PREFECT_API_URL` setting to specify the Prefect Cloud or Prefect server API.

Go to your terminal session and run this command to set the API URL to point to a Prefect server instance:

<div class='terminal'>
```bash
$ prefect config set PREFECT_API_URL="http://127.0.0.1:4200/api"
```
</div>

For Prefect Cloud, you can configure the `PREFECT_API_URL` and `PREFECT_API_KEY` settings to authenticate with Prefect Cloud by using an account ID, workspace ID, and API key.

<div class="terminal">
```bash
$ prefect config set PREFECT_API_URL="https://api.prefect.cloud/api/accounts/[ACCOUNT-ID]/workspaces/[WORKSPACE-ID]"
$ prefect config set PREFECT_API_KEY="[API-KEY]"
```
</div>

When you're in a Prefect Cloud workspace, you can copy the `PREFECT_API_URL` value directly from the page URL.

In this example, we configured `PREFECT_API_URL` and `PREFECT_API_KEY` in the default profile. You can use `prefect profile` CLI commands to create settings profiles for different configurations. For example, you could have a "cloud" profile configured to use the Prefect Cloud API URL and API key, and another "local" profile for local development using a local Prefect API server started with `prefect server start`. See [Settings](/concepts/settings/) for details.

!!! note "Environment variables"
    You can also set `PREFECT_API_URL` and `PREFECT_API_KEY` as you would any other environment variable. See [Overriding defaults with environment variables](/concepts/settings/#overriding-defaults-with-environment-variables) for more information.

See the [Flow orchestration with Prefect](/tutorials/orchestration/) tutorial for examples.

## Install requirements in execution environments

In local and remote execution environments &mdash; such as VMs and containers &mdash; you must make sure any flow requirements or dependencies have been installed before creating a flow run.
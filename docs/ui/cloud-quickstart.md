---
description: Start using Prefect Cloud and run a flow.
icon: material/cloud-outline
tags:
    - UI
    - dashboard
    - Prefect Cloud
    - quickstart
    - workspaces
    - tutorial
    - getting started
---

# Prefect Cloud Quickstart <span class="badge cloud"></span>

Get signed in and using Prefect Cloud, including running a flow observed by Prefect Cloud, in just a few steps:

1. [Sign in or register](#sign-in-or-register) a Prefect Cloud account.
1. [Create a workspace](#create-a-workspace) for your account.
1. [Install Prefect](#install-prefect) in your local environment.
1. [Log into Prefect Cloud](#log-into-prefect-cloud-from-a-terminal) from a local terminal session.
1. [Run a flow](#run-a-flow-with-prefect-cloud) locally and view flow run execution in Prefect Cloud.

Prefer to follow this tutorial in a video? We've got exactly what you need. Happy engineering!

<div class="video-wrapper">
  <iframe width="100%" height="500" src="https://www.youtube.com/embed/vOpmE5w0XuU" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>
</div>

## Sign in or register

To sign in with an existing account or register an account, go to [https://app.prefect.cloud/](https://app.prefect.cloud/).

You can create an account with:

- Google account
- Microsoft (GitHub) account
- Email

![Creating a new Prefect Cloud account.](../img/ui/cloud-sign-in.png)

## Create a workspace

A workspace is an isolated environment within Prefect Cloud for your flows and deployments. You can use workspaces to organize or compartmentalize your workflows.

When you register a new account, you'll be prompted to create a workspace.  

![Creating a new Prefect Cloud account.](../img/ui/cloud-new-login.png)

Select **Create Workspace**. You'll be prompted to provide a name and description for your workspace.

![Creating a new workspace in the Cloud UI.](../img/ui/cloud-workspace-details.png)

Note that the **Owner** setting applies only to users who are members of Prefect Cloud organizations and have permission to create workspaces within the organization.

Select **Save** to create the workspace. If you change your mind, select **Edit** from the options menu to modify the workspace details or to delete it. 

![Viewing a workspace dashboard in the Prefect Cloud UI.](../img/ui/cloud-new-workspace.png)

The **Workspace Settings** page for your new workspace displays the commands that enable you to install Prefect and log into Prefect Cloud in a local execution environment.

## Install Prefect

Configure a local execution environment to use Prefect Cloud as the API server for flow runs. In other words, "log in" to Prefect Cloud from a local environment where you want to run a flow.

Open a new terminal session.

[Install Prefect](/getting-started/installation/) in the environment in which you want to execute flow runs.

<div class="terminal">
```bash
$ pip install -U prefect
```
</div>

!!! note "Installation requirements"
    Prefect requires Python 3.7 or later. If you have any questions about Prefect installations requirements or dependencies in your preferred development environment, check out the [Installation](/getting-started/installation/) documentation.

## Log into Prefect Cloud from a terminal

Use the `prefect cloud login` Prefect CLI command to log into Prefect Cloud from your environment.

<div class="terminal">
```bash
$ prefect cloud login
```
</div>

The `prefect cloud login` command, used on its own, provides an interactive login experience. Using this command, you may log in with either an API key or through a browser.

<div class="terminal">
```shell
$ prefect cloud login
? How would you like to authenticate? [Use arrows to move; enter to select]
> Log in with a web browser
  Paste an API key
Opening browser...
Waiting for response...
? Which workspace would you like to use? [Use arrows to move; enter to select]
> prefect/terry-prefect-workspace
  g-gadflow/g-workspace
Authenticated with Prefect Cloud! Using workspace 'prefect/terry-prefect-workspace'.
```
</div>

If you choose to log in via the browser, Prefect opens a new tab in your default browser and enables you to log in and authenticate the session. Use the same login information as you originally used to create your Prefect Cloud account.

## Run a flow with Prefect Cloud

Okay, you're all set to run a local flow with Prefect Cloud. Notice that everything works just like [running local flows](/tutorials/first-steps/). However, because you logged into Prefect Cloud locally, your local flow runs show up in Prefect Cloud!

In your local environment, where you configured the previous steps, create a file named `quickstart_flow.py` with the following contents:

```python
from prefect import flow, get_run_logger

@flow(name="Prefect Cloud Quickstart")
def quickstart_flow():
    logger = get_run_logger()
    logger.warning("Local quickstart flow is running!")

if __name__ == "__main__":
    quickstart_flow()
```

Now run `quickstart_flow.py`. You'll see the following log messages in the terminal, indicating that the flow is running correctly.

<div class="terminal">
```
$ python quickstart_flow.py
17:52:38.741 | INFO    | prefect.engine - Created flow run 'aquamarine-deer' for flow 'Prefect Cloud Quickstart'
17:52:39.487 | WARNING | Flow run 'aquamarine-deer' - Local quickstart flow is running!
17:52:39.592 | INFO    | Flow run 'aquamarine-deer' - Finished in state Completed()
```
</div>

Go to the **Flow Runs** pages in your workspace in Prefect Cloud. You'll see the flow run results right there in Prefect Cloud!

![Viewing flow run results in the Prefect Cloud UI Flow Runs dashboard.](../img/ui/cloud-flow-run.png)

Prefect Cloud automatically tracks any flow runs in a local execution environment logged into Prefect Cloud.

Select the name of the flow run to see details about this run. In this example, the randomly generated flow run name is `aquamarine-deer`. Your flow run name is likely to be different.

![Viewing local flow run details in the Prefect Cloud UI.](../img/ui/cloud-flow-run-details.png)

Congratulations! You successfully ran a local flow and, because you're logged into Prefect Cloud, the local flow run results were captured by Prefect Cloud.

## Next steps

If you're new to Prefect, learn more about writing and running flows in the [Prefect Flows First Steps](/tutorials/first-steps/) tutorial. If you're already familiar with Prefect flows and want to try creating deployments and kicking off flow runs with Prefect Cloud, check out the [Deployments](/tutorials/deployments/) and [Storage and Infrastructure](/tutorials/storage/) tutorials.

Want to learn more about the features available in Prefect Cloud? Start with the [Prefect Cloud Overview](/ui/cloud/).

If you ran into any issues getting your first flow run with Prefect Cloud working, please join our community to ask questions or provide feedback:

- [Prefect's Slack Community](https://www.prefect.io/slack/) is helpful, friendly, and fast growing - come say hi!
- [Prefect Discourse](https://discourse.prefect.io/) is a knowledge base with plenty of tutorials, code examples, answers to frequently asked questions, and troubleshooting tips.
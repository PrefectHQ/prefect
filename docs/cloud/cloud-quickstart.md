---
description: Start using Prefect Cloud and run a flow.
tags:
    - UI
    - dashboard
    - Prefect Cloud
    - quickstart
    - workspaces
    - tutorial
    - getting started
search:
  boost: 2
---

# Getting Started with Prefect Cloud <span class="badge cloud"></span>

Get started with Prefect Cloud in just a few steps:

1. [Sign in or register](#sign-in-or-register) a Prefect Cloud account.
1. [Create a workspace](#create-a-workspace) for your account.
1. [Install Prefect](#install-prefect) in your local environment.
1. [Log into Prefect Cloud](#log-into-prefect-cloud-from-a-terminal) from a local terminal session.
1. [Run a flow](#run-a-flow-with-prefect-cloud) locally and view flow run execution in Prefect Cloud.

<!-- 
TK commented out until video updated
TK to hide TOC for video: add hide: toc 

Prefer to follow this tutorial in a video? We've got exactly what you need. Happy engineering!

<div class="video-wrapper">
  <iframe width="100%" height="500" src="https://www.youtube.com/embed/vOpmE5w0XuU" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>
</div>
-->

## Sign in or register

To sign in with an existing account or register an account, go to [https://app.prefect.cloud/](https://app.prefect.cloud/).

You can create an account with any of the following:

- Google account
- Microsoft account
- GitHub account
- Email

![Creating a new Prefect Cloud account.](/img/ui/cloud-sign-in.png)

## Create a workspace

A workspace is an isolated environment within Prefect Cloud for your flows and deployments.
You can use workspaces to organize or compartmentalize your workflows.

When you register a new account, you'll be prompted to provide a name and description for your workspace.

![Creating a new workspace in the Cloud UI.](/img/ui/cloud-workspace-details.png)

Note that the **Owner** setting applies only to users who are members of Prefect Cloud accounts and have permission to create workspaces within account.

Select **Create** to create the workspace.
If you change your mind, select **Edit** from the options menu to modify the workspace details or to delete it.

![Viewing a workspace dashboard in the Prefect Cloud UI.](/img/ui/cloud-new-workspace.png)

The **Workspace Settings** page for your new workspace displays the commands that enable you to install Prefect and log into Prefect Cloud in a local execution environment.

## Install Prefect

Configure a local execution environment to use Prefect Cloud as the API server for flow runs.
In other words, "log in" to Prefect Cloud from a local environment where you want to run a flow.

Open a new terminal session.

[Install Prefect](/getting-started/installation/) in the environment in which you want to execute flow runs.

```bash
pip install -U prefect
```

!!! note "Installation requirements"
    Prefect requires Python 3.8 or later.
    If you have any questions about Prefect installations requirements or dependencies in your preferred development environment, check out the [Installation](/getting-started/installation/) documentation.

## Log into Prefect Cloud from a terminal

Use the `prefect cloud login` Prefect CLI command to log into Prefect Cloud from your environment.

```bash
prefect cloud login
```

The `prefect cloud login` command, used on its own, provides an interactive login experience.
Using this command, you may log in with either an API key or through a browser.

```output

? How would you like to authenticate? [Use arrows to move; enter to select]
> Log in with a webb browser                                                
  Paste an API key                                                         
Opening browser...
Waiting for response...
Authenticated with Prefect Cloud! Using workspace 'jeffdc/prod'.

```

If you choose to log in via the browser, Prefect opens a new tab in your default browser and enables you to log in and authenticate the session.

## Run a flow with Prefect Cloud

You're all set to run a flow locally, orchestrated with Prefect Cloud.

In your local environment, where you configured the previous steps, create a file named `quickstart_flow.py` with the following contents:

```python
from prefect import flow

@flow(log_prints=True)
def quickstart_flow():
    print("Local quickstart flow is running!")

if __name__ == "__main__":
    quickstart_flow()
```

Now run `quickstart_flow.py`.
You'll see log messages like this in your terminal, indicating that the flow is running correctly:

```output
17:18:09.863 | INFO    | prefect.engine - Created flow run 'fragrant-quetzal' for flow 'quickstart-flow'
17:18:09.864 | INFO    | Flow run 'fragrant-quetzal' - View at https://app.prefect.cloud/account/my_workspace_id/workspace/my_flow_id/flow-runs/flow-run/my_flow_run_id
17:18:10.010 | INFO    | Flow run 'fragrant-quetzal' - Local quickstart flow is running!
17:18:10.144 | INFO    | Flow run 'fragrant-quetzal' - Finished in state Completed()
```

Go to the **Flow Runs** pages in your workspace in Prefect Cloud.
You'll see the flow run results right there in Prefect Cloud!

![Viewing flow run results in the Prefect Cloud UI Flow Runs dashboard.](/img/ui/cloud-flow-run.png)

Prefect Cloud automatically tracks any flow runs in a local execution environment logged into Prefect Cloud.

Select the name of the flow run to see details about this run.

![Viewing local flow run details in the Prefect Cloud UI.](/img/ui/cloud-flow-run-details.png)

Congratulations! You successfully ran a local flow and, because you're logged into Prefect Cloud, the local flow run results were captured by Prefect Cloud.

## Next steps

If you're new to Prefect, learn more about writing and running flows in the [Prefect Flows First Steps](/tutorial/flows/) tutorial.
If you're already familiar with flows, try creating a deployment and triggering flow runs with Prefect Cloud by following the [Deployments](/tutorial/deployments/) tutorial.

Want to learn more about the features available in Prefect Cloud?
Start with the [Prefect Cloud Overview](/ui/cloud/).

If you ran into any issues getting your first flow run with Prefect Cloud working, please join our community to ask questions or provide feedback:

[Prefect's Slack Community](https://www.prefect.io/slack/) is helpful, friendly, and fast growing - come say hi!

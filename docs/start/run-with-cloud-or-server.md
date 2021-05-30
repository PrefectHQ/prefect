# Quick Start

This tutorial guides you through writing and running a simple flow.  The second section also covers registering the flow using Prefect Cloud (or Prefect Server) and running it without configuring external storage.

## Set up your local environment

First, let's make sure that your local environment is set up to run Prefect.

Make sure you have a working `Python 3.6+` environment with the latest version of Prefect installed. If Prefect is not installed, you can install the latest version from the command line using the package manager of your choice, such as `pip` or `conda`:

```python
pip install prefect -U
conda install prefect -c conda-forge
```

## Run a Flow Using Prefect Core

```python
import prefect
from prefect import task, Flow

@task
def hello_task():
logger = prefect.context.get("logger")
logger.info("Hello world!")

flow = Flow("hello-flow", tasks=[hello_task])

flow.run()
```

Paste the code above into an interactive Python REPL session. You should see the following logs after running `flow.run()` :

```
[2020-01-08 23:49:00,239] INFO - prefect.FlowRunner | Beginning Flow run for 'hello-flow'
[2020-01-08 23:49:00,242] INFO - prefect.FlowRunner | Starting flow run.
[2020-01-08 23:49:00,249] INFO - prefect.TaskRunner | Task 'hello_task': Starting task run...
[2020-01-08 23:49:00,249] INFO - prefect.Task: hello_task | Hello world!
[2020-01-08 23:49:00,251] INFO - prefect.TaskRunner | Task 'hello_task': finished task run for task with final state: 'Success'
[2020-01-08 23:49:00,252] INFO - prefect.FlowRunner | Flow run SUCCESS: all reference tasks succeeded
```

If you're running into issues, check that your Python environment is properly set up to run Prefect. Refer to the [Prefect Core Installation](https://docs.prefect.io/core/getting_started/installation.html) documentation for further details.

## Select an Orchestration Backend

Prefect supports two different orchestration backends:

- `cloud` - our [hosted service](https://cloud.prefect.io)
- `server` - the [open source backend](/orchestration/server/overview.md),
  deployed on your infrastructure

To use Prefect with either backend, you must first select that backend via
the CLI:

:::: tabs
::: tab Cloud

```bash
$ prefect backend cloud
```

:::

::: tab Server

```bash
$ prefect backend server
```

:::
::::

Note that you can change backends at any time by rerunning the `prefect backend ...` command.

## Authenticating with Prefect Cloud <Badge text="Cloud"/>

To authenticate, you'll need to create an [API Key](/user/keys) and save it.

- In the user menu in the top right corner go to **Account Settings -> API Keys -> Create An API Key**.
- Copy the created key
- Save the key locally either in your `~/.prefect/config.toml` config file, or as an environment variable:

```bash
# ~/.prefect/config.toml
[cloud]
auth_token = <API_KEY>
```

```bash
export PREFECT__CLOUD__AUTH_TOKEN=<API_KEY>
```

### Create a Service Account Key

Running deployed Flows with an [Agent](https://docs.prefect.io/orchestration/agents/overview.html) also requires an API key for the Agent. You can create one in the [Service Accounts](/team/service-accounts) page of the UI.

You'll need this token later in the tutorial. You can save it locally either in your `~/.prefect/config.toml` config file, or as an environment variable:

```bash
# ~/.prefect/config.toml
[cloud.agent]
auth_token = <SERVICE_ACCOUNT_API_KEY>
```

```bash
export PREFECT__CLOUD__AGENT__AUTH_TOKEN=<SERVICE_ACCOUNT_API_KEY>
```

## Creating a project

Projects are used to organize flows that have been deployed to Prefect Cloud.

Every time you deploy a flow, you will need to specify a project to deploy into. There are no limits on the number of projects you can have, and you can always delete projects later. You can read more about interacting with projects [here](https://docs.prefect.io/cloud/concepts/projects.html).

You can create a project using the CLI:

```bash
prefect create project tester
```

You can also create a project using the project selector on the dashboard page of the UI or using the API.

## Deploy your flow with Universal Deploy

We're almost there! With a very slight modification to our flow code, we will be able to register our flow with Prefect Cloud and get a local agent running:

```python
import prefect
from prefect import task, Flow

@task
def hello_task():
    logger = prefect.context.get("logger")
    logger.info("Hello world!")

flow = Flow("hello-flow", tasks=[hello_task])

# flow.run() We could run our flow locally using the flow's run method but we'll be running this from Cloud!

flow.register(project_name="tester")
flow.run_agent()
```

Paste the code into your interactive Python REPL session. If all goes well, you should see the local agent process start to run. If you're seeing the error message `"No agent API token provided"`, try passing your API key explicitly to the `run_agent()` method:

```python
flow.run_agent(token="<SERVICE_ACCOUNT_API_KEY>")
```

And that's it! Your flow is now registered with Prefect Cloud, and an agent process is running on your local machine waiting to execute your flow runs. For now, your flow is stored on your local machine in your `~/.prefect directory`. You can configure this later through the use of Storage.

We call this pattern `"Universal Deploy"` because all it requires is a working Python environment to create a Prefect Deployment!

## Run Your Flow In Prefect Cloud or Prefect Server

To run your flow in Prefect Cloud (or Server), navigate to it from the `Flows` tab of the Dashboard and use the `Quick Run` button at the top of the page. This will run your flow with no additional settings.

You can use the `Run` tab on your flow page to pass parameters or context to your flow or to schedule a run for some point in the future. You can update default parameters and add or modify schedules by selecting the `Settings` tab on the flow page.

**Universal Deploy and Labels**

You may have noticed that both your registered flow and your local agent have labels associated with them. Specifically, your may have noticed that your flow had a single label set to the hostname of your local machine (e.g. "Janes-MacBook.local") and your agent had many labels, one of which was also the hostname of your machine.

This hostname label ensures that only local agents started on this machine can execute your registered flow. Without labels, your flow might get picked up by other agents running in your infrastructure, or your locally running agent would attempt to execute other flows - potentially even flows that it can't access!

Labels are a powerful feature of Prefect Cloud, providing fine control over exactly what flows your agents can execute. Keep an eye out for an upcoming tutorial that will cover running a flow with custom labels.

## Video Guides

Check out the Prefect YouTube channel for advice and guides such as [how to Deploy Prefect Server.](https://youtu.be/yjORjWHyKhg)

## Ideas and Tutorials from the Prefect Blog
The Prefect blog has lots of guides on getting started and ideas on simple ways to get started with Prefect

Learn how to get started with parallel computation: [Part 1](https://medium.com/the-prefect-blog/getting-started-with-parallel-computation-60da4850f0)[Part 2](https://medium.com/the-prefect-blog/prefect-getting-started-with-operationalizing-your-python-code-999a0bf1dda8)

[Get started with Prefect Cloud on AWS](https://medium.com/the-prefect-blog/seamless-move-from-local-to-aws-kubernetes-cluster-with-prefect-f263a4573c56)

[Set up Server on GCP](https://medium.com/the-prefect-blog/prefect-server-101-deploying-to-google-cloud-platform-47354b16afe2)

[Possible First Project](https://medium.com/the-prefect-blog/my-prefect-home-c05ebe625410)

[Using Notifiers](https://medium.com/the-prefect-blog/something-went-wrong-b3bd5899a1ef)
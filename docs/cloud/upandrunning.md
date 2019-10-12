# Prefect Cloud: Up and Running

In this guide, we will look at a minimal and quick way to get Prefect Cloud flow deployments up and running on your local machine. We will write a simple flow, build its Docker storage, deploy to Prefect Cloud, and orchestrate a run with the Local Agent. No extra infrastructure required!

### Prerequisites

In order to start using Prefect Cloud we need to set up our authentication. Head to the UI and retrieve a `USER` API token which we will use to log into Prefect Cloud. We are also going to want to generate a `RUNNER` token and save that in a secure place because we will use it later when creating our Local Agent. 

For information on how to create a `RUNNER` token visit the [Tokens](concepts/tokens.html) page.

Let's use the Prefect CLI to log into Cloud. Run this command, replacing `$PREFECT_USER_TOKEN` with the `USER` token you generated a moment ago:
```
$ prefect auth login --token $PREFECT_USER_TOKEN
Login successful!
```

Now you should be able to begin working with Prefect Cloud! Verify that you have a default project by running:
```
$ prefect get projects
NAME            FLOW COUNT  AGE         DESCRIPTION
Hello, World!   0           1 day ago
```

### Write a Flow

To start, we're going to write a dummy flow that doesn't do anything. You can make your flow as complex as you want, but this is the flow we'll use for the tutorial!

```python
from prefect import Flow

flow = Flow("my-flow") # empty dummy flow
```

### Deploying Flow to Cloud

::: tip Docker
Make sure that you have Docker installed and running in order for this step to work!
:::

Now that the flow is written and we want to call the `deploy` function which will build our flow's default Docker storage and then send some metadata to Prefect Cloud! Note that in this step no flow code or images ever leave your machine. We are going to deploy this flow to the Prefect Cloud project that we saw at the beginning of this guide.

```python
flow.deploy(project_name="Hello, World!")
```

A few things are happening in this step. First your flow will be serialized and placed into a local Docker image. By not providing a registry url, the step to push your image to a container registry is skipped entirely. Once the image finished building a small metadata description of the structure of your flow will be sent to Prefect Cloud.

::: warning Production
The decision to not push our image to a container registry is entirely for the purposes of this tutorial. In an actual production setting you would be pushing the images that contain your flows to a registry so they can be stored and retrieved by agents running on platforms other than your local machine.
:::

You should now be able to see the flow's Docker image on your machine if you would like by running `docker image list` in your command line.

After this deployment is complete you should be able to see your flow now exists in Prefect Cloud!

```
$ prefect get flows
NAME        VERSION    PROJECT NAME    AGE
my-flow     1          Demo            a few seconds ago
```

### Start Local Agent

In order to orchestrate runs of your flow we will need to boot up a Prefect Agent which will look for flow runs to execute. This is where the `RUNNER` token you generated earlier will become useful.

```
$ prefect agent start -t RUNNER_TOKEN

 ____            __           _        _                    _
|  _ \ _ __ ___ / _| ___  ___| |_     / \   __ _  ___ _ __ | |_
| |_) | '__/ _ \ |_ / _ \/ __| __|   / _ \ / _` |/ _ \ '_ \| __|
|  __/| | |  __/  _|  __/ (__| |_   / ___ \ (_| |  __/ | | | |_
|_|   |_|  \___|_|  \___|\___|\__| /_/   \_\__, |\___|_| |_|\__|
                                           |___/

2019-09-01 13:11:58,202 - agent - INFO - Starting LocalAgent
2019-09-01 13:11:58,203 - agent - INFO - Agent documentation can be found at https://docs.prefect.io/cloud/
2019-09-01 13:11:58,453 - agent - INFO - Agent successfully connected to Prefect Cloud
2019-09-01 13:11:58,453 - agent - INFO - Waiting for flow runs...
```

Here we use the Prefect CLI to start a Local Agent. The `RUNNER` token that was generated earlier is specified through the `--token` argument.

### Create a Flow Run

Now that the Local Agent is running we want to create a flow run in Prefect Cloud that the agent can pick up and execute! If you recall, we named our flow `my-flow` and deployed it to the `Hello, World!` project. We are going to use these two names in order to create the flow run with the Prefect CLI.

```
$ prefect run cloud -n my-flow -p "Hello, World!"
Flow Run ID: 43a6624a-c5ce-43f3-a652-55e9c0b20527
```

Our flow run has been created! We should be able to see this picked up in the agent logs:
```
2019-09-01 13:11:58,716 - agent - INFO - Found 1 flow run(s) to submit for execution.
2019-09-01 13:12:00,534 - agent - INFO - Submitted 1 flow run(s) for execution.
```

Now the agent has submitted the flow run and created a Docker container locally. We may be able to catch it in the act with `docker ps` but our flow doesn't do anything so it may run too fast for us! (Another option: Kitematic is a great tool for interacting with containers while they are live)

You can check on your flow run using Prefect Cloud:
```
$ prefect get flow-runs
NAME                FLOW NAME       STATE    AGE                START TIME
super-bat           my-flow         Success  a few seconds ago  2019-09-01 13:12:02
```

Congratulations! You ran a flow using Prefect Cloud! Now you can take it a step further and deploy a Prefect Agent on a high availability platform such as [Kubernetes](agent/kubernetes.html).

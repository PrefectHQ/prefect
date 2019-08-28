# Prefect Cloud: Up and Running

In this guide, we will look at a quick way to get Prefect Cloud flow deployments up and running on your local machine. We will write a simple flow, build its Docker storage, deploy to Prefect Cloud, and orchestrate a run with the Local Agent. No extra infrastructure required!

### Prerequisites

In order to start using Prefect Cloud we need to set up our authentication. Head to the UI and retrieve a `USER` API token which we will use to log into Prefect Cloud. We are also going to want to generate an `AGENT` token and save that in a secure place because we will use it later when creating our Local Agent.

Let's use the Prefect CLI to log into Cloud:
```
$ prefect auth login --token USER_TOKEN
Login successful
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

### Build Flow Storage

::: tip Docker
Make sure that you have Docker installed and running in order for this step to work!
:::

Typically, flow storage will be built on the deploy step to Cloud and shipped off to a registry but we are going to perform this guide without the need of an external container registry.

```python
from prefect.environments.storage import Docker

flow.storage = Docker(registry_url="")
flow.storage.add_flow(flow)
flow.storage = flow.storage.build(push=False)
```

A few things are happening in this step. First, we are giving the flow a storage option of Docker and specifying the registry as an empty string. We are doing this because this image is not being pushed to a container registry. Second, the flow is added to the definition of the Docker image and on build the flow will be serialized to byte code and placed into the image. Finally, the Docker image is being built on your machine without being pushed to a registry after build.

You should now be able to see the flow's Docker image on your machine if you would like by running `docker image list` in your command line.

### Deploying Flow to Cloud

Now that the flow is written and the storage is built locally we can deploy some metadata to Prefect Cloud! Note that in this step no flow code or images ever leave your machine.

```python
flow.deploy("Hello, World!", build=False)
```

We deploy this flow to the Prefect Cloud project that we saw at the beginning of this guide. On this deploy we are also choosing not to rebuild the flow's storage because we already did that in the prior step.

After this deployment is complete you should be able to see your flow now exists in Prefect Cloud!

```
$ prefect get flows
NAME        VERSION    PROJECT NAME    AGE
my-flow     1          Demo            a few seconds ago
```

### Start Local Agent

In order to orchestrate runs of your flow we will need to boot up a Prefect Agent which will look for flow runs to execute. This is where the `AGENT` token you generated earlier will become useful.

```
$ prefect agent start -t AGENT_TOKEN --no-pull

 ____            __           _        _                    _
|  _ \ _ __ ___ / _| ___  ___| |_     / \   __ _  ___ _ __ | |_
| |_) | '__/ _ \ |_ / _ \/ __| __|   / _ \ / _` |/ _ \ '_ \| __|
|  __/| | |  __/  _|  __/ (__| |_   / ___ \ (_| |  __/ | | | |_
|_|   |_|  \___|_|  \___|\___|\__| /_/   \_\__, |\___|_| |_|\__|
                                           |___/

2019-09-01 13:11:58,202 - agent - INFO - Starting LocalAgent
2019-09-01 13:11:58,203 - agent - INFO - Agent documentation can be found at https://docs.prefect.io/cloud/agent
2019-09-01 13:11:58,453 - agent - INFO - Agent successfully connected to Prefect Cloud
2019-09-01 13:11:58,453 - agent - INFO - Waiting for flow runs...
```

Here we use the Prefect CLI to start a Local Agent. The `AGENT` token that was generated earlier is specified through the `--token` argument. We also pass the `--no-pull` flag to the agent start command. This is because we deployed our flow to Prefect Cloud without actually pushing our flow's Docker storage to a registry. The image exists locally on your machine (and does not have a specified registry) therefore we want to tell the Local Agent to not bother trying to pull the image.

### Create a Flow Run

Now that the Local Agent is running we want to create a flow run in Prefect Cloud that the agent can pick up and execute! If you recall, we named our flow `my-flow` and deployed it to the `Hello, World!` project. We are going to use these two names in order to create the flow run with the Prefect CLI.

```
$ prefect cloud run -n my-flow -p "Hello, World!"
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

Congratulations! You ran a flow using Prefect Cloud! Now you can take it a step further and deploy a Prefect Agent on a high availability platform such as [Kubernetes](https://docs.prefect.io/cloud/agent/kubernetes.html).

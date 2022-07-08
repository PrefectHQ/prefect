---
description: Learn how to run Prefect flows as Kubernetes Jobs using the Kubernetes flow runner.
tags:
    - Kubernetes
    - orchestration
    - flow runners
    - KubernetesFlowRunner
    - tutorial
---

# Running flows in Kubernetes

Prefect integrates with Kubernetes via the [flow runner interface](/concepts/flow-runners/). The [KubernetesFlowRunner](/api-ref/prefect/flow-runners/#prefect.flow_runners.KubernetesFlowRunner) runs Prefect flows on Kubernetes as Jobs. You can also can run the Orion API, UI, and agent on Kubernetes.

For this tutorial, we'll deploy a Orion flow to a local Kubernetes cluster.

## Requirements

To run the steps in this tutorial, you'll need a few easily configured prerequisites:

- `kubectl` configured to connect to a cluster.
- A remote [Storage](/concepts/storage/) configuration, not Local Storage or Temporary Local Storage.

An easy way to get started is to use [Docker Desktop](https://www.docker.com/products/docker-desktop), turning on the [Kubernetes server and client](https://docs.docker.com/desktop/kubernetes/) and Docker CLI integration.

You'll also need to configure a remote store such as S3, Google Cloud Storage, or Azure Blob Storage. See the [Storage](/concepts/storage/) documentation for details.

## A simple Kubernetes deployment

We'll create a simple flow that simply logs a message, indicating that it ran in the Kubernetes cluster. We'll include the [deployment specification](/concepts/deployments/#deployment-specifications) alongside the flow code.

Save the following script to the file `kubernetes-deployment.py`:

```python
from prefect import flow, get_run_logger
from prefect.deployments import DeploymentSpec
from prefect.flow_runners import KubernetesFlowRunner

@flow
def my_kubernetes_flow():
    logger = get_run_logger()
    logger.info("Hello from Kubernetes!")

DeploymentSpec(
    name="k8s-example",
    flow=my_kubernetes_flow,
    flow_runner=KubernetesFlowRunner()
)
```

Notice that this code is not significantly different from the example we used to demonstrate the `DockerFlowRunner` for running a flow in a Docker container &mdash; we just imported `KubernetesFlowRunner` and specified it as the flow runner for this deployment.


In future when we reference the deployment, we'll use the format "flow name/deployment name" &mdash; in this case, `my-kubernetes-flow/k8s-example`.

## Run Orion on Kubernetes

The easiest way to get started with the Kubernetes flow runner is to run Orion itself on Kubernetes.

The Prefect CLI includes a command that automatically generates a manifest that runs Orion as a Kubernetes deployment. By default, it simply prints out the YAML configuration for a manifest. You can pipe this output to a file of your choice and edit as necessary.

The default name for the deployment is "orion" and it uses a pre-built Prefect image for its containers.

In this case, we'll pipe the output directly to `kubectl` and apply the manifest to a Kubernetes cluster:

```bash
prefect kubernetes manifest orion | kubectl apply -f -
```

After applying the output of this command to your cluster, a Kubernetes deployment named "orion" should start running.

<div class='termy'>
```
$ prefect kubernetes manifest orion | kubectl apply -f -
deployment.apps/orion created
service/orion created
role.rbac.authorization.k8s.io/flow-runner created
rolebinding.rbac.authorization.k8s.io/flow-runner-role-binding created
```
</div>

Check the logs with `kubectl` to demonstrate that the deployment is running and an Prefect agent is ready to run a flow:

```bash
kubectl logs -lapp=orion --all-containers
```

You should see something like this indicating that the Orion API is running in Kubernetes:

<div class='termy'>
```
$ kubectl logs -lapp=orion --all-containers
INFO:     10.1.0.1:26106 - "POST /work_queues/48199460-6a55-45c1-a96f-baf849c8c25f/get_runs HTTP/1.1" 200 OK
INFO:     10.1.0.1:56253 - "POST /work_queues/48199460-6a55-45c1-a96f-baf849c8c25f/get_runs HTTP/1.1" 200 OK
INFO:     10.1.0.1:23968 - "POST /work_queues/48199460-6a55-45c1-a96f-baf849c8c25f/get_runs HTTP/1.1" 200 OK
INFO:     10.1.0.1:47196 - "POST /work_queues/48199460-6a55-45c1-a96f-baf849c8c25f/get_runs HTTP/1.1" 200 OK
INFO:     10.1.0.1:36464 - "POST /work_queues/48199460-6a55-45c1-a96f-baf849c8c25f/get_runs HTTP/1.1" 200 OK
INFO:     10.1.0.1:7321 - "POST /work_queues/48199460-6a55-45c1-a96f-baf849c8c25f/get_runs HTTP/1.1" 200 OK
INFO:     10.1.0.1:2044 - "POST /work_queues/48199460-6a55-45c1-a96f-baf849c8c25f/get_runs HTTP/1.1" 200 OK
INFO:     10.1.0.1:29042 - "POST /work_queues/48199460-6a55-45c1-a96f-baf849c8c25f/get_runs HTTP/1.1" 200 OK
INFO:     10.1.0.1:29406 - "POST /work_queues/48199460-6a55-45c1-a96f-baf849c8c25f/get_runs HTTP/1.1" 200 OK
INFO:     10.1.0.1:38615 - "POST /work_queues/48199460-6a55-45c1-a96f-baf849c8c25f/get_runs HTTP/1.1" 200 OK
Created kubernetes work queue 48199460-6a55-45c1-a96f-baf849c8c25f.
Starting agent connected to http://orion:4200/api...

  ___ ___ ___ ___ ___ ___ _____     _   ___ ___ _  _ _____
 | _ \ _ \ __| __| __/ __|_   _|   /_\ / __| __| \| |_   _|
 |  _/   / _|| _|| _| (__  | |    / _ \ (_ | _|| .` | | |
 |_| |_|_\___|_| |___\___| |_|   /_/ \_\___|___|_|\_| |_|


Agent started! Looking for work from queue 'kubernetes'...
19:46:51.179 | WARNING | prefect.agent - No work queue found named 'kubernetes'
```
</div>

This Kubernetes deployment runs the Orion API and UI servers, creates a [work queue](/concepts/work-queues/), and starts and agent &mdash; all within the cluster.

Don't worry about the `No work queue found named 'kubernetes'` warning here. A new Prefect Orion API server does not start with a default work queue from which the agent can pick up work. We'll create the work queue in a future step.

## Configure the Orion API on Kubernetes

To interact with the Prefect Orion API running in Kubernetes, we need to make sure of two things:

- The `prefect` command knows to talk to the Orion API running in Kubernetes
- We can visit the Orion UI running in Kubernetes

## Forward ports

First, use the `kubectl port-forward` command to forward a port on your local machine to an open port within the cluster.

```bash
kubectl port-forward deployment/orion 4200:4200
```

This forwards port 4200 on the default internal loop IP for localhost to the “orion” deployment. You’ll see output like this:

<div class='termy'>
```
$ kubectl port-forward deployment/orion 4200:4200
Forwarding from 127.0.0.1:4200 -> 4200
Forwarding from [::1]:4200 -> 4200
Handling connection for 4200
```
</div>

Keep this command running, and open a new terminal for the next commands. Make sure you change to the same directory as you were previously using and activate your Python virtual environment, if you're using one.

## Configure the API URL

Now we need to tell our local `prefect` command how to communicate with the Orion API running in Kubernetes.

In the new terminal session, run the `prefect config view` command to see your current Prefect settings. We're particularly interested in `PREFECT_API_URL`.

<div class='termy'>
```
$ prefect config view
PREFECT_PROFILE='default'
PREFECT_API_URL='http://127.0.0.1:4200/api'
```
</div>

If your `PREFECT_API_URL` is currently set to 'http://127.0.0.1:4200/api' or 'http://localhost:4200/api', great! Prefect is configured to communicate with the API at the address we're forwarding, so you can go to the next step.

If `PREFECT_API_URL` is not set as shown above, run the following Prefect CLI command to configure it for this tutorial:

```bash
prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api
```

Since we previously configured port forwarding for the localhost port to the Kubernetes environment, we’ll be able to interact with the Orion API running in Kubernetes when using local Prefect CLI commands.

## Configure storage

Now that we can communicate with the Orion API running on the Kubernetes cluster, lets configure [storage](/concepts/storage/) for flow and task run data.

Note that if you created remote storage for the [Docker flow runner tutorial](/tutorials/docker-flow-runner/#configure-storage), you'll still need to create a new storage configuration here: storage is configured on the Orion server, and in this case we need to configure storage on the server running in Kubernetes rather than the one you ran locally in the Docker tutorial.

Before doing this next step, make sure you have the information to connect to and authenticate with a remote data store. In this example we're connecting to an AWS S3 bucket, but you could also Google Cloud Storage or Azure Blob Storage.

Run the `prefect storage create` command. In this case we choose the S3 option and supply the bucket name and AWS IAM access key. You should use the details of a service and authentication method that you have configured.

<div class='termy'>
```
$ prefect storage create
Found the following storage types:
0) Azure Blob Storage
    Store data in an Azure blob storage container
1) Google Cloud Storage
    Store data in a GCS bucket
2) KV Server Storage
    Store data by sending requests to a KV server
3) Local Storage
    Store data in a run's local file system
4) S3 Storage
    Store data in an AWS S3 bucket
5) Temporary Local Storage
    Store data in a temporary directory in a run's local file system
Select a storage type to create: 4

You've selected S3 Storage. It has 6 option(s).
BUCKET: the-curious-case-of-benjamin-bucket
AWS ACCESS KEY ID (optional): XXXXXXXXXXXXXXXXXXXX
AWS SECRET ACCESS KEY (optional): XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
AWS SESSION TOKEN (optional):
PROFILE NAME (optional):
REGION NAME (optional):
Choose a name for this storage configuration: benjamin-bucket
Validating configuration...
Registering storage with server...
Registered storage 'benjamin-bucket' with identifier '0f536aaa-216f-4c72-9c31-f3272bcdf977'.
You do not have a default storage configuration. Would you like to set this as your default storage? [Y/n]: y
Set default storage to 'benjamin-bucket'.
```
</div>

We set this storage as the default for the server running in Kubernetes, and any flow runs orchestrated by this server can use the persistent S3 storage for flow code, task results, and flow results.

## Create a work queue

Work queues organize work that agents can pick up to execute. Work queues can be configured to make available deployments based on criteria such as tags, flow runners, or even specific deployments. Agents are configured to poll for work from specific work queues. To learn more, see the [Work Queues & Agents](/concepts/work-queues/) documentation.

To run orchestrated deployments, you'll need to set up at least one work queue and agent. As you saw earlier, there's already an agent running in Kubernetes, looking for a work queue.

For this project we'll configure a work queue that works with any Kubernetes-based agent.

In the terminal, use the `prefect work-queue create` command to create a work queue called "kubernetes". We don't pass any other options, so this work queue passes any scheduled flow runs to the waiting agent.

<div class='termy'>
```
$ prefect work-queue create kubernetes
UUID('3c482650-ea98-4eee-9b8d-c92a4b758d61')
```
</div>

## Create the deployment on Kubernetes

Now use the Prefect CLI to create the deployment, passing the file containing the flow code and deployment specification, `kubernetes-deployment.py`:

<div class='termy'>
```
$ prefect deployment create ./kubernetes-deployment.py
Loading deployments from python script at 'kubernetes-deployment.py'...
Created deployment 'k8s-example' for flow 'my-kubernetes-flow'
```
</div>

## Run a flow on Kubernetes

Now we can run the deployment using the `prefect deployment run` CLI command:

<div class='termy'>
```
$ prefect deployment run my-kubernetes-flow/k8s-example
Created flow run 'poetic-scorpion' (adb711df-e005-41c7-a822-9cb3ae2704f4)
```
</div>

You can also run the flow from the Prefect Orion UI. Open a browser tab and navigate to [http://127.0.0.1:4200](http://127.0.0.1:4200). You should see the flow run deployment “my-kubernetes-flow” and a successful flow run.

![Screenshot showing the "my-kubernetes-flow" flow](/img/tutorials/k8s-test-flow.png)

Click **Deployments** to see the entry for this deployment, `k8s-example`. You can run the flow interactively using the **Quick Run** button.

![Screenshot showing deployed “k8s-example” deployment](/img/tutorials/k8s-test-deploy.png)

Go ahead and kick off an ad-hoc flow run: click **Quick Run** to run the deployment a second time.

## Inspect flow run Jobs

Let's take a closer look at the `my-kubernetes-flow` flow runs we created from the `k8s-example` deployment.

Click **Flow Runs** to see that we did, in fact, create two flow runs that executed as Kubernetes Jobs.

![Screenshot showing flow runs for “k8s-example”](/img/tutorials/k8s-flow-runs.png)

Now select one of the flow runs by clicking on the flow run name &mdash; in this case I clicked "poetic-scorpion". Your flow names will be different.

![Screenshot showing details for the "poetic-scorpion" flow run](/img/tutorials/k8s-flow-run-logs.png)

Go to the **Logs** tab of your flow run. You should see the "Hello from Kubernetes!" log message created by the flow running in Kubernetes!

You can also inspect the Jobs directly through Kubernetes by using `kubectl`. Use `kubectl get jobs` to get the Jobs you just ran:

<div class='termy'>
```
$ kubectl get jobs -l app=orion
NAME                     COMPLETIONS   DURATION   AGE
impetuous-condorbwwmc    1/1           6s         16m
poetic-scorpion9m8tq     1/1           5s         31m
```
</div>

If you know the name of the specific flow run whose Job you want to find, using the flow run name and `kubectl get jobs` you can find the Jobs for that flow run (your flow run names may be different since they're automatically generated at flow run time):

```bash
kubectl get jobs -l io.prefect.flow-run-name=poetic-scorpion
```

Since each flow run is a Kubernetes Job, every Job starts a Pod, which in turn starts a container. You can use the `kubectl logs` command to see the logs for all Pods created by a specific Job:

<div class='termy'>
```
$ kubectl logs -l job-name=poetic-scorpion9m8tq
00:50:12.123 | INFO    | Flow run 'poetic-scorpion' - Using task runner 'ConcurrentTaskRunner'
00:50:12.155 | INFO    | Flow run 'poetic-scorpion' - Hello from Kubernetes!
00:50:12.806 | INFO    | Flow run 'poetic-scorpion' - Finished in state Completed(None)
```
</div>

You did it! The Kubernetes flow runner ran your flow as a Job in Kubernetes!

To continue experimenting with the flow in Kubernetes, make any changes to the flow definition and run `prefect deployment create` again for the flow file. This updates the deployment. Orion will pick up your changes for the next scheduled flow run.

## Cleaning up

When you're finished, just close the Prefect Orion UI tab in your browser, and close the terminal sessions running the port forwarding to your cluster.

You can use `kubectl` commands to remove the "orion" Kubernetes deployment. `kubectl get deployments` lists any Kubernetes deployments in your environment.

<div class='termy'>
```
$ kubectl get deployments
<div style="color:white; white-space:pre-wrap;">NAME    READY   UP-TO-DATE   AVAILABLE   AGE
orion   1/1     1            1           66m</div>
```
</div>

`kubectl delete deployments` removes the deployment from Kubernetes if you don't want to use it further.

<div class='termy'>
```
$ kubectl delete deployments orion
deployment.apps "orion" deleted
```
</div>

Follow the Docker Desktop instructions to [disable Kubernetes](https://docs.docker.com/desktop/kubernetes/#disable-kubernetes).

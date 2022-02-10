---
description: Learn how to run flow as Kubernetes Jobs using the KubernetesFlowRunner.
tags:
    - Kubernetes
    - orchestration
    - flow runners
    - KubernetesFlowRunner
    - tutorial
---

# Running flows in Kubernetes

Prefect integrates with Kubernetes via the [flow runner interface](/concepts/flow-runners/). The [KubernetesFlowRunner](/api-ref/prefect/flow-runners.md#prefect.flow_runners.KubernetesFlowRunner) runs Prefect flows on Kubernetes as Jobs. You can also can run the Orion API, UI, and agent on Kubernetes.

For this tutorial, we'll deploy a Orion flow to a local Kubernetes cluster run with Docker Desktop.

## Requirements

To run the steps in this tutorial, you'll need:

- [Docker Desktop](https://www.docker.com/products/docker-desktop) must be installed and running.
- Turn on the [Kubernetes server and client](https://docs.docker.com/desktop/kubernetes/) and Docker CLI integration in Docker Desktop.

## Running Orion on Kubernetes

The easiest way to get started with the Kubernetes flow runner is to run Orion itself on Kubernetes. 

The Prefect CLI includes a command that automatically generates a manifest that runs Orion as a Kubernetes deployment. By default, it simply prints out the YAML configuration for a manifest. You can pipe this output to a file of your choice and edit as necessary. The deployment portion of the manifest looks like this:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orion
spec:
  selector:
    matchLabels:
      app: orion
  replicas: 1  # We're using SQLite, so we should only run 1 pod
  template:
    metadata:
      labels:
        app: orion
    spec:
      containers:
      - name: api
        image: prefecthq/prefect:dev-python3.8
        command: ["prefect", "orion", "start", "--host", "0.0.0.0", "--no-agent", "--log-level", "DEBUG"]
        imagePullPolicy: "IfNotPresent"
        ports:
        - containerPort: 4200
      - name: agent
        image: prefecthq/prefect:dev-python3.8
        command: [ "prefect", "agent", "start"]
        imagePullPolicy: "IfNotPresent"
        env:
          - name: PREFECT_ORION_HOST
            value: http://orion:4200/api
```

You can see that the default name for the deployment is "orion" and it uses a pre-built `prefecthq/prefect:dev-python3.8` image for its containers.

In this case, we'll pipe the output directly to `kubectl` and apply the manifest to a Kubernetes cluster:

```bash
prefect orion kubernetes-manifest | kubectl apply -f -
```

After applying the output of this command to your cluster, a Kubernetes deployment named "orion" should start running.

```bash
deployment.apps/orion configured
service/orion unchanged
role.rbac.authorization.k8s.io/flow-runner created
rolebinding.rbac.authorization.k8s.io/flow-runner-role-binding created
```

Check the logs with `kubectl` to demonstrate that the deployment is running and an Prefect agent is ready to run a flow:

```bash
kubectl logs -lapp=orion --all-containers
```

You should see something like this:

```bash
Configure Prefect to communicate with the server with:

    PREFECT_ORION_HOST=http://0.0.0.0:4200/api

Check out the dashboard at <http://0.0.0.0:4200>

The agent has been disabled. Start an agent with `prefect agent start`.

Starting agent connected to <http://localhost:4200/api>...

  ___ ___ ___ ___ ___ ___ _____     _   ___ ___ _  _ _____
 | _ \\ _ \\ __| __| __/ __|_   _|   /_\\ / __| __| \\| |_   _|
 |  _/   / _|| _|| _| (__  | |    / _ \\ (_ | _|| .` | | |
 |_| |_|_\\___|_| |___\\___| |_|   /_/ \\_\\___|___|_|\\_| |_|

Agent started!

```

This Kubernetes deployment runs the Orion API and UI servers in one container and the agent process in another container, both using pre-built Prefect container images. 

## Forwarding Orion ports to Kubernetes

Next, we'll run a flow in Kubernetes. But before we do, we need to make sure of two things:

- The `prefect` command knows to talk to the Orion API running Kubernetes
- We can visit the Orion UI, running in Kubernetes

To do this, use the `kubectl port-forward` command to forward a port on your local machine to an open port within the cluster. 

```bash
kubectl port-forward deployment/orion 4200:4200
```

This forwards port 4200 on the default internal loop IP for localhost to the “orion” deployment. You’ll see output like this:

```bash
Forwarding from 127.0.0.1:4200 -> 4200
Forwarding from [::1]:4200 -> 4200
```

Keep this command running, and open a new terminal for the next commands.

## Running flows on Kubernetes

Now that we have Orion running on Kubernetes, let's talk about running your actual flows and tasks on Kubernetes. To demonstrate this, we’ll do three things:

- Set an environment variable to so we can communicate with the Orion API running in Kubernetes.
- Create a flow and deployment that will run in Kubernetes.
- Inspect our flow runs that are executing in the Kubernetes cluster.

## Configure communication with the cluster

Before we do anything else, we need to tell our local `prefect` command how to communicate with the Orion API running in Kubernetes.

To do this, set the `PREFECT_ORION_HOST` environment variable:

```bash
export PREFECT_ORION_HOST=http://localhost:4200/api
```

Since we previously configured port forwarding for the localhost port to the Kubernetes environment, we’ll be able to interact with the Orion API running in Kubernetes when using local Prefect CLI commands.

## Creating a flow and deployment

Now that the environment is configured, we can write a flow that runs on the "orion" cluster. Specifying the [KubernetesFlowRunner](/api-ref/prefect/flow-runners.md#prefect.flow_runners.KubernetesFlowRunner) runs your flow as a Kubernetes job.

You can think of a deployment as a way to tell Prefect when and how to run flows on a schedule. Using a flow runner requires creating a Prefect deployment for your flow.

Let's configure a new deployment that runs a flow using the Kubernetes flow runner. This deployment will run a flow that prints "Hello from Kubernetes!" every 30 seconds.

To test out this flow, paste this code into a file named `k8s_flow.py`.

```python
from prefect import flow
from prefect.deployments import DeploymentSpec
from prefect.flow_runners import KubernetesFlowRunner

@flow
def test_flow():
    print("Hello from Kubernetes!")

DeploymentSpec(
    flow=test_flow,
    name="test-deployment",
    flow_runner=KubernetesFlowRunner(stream_output=True),
)
```

Note that the flow itself is incredibly simple &mdash; it just prints a message &mdash; but you could put more sophisticated flow logic here and even call tasks or subflows.

This code also includes a [deployment specification](/concepts/deployments/#deployment-specifications) that specifies we want to use the Kubernetes flow runner.

Now, use the Prefect CLI to [create the deployment](/concepts/deployments/#creating-deployments):

```bash
prefect deployment create k8s_flow.py
```

Running this command creates a deployment in the Prefect Orion backend, or updates an existing deployment if you’ve run this tutorial before.

Once you’ve created a deployment, you can use it to schedule a flow run:

```bash
prefect deployment run test-flow/test-deployment
```

Go to the Orion UI — open a browser tab and navigate to [http://127.0.0.1:4200](http://127.0.0.1:4200) — you should see the flow run deployment “test-flow” and a successful flow run.

![Screenshot showing the "test-flow" flow]()

Click **Deployments** to see the entry for this deployment, “test-deployment”. You can run the flow interactively using the **Quick Run** button. 

![Screenshot showing deployed “test-deployment” flow deployment]()

If you click **Flow Runs** you should see the completed flow runs for this deployment that ran in the cluster.

![Screenshot showing flow runs for “test-deployment”]()

## Inspecting flow run jobs

Once the Prefect agent successfully runs a flow using Kubernetes, you'll start to see Jobs for your flow runs. You can use `kubectl get jobs` to get Orion's Jobs like this:

```bash
kubectl get jobs -l app=orion
```

You should see a list of Jobs for flow runs similar to this:

```bash
# ToDo: output goes here 
```

If you know the name of the flow run whose jobs you want to find, you can also find Jobs for a specific flow run. You can see these in the Orion UI flow run listing as well as in the list of Jobs that there was a Job for flow run `name here`:

```bash
# ToDo: output of example line goes here 
```

Using the flow run name and `kubectl get jobs` we can find the Jobs for that flow run (your flow run names may be different since they're automatically generated at flow run time):

```bash
kubectl get jobs -l io.prefect.flow-run-name=flashy-ant
```

Since each flow run is a Kubernetes Job, every Job starts a Pod, which in turn starts a container. You can use the following command to see the logs for all Pods created by a specific Job:

```bash
kubectl logs -l job-name=flashy-antbqxjq
```

If your agent is processing scheduled flow runs with the Kubernetes flow runner correctly, you should see logging output like the following from the Job's Pods when you run the previous command:

```
08:06:28.522 | INFO    | Flow run 'flashy-ant' - Using task runner 'SequentialTaskRunner'
08:06:28.717 | INFO    | Flow run 'flashy-ant' - Finished in state Completed(None)
Hello from Kubernetes!

```

You did it! The new Kubernetes flow runner ran your flow in Kubernetes!

To continue experimenting with the flow in Kubernetes, make any changes to the flow definition and run `prefect deployment create` again for the flow file. This updates the deployment. Orion will pick up your changes for the next scheduled flow run.

To stop scheduled flow runs, comment out or remove the `schedule=` line from the deployment specification and update the deployment. 

To clean up your cluster, follow the Docker Desktop instructions to [disable Kubernetes](https://docs.docker.com/desktop/kubernetes/#disable-kubernetes).

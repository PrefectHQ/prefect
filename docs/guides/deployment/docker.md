---
description: Learn how to store your flow code in a Docker image and serve your flow on any docker-compatible infrastructure.
tags:
    - Docker
    - containers
    - orchestration
    - infrastructure
    - deployments
search:
  boost: 2
---

# Running flows with Docker

In the [Deployments](/tutorial/deployments/) tutorial, we looked at serving a flow that enables scheduling or creating flow runs via the Prefect API.

With our Python script in hand, we can build a Docker image for our script, allowing us to serve our flow in various remote environments. We'll use Kubernetes in this guide, but you can use any Docker-compatible infrastructure.

In this guide we'll:

- Write a Dockerfile to build an image that stores our Prefect flow code.
- Build a Docker image for our flow.
- Deploy and run our Docker image on a Kubernetes cluster.

## Prerequisites

To complete this guide, you'll need the following:

- A Python script that defines and serves a flow. 
  - We'll use the flow script and deployment from the [Deployments](/tutorial/deployments/) tutorial. 
- Access to a running Prefect API server.
  - You can sign up for a forever free [Prefect Cloud account](https://docs.prefect.io/cloud/) or run a Prefect API server locally with `prefect server start`.
- [Docker Desktop](https://docs.docker.com/desktop/) installed on your machine.

## Writing a Dockerfile

First let's make a clean directory to work from, `prefect-docker-guide`.

<div class="terminal">
```bash
mkdir prefect-docker-guide
cd prefect-docker-guide
```
</div>

In this directory, we'll create a sub-directory named `flows` and put our flow script from the [Deployments](/tutorial/deployments/) tutorial in it.

<div class="terminal">
```bash
mkdir flows
cd flows
touch prefect-docker-guide-flow.py
```
</div>

Here's the flow code for reference:

```python title="prefect-docker-guide-flow.py"
import httpx
from prefect import flow


@flow(log_prints=True)
def get_repo_info(repo_name: str = "PrefectHQ/prefect"):
    url = f"https://api.github.com/repos/{repo_name}"
    response = httpx.get(url)
    response.raise_for_status()
    repo = response.json()
    print(f"{repo_name} repository statistics 🤓:")
    print(f"Stars 🌠 : {repo['stargazers_count']}")
    print(f"Forks 🍴 : {repo['forks_count']}")


if __name__ == "__main__":
    get_repo_info.serve(name="prefect-docker-guide")
```

The next file we'll add to the `prefect-docker-guide` directory is a `requirements.txt`. We'll include all dependencies required for our `prefect-docker-guide-flow.py` script in the Docker image we'll build.

<div class="terminal">
```bash
touch requirements.txt
```
</div>

Here's what we'll put in our `requirements.txt` file:

```txt title="requirements.txt"
prefect>=2.12.0
httpx
```

Next, we'll create a `Dockerfile` that we'll use to create a Docker image that will also store the flow code. 

<div class="terminal">
```bash
touch Dockerfile
```
</div>

We'll add the following content to our `Dockerfile`:

```dockerfile title="Dockerfile"
# We're using the latest version of Prefect with Python 3.9
FROM prefecthq/prefect:2-python3.9

# Add our requirements.txt file to the image and install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt --trusted-host pypi.python.org --no-cache-dir

# Add our flow code to the image
COPY flows /opt/prefect/flows

# Run our flow script when the container starts
CMD ["python", "flows/prefect-docker-guide-flow.py"]
```

## Building a Docker image

Now that we have a Dockerfile we can build our image by running: 

<div class="terminal">
```bash
docker build -t prefect-docker-guide-image .
```
</div>

And we can check that our image works by running:

<div class="terminal">
```bash
docker run -e PREFECT_API_URL=YOUR_PREFECT_API_URL -e PREFECT_API_KEY=YOUR_API_KEY prefect-docker-guide-image
```
</div>

The container should start up and serve the flow within the container!

!!!tip Prefect API URL and API key
    In the `docker run` command above, we're passing in the Prefect API URL and API key as environment variables.

    If you are using Prefect Cloud, you will need an Prefect API URL and API key for your served flow to be able to communicate with the Prefect API. You can get an API key from the [API Keys](https://docs.prefect.io/2.12.0/cloud/users/api-keys/) section of the user settings in the Prefect UI.

    You can get the Prefect API URL for your current setup by running `prefect config view` in your terminal.

## Deploying to a remote environment

Now that we have a Docker image with our flow code embedded, we can deploy it to a remote environment! 

For this guide, we'll simulate a remote environment by using Kubernetes locally with Docker Desktop. You can use the [instructions provided by Docker to set up Kubernetes locally.](https://docs.docker.com/desktop/kubernetes/) 

### Creating a Kubernetes deployment manifest

To ensure the process serving our flow is always running, we'll create a [Kubernetes deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/). If our flow's container ever crashes, Kubernetes will automatically restart it, thus ensuring that we won't miss any scheduled runs.

First, we'll create a `deployment-manifest.yaml` file in our `prefect-docker-guide` directory:

<div class="terminal">
```bash
touch deployment-manifest.yaml
```
</div>

And we'll add the following content to our `deployment-manifest.yaml` file:

```yaml title="deployment-manifest.yaml"
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prefect-docker-guide
spec:
  replicas: 1
  selector:
    matchLabels:
      flow: get-repo-info
  template:
    metadata:
      labels:
        flow: get-repo-info
    spec:
      containers:
      - name: flow-container
        image: prefect-docker-guide-image:latest
        env:
        - name: PREFECT_API_URL
          value: YOUR_PREFECT_API_URL
        - name: PREFECT_API_KEY
          value: YOUR_API_KEY
        # Never pull the image because we're using a local image
        imagePullPolicy: Never
```

This manifest defines how our image will run when deployed in our Kubernetes cluster. Note that we will be running a single replica of our flow container. If you want to run multiple replicas of your flow container to keep up with an active schedule, or because our flow is resource-intensive, you can increase the `replicas` value.

!!!tip Keep your API key secret
    In the above manifest we are passing in the Prefect API URL and API key as environment variables. This approach is simple, but it is not secure. If you are deploying your flow to a remote cluster, you should use a [Kubernetes secret](https://kubernetes.io/docs/concepts/configuration/secret/) to store your API key.

### Deploying our flow to the cluster

Now that we have a deployment manifest, we can deploy our flow to the cluster by running:

<div class="terminal">
```bash
kubectl apply -f deployment-manifest.yaml
```
</div>

We can monitor the status of our Kubernetes deployment by running:

<div class="terminal">
```bash
kubectl get deployments
```
</div>

Once the deployment has successfully started, we can check the logs of our flow container by running the following:

<div class="terminal">
```bash
kubectl logs -l flow=get-repo-info
```
</div>

Now that we're serving our flow in our cluster, we can trigger a flow run by running:

<div class="terminal">
```bash
prefect deployment run get-repo-info/prefect-docker-guide
```
</div>

If we navigate to the URL provided by the `prefect deployment run` command, we can follow the flow run via the logs in the Prefect UI!

## Conclusion

After going through this guide you should be armed with the knowledge to serve your flows in various environments using Docker.

We only served a single flow in this guide, but you can extended this guide to serve multiple flows in a single Docker image by updating your Python script to using `flow.to_deployment` and `serve` to serve multiple flows or the same flow with different configuration.

To learn more about deploying flows, check out the [Deployments](/concepts/deployments/) concept doc!
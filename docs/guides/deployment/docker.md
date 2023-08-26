---
description: Learn how to store your flow code in a Docker image and build Prefect deployments that create flow runs in Docker containers.
tags:
    - Docker
    - containers
    - orchestration
    - infrastructure
    - deployments
search:
  boost: 2
---

# Running flows in a Docker container

In this guide, we'll see how to run flows in a Docker container.
We'll see how we can use work pools to configure a Prefect deployment to run flow runs in Docker containers.
We'll also see how we can store our flow code inside of a Docker image.

## Prerequisites

To run a deployed flow in a Docker container, you'll need the following:

- A connection to a self-hosted [Prefect server]() or [Prefect Cloud]() account. TK
- [Docker Engine](https://docs.docker.com/engine/) installed and running on the same machine as your worker.

[Docker Desktop](https://www.docker.com/products/docker-desktop) works fine for local testing if you don't already have Docker Engine configured in your environment.

## Flow code

In the root of your project directory, create a file named `flows.py` with your flow code in it.

```python

from prefect import flow

@flow
def docker_flow():
    return "Hello, Docker!"
```

## Create a Docker work pool

Go to

Workers will poll the server for scheduled flow runs.
When a flow run is executed, the worker will spin up the Docker container as specified in our work pool and with any deployment-specific overrides, and track flow run.

## Create a deployment

We have several options for creating a deployment with Docker:

1. Use the guided deployment experience with `prefect deploy` that will create a deployment and output a `prefect.yaml`.
1. Use `prefect init` to create a `prefect.yaml` file from a template and then deploy it with `prefect deploy`.

Let's use the guided deployment experience.

### Guided deployment experience

In the root folder of your project, run `prefect deploy`.

Select the flow you want to deploy from the list of flows.

Enter a name for your deployment. Let's use `docker-deployment`.

Select `n` for no schedule.

## Getting other Python packages into your deployment

Options:

1. Add environment variables extra pip packages to your work pool
1. Hardcode in your Dockerfile
1. Specify requirements.txt file in your Dockerfile
1. Build step include install from requirements.txt file will auto-build in your dockerfile

### Flow code storage

The next file you will add to the `docker-tutorial` directory is a `requirements.txt`.  In this file make sure to include all dependencies that are required for your `docker-tutorial-flow.py` script.  

Next, you will create a `Dockerfile` that will be used to create a Docker image that will also store the flow code.  This `Dockerfile` should look similar to the following:  

```bash
FROM prefecthq/prefect:2-python3.9
COPY requirements.txt .
RUN pip install -r requirements.txt --trusted-host pypi.python.org --no-cache-dir
ADD flows /opt/prefect/flows
```

Finally, we build this image by running:

```bash
docker build -t docker-tutorial-image .
```

This will create a Docker image in your Docker repository with your Prefect flow stored in the image.  

## Prefect.yaml File

Now that you have created a Docker image that stores your Prefect flow code, you're going to make use of Prefect's deployment recipes. In your terminal, run:

<div class="terminal">
```bash
prefect init --recipe docker
```
</div>

You will see a prompt to input values for image name and tag, lets use:

```
image_name: docker-tutorial-image
tag: latest
```

This will create a `prefect.yaml` file for us populated with some fields. By default, it will look like this:

```yaml
# Welcome to your prefect.yaml file! You can use this file for storing and managing
# configuration for deploying your flows. We recommend committing this file to source
# control along with your flow code.

# Generic metadata about this project
name: docker-tutorial
prefect-version: 2.10.16

# build section allows you to manage and build docker images
build:
- prefect_docker.deployments.steps.build_docker_image:
    id: build_image
    requires: prefect-docker>=0.3.0
    image_name: docker-tutorial-image
    tag: latest
    dockerfile: auto
    push: true

# push section allows you to manage if and how this project is uploaded to remote locations
push: null

# pull section allows you to provide instructions for cloning this project in remote locations
pull:
- prefect.deployments.steps.set_working_directory:
    directory: /opt/prefect/docker-tutorial

# the deployments section allows you to provide configuration for deploying flows
deployments:
- name: null
  version: null
  tags: []
  description: null
  schedule: {}
  flow_name: null
  entrypoint: null
  parameters: {}
  work_pool:
    name: null
    work_queue_name: null
    job_variables:
      image: '{{ build_image.image }}'
```

Once you have made any updates you would like to this `prefect.yaml` file, in your terminal run:

<div class="terminal">
```bash
prefect deploy
```
</div>

The Prefect deployment wizard will walk you through the deployment experience to deploy your flow in either Prefect Cloud or your local Prefect Server.  Once the flow is deployed, you can even save the configuration to your `prefect.yaml` file for faster deployment in the future.

## Cleaning up

When you're finished, just close the Prefect UI tab in your browser, and close the terminal sessions running the Prefect server and agent.

---
description: Learn how to build Prefect deployments that create flow runs in Docker containers.
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

In the [Deployments](/tutorial/deployments/) tutorial, we looked at creating configuration that enables creating flow runs via the API and with code that was uploaded to a remotely accessible location.  

In this guide, we'll further configure the deployment so flow runs are executed in a Docker container. We'll run our Docker instance locally, but you can extend this guide to run it on remote machines.

In this guide we'll:

- Configure a [build step](/concepts/deployments#build) which will build a docker image on our behalf
- Build and register a new `log_flow.py` deployment that uses the new image.
- Create a flow run from this deployment that spins up a Docker container and executes, logging a message.

## Prerequisites

To run a deployed flow in a Docker container, you'll need the following:

- We'll use the flow script and deployment from the [Deployments](/tutorial/deployments/) tutorial. 
- You must run a standalone Prefect server (`prefect server start`) or use Prefect Cloud.
- You'll need [Docker Engine](https://docs.docker.com/engine/) installed and running on the same machine as your agent.

[Docker Desktop](https://www.docker.com/products/docker-desktop) works fine for local testing if you don't already have Docker Engine configured in your environment.

!!! note "Run a Prefect server"
    This guide assumes you're already running a Prefect server with `prefect server start`, as described in the [Deployments](/tutorial/deployments/) tutorial.
    
    If you shut down the server, you can start it again by opening another terminal session and starting the Prefect server with the `prefect server start` CLI command.

## Prefect.yaml File

First let's create a directory to work from, calling it `docker-tutorial`.

We're going to make use of Prefect's deployment recipes. Next, in your terminal run:

<div class="terminal">
```bash
prefect init --recipe docker
```
</div>

You will see a prompt to input values for image name and tag, lets use:
```
image_name: prefect-docker-tutorial
tag: latest
```

This will create a `prefect.yaml` file for us populated with some fields, by default it will look like this:

```yaml
# Welcome to your prefect.yaml file! You can you this file for storing and managing
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
    image_name: prefect-docker-tutorial
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

A few callouts

## Cleaning up

When you're finished, just close the Prefect UI tab in your browser, and close the terminal sessions running the Prefect server and agent.

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
Finally, we'll see the Prefect-maintained Docker images and discuss options for use.

## Prerequisites

To run a deployed flow in a Docker container, you'll need the following:

- A connection to a self-hosted [Prefect server]() or [Prefect Cloud]() account. TK
- [`prefect-docker`]() package installed.
- [Docker Engine](https://docs.docker.com/engine/) installed and running on the same machine as your worker.

[Docker Desktop](https://www.docker.com/products/docker-desktop) works fine for local testing if you don't already have Docker Engine configured in your environment.

## Flow code

In the root of your project directory, create a file named `flows.py` with your flow code in it.
Here's a very basic example flow for testing.

```python

from prefect import flow

@flow
def docker_flow():
    return "Hello, Docker!"
```

## Create a Docker work pool

[Work pools](/concepts/work-pools/) allow you to manage deployment infrastructure.
We'll configure the default values for our Kubernetes base job template.
Note that these values can be overridden by individual deployments.

Let's switch to the Prefect Cloud UI, where we'll create a new Kubernetes work pool (alternatively, you could use the Prefect CLI to create a work pool).

1. Click on the **Work Pools** tab on the left sidebar
1. Click the **+** button at the top of the page
1. Select **Docker** as the work pool type
1. Click **Next** to configure the work pool settings

Let's look at a few popular configuration options.

**Environment Variables**
Add environment variables to set when starting a flow run.
You can specify Python packages to install at runtime with `{"EXTRA_PIP_PACKAGES":"my_package"}`. For example `{"EXTRA_PIP_PACKAGES":"pandas==1.2.3"}` will install pandas version 1.2.3.
Alternatively, you can specify package installation in a custom Dockerfile, which can allow you to take advantage of image caching.
As we'll see below, Prefect can help us create a Dockerfile with our flow code and the packages specified in a `requirements.txt` file baked in.

**Image**
Specify the Docker container image for created jobs. If not set, the latest Prefect 2 image will be used.

**Image Pull Policy**
Select from the dropdown options to specify when to pull the image.

Workers will poll the server for scheduled flow runs.
When a flow run is executed, the worker will spin up the Docker container as specified in our work pool and with any deployment-specific overrides, and track flow run.

## Create a deployment

We have several options for creating a deployment with Docker:

1. Use the guided deployment experience with `prefect deploy` to create a deployment and output a `prefect.yaml`.
1. Use `prefect init` to create a `prefect.yaml` file from a template and then deploy it with `prefect deploy`.

Let's use the guided deployment experience.

### Guided deployment experience

In the root folder of your project, run `prefect deploy`.

Select the flow you want to deploy from the list of flows.

Enter a name for your deployment. Let's use `docker-deployment`.

Select `n` for no schedule.

Select a Docker work pool.

When prompted `Would you like to build a custom Docker image for this deployment? [y/n] (n):`

Select `y` to build a custom Docker image for this deployment.

`Repository name (e.g. your Docker Hub username):`

`Image name (docker-deployment):` is autopopulated with the deployment name. Let's use that.
`Image tag (latest):` works fine for our purposes.

```
Image discdiver/docker-deployment:latest will be built.
? Would you like to push this image to a remote 
registry? [y/n] (n):
```

Note that you must be authenticated through the CLI if you would like to push your image to a remote registry.

Dockerhub is the default registry, but you can specify a different registry by entering the URL.

```
Registry URL (docker.io):
```

```
Is this a private registry? [y/n]:
```

```
Would you like use prefect-docker to manage Docker 
registry credentials? [y/n] (n):
```

If you select `y`, you will be prompted to enter your Dockerhub username and password. Prefect will create a Docker Registry block on the server to store your credentials.

You should see the image being built and pushed in the CLI

You will then be prompted to create a `prefect.yaml` file with the deployment configuration.

```
Would you like to save configuration for this deployment for faster deployments in the future? [y/n]
```

## Adding Python packages into your deployment

The Prefect package is already installed in the Docker image, but you may want to add additional packages to your deployment.

Options:

1. Add environment variables extra pip packages to your work pool as shown above
1. Install packages from a `requirements.txt` file in your hand-made Dockerfile.
1. Add a `requirements.txt` file to your folder and allow Prefect to auto-build a Dockerfile that includes the packages.

If you want to create your own `Dockerfile`, you can base it on the one below

```bash
FROM prefecthq/prefect:2-python3.11
COPY requirements.txt .
RUN pip install -r requirements.txt --trusted-host pypi.python.org --no-cache-dir
ADD flows /opt/prefect/flows
```

## Flow code storage

Your flow code can be stored in a variety of places.

1. Bake your flow code into your Docker image. This can allow you to take advantage of image caching in some cases.
1. Store your flow code in a git-based repository or cloud provider. See the flow code [storage guide](/guides/deployment/storage-guide/) for more details.

If you would prefer to use flow code stored in a git-based repository or cloud provider, just specify that in the `prefect.yaml` file. A template for a Dockerfile with git-based storage is available by running `prefect init --recipe docker-git`.

TK list pull step

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
name: demos
prefect-version: 2.11.5

# build section allows you to manage and build docker images
build:
- prefect_docker.deployments.steps.build_docker_image:
    requires: prefect-docker>=0.3.1
    id: build-image
    dockerfile: auto
    image_name: docker.io/discdiver/docker-deployment
    tag: latest

# push section allows you to manage if and how this project is uploaded to remote locations
push:
- prefect_docker.deployments.steps.push_docker_image:
    requires: prefect-docker>=0.3.1
    image_name: '{{ build-image.image_name }}'
    tag: '{{ build-image.tag }}'
    credentials: '{{ prefect_docker.docker-registry-credentials.docker_registry_creds_name
      }}'

# pull section allows you to provide instructions for cloning this project in remote locations
pull:
- prefect.deployments.steps.set_working_directory:
    directory: /opt/my_directory

# the deployments section allows you to provide configuration for deploying flows
deployments:
- name: docker-deployment
  version: null
  tags: []
  description: null
  entrypoint: flows.py:docker_flow
  parameters: {}
  work_pool:
    name: docker-pool
    work_queue_name: null
    job_variables:
      image: '{{ build-image.image }}'
  schedule: null
```

In the future, you can make updates to this `prefect.yaml` file, and redeploy it with `prefect deploy`.

## Prefect-maintained Docker images

Every release of Prefect results in several new Docker images.
These images are all named [prefecthq/prefect](https://hub.docker.com/r/prefecthq/prefect) and their
**tags** identify their differences.

### Image tags

When a release is published, images are built for all of Prefect's supported Python versions.
These images are tagged to identify the combination of Prefect and Python versions contained.
Additionally, we have "convenience" tags which are updated with each release to facilitate automatic updates.

For example, when release `2.11.5` is published:

1. Images with the release packaged are built for each supported Python version (3.8, 3.9, 3.10, 3.11) with both standard Python and Conda.
2. These images are tagged with the full description, e.g. `prefect:2.1.1-python3.10` and `prefect:2.1.1-python3.10-conda`.
3. For users that want more specific pins, these images are also tagged with the SHA of the git commit of the release, e.g. `sha-88a7ff17a3435ec33c95c0323b8f05d7b9f3f6d2-python3.10`
4. For users that want to be on the latest `2.1.x` release, receiving patch updates, we update a tag without the patch version to this release, e.g. `prefect.2.1-python3.10`.
5. For users that want to be on the latest `2.x.y` release, receiving minor version updates, we update a tag without the minor or patch version to this release, e.g. `prefect.2-python3.10`
6. Finally, for users who want the latest `2.x.y` release without specifying a Python version, we update `2-latest` to the image for our highest supported Python version, which in this case would be equivalent to `prefect:2.1.1-python3.10`.

!!! tip "Choose image versions carefully"
    It's a good practice to use Docker images with specific Prefect versions in production.

    Use care when employing images that automatically update to new versions (such as `prefecthq/prefect:2-python3.9` or `prefecthq/prefect:2-latest`).

### Standard Python

Standard Python images are based on the official Python `slim` images, e.g. `python:3.10-slim`.

| Tag                   |       Prefect Version       | Python Version  |
| --------------------- | :-------------------------: | -------------:  |
| 2-latest              | most recent v2 PyPi version |            3.10 |
| 2-python3.11          | most recent v2 PyPi version |            3.11 |
| 2-python3.10          | most recent v2 PyPi version |            3.10 |
| 2-python3.9           | most recent v2 PyPi version |            3.9  |
| 2-python3.8           | most recent v2 PyPi version |            3.8  |
| 2.X-python3.11        |             2.X             |            3.11 |
| 2.X-python3.10        |             2.X             |            3.10 |
| 2.X-python3.9         |             2.X             |            3.9  |
| 2.X-python3.8         |             2.X             |            3.8  |
| sha-&lt;hash&gt;-python3.11 |            &lt;hash&gt;           |            3.11 |
| sha-&lt;hash&gt;-python3.10 |            &lt;hash&gt;           |            3.10 |
| sha-&lt;hash&gt;-python3.9  |            &lt;hash&gt;           |            3.9  |
| sha-&lt;hash&gt;-python3.8  |            &lt;hash&gt;           |            3.8  |

### Conda-flavored Python

Conda flavored images are based on `continuumio/miniconda3`.
Prefect is installed into a conda environment named `prefect`.

| Tag                         |       Prefect Version       | Python Version  |
| --------------------------- | :-------------------------: | -------------:  |
| 2-latest-conda              | most recent v2 PyPi version |            3.10 |
| 2-python3.11-conda          | most recent v2 PyPi version |            3.11 |
| 2-python3.10-conda          | most recent v2 PyPi version |            3.10 |
| 2-python3.9-conda           | most recent v2 PyPi version |            3.9  |
| 2-python3.8-conda           | most recent v2 PyPi version |            3.8  |
| 2.X-python3.11-conda        |             2.X             |            3.11 |
| 2.X-python3.10-conda        |             2.X             |            3.10 |
| 2.X-python3.9-conda         |             2.X             |            3.9  |
| 2.X-python3.8-conda         |             2.X             |            3.8  |
| sha-&lt;hash&gt;-python3.11-conda |            &lt;hash&gt;           |            3.11 |
| sha-&lt;hash&gt;-python3.10-conda |            &lt;hash&gt;           |            3.10 |
| sha-&lt;hash&gt;-python3.9-conda  |            &lt;hash&gt;           |            3.9  |
| sha-&lt;hash&gt;-python3.8-conda  |            &lt;hash&gt;           |            3.8  |

## Building your own image

If your flow relies on dependencies not found in the default `prefecthq/prefect` images, you may want to build your own image. You can either
base it off of one of the provided `prefecthq/prefect` images, or build your own image.
See the [Docker guide](\guides\deployment\docker\) for discussion of how the Prefect CLI can help you build custom images with dependencies specifiied in a `requirements.txt` file.

By default, Prefect [work pools](/concepts/work-pools) that use containers refer to the `2-latest` image.
You can specify another image at work pool creation.
The work pool image choice can be overridden in individual deployments.

### Extending the `prefecthq/prefect` image manually

Here we provide an example `Dockerfile` for building an image based on
`prefecthq/prefect:2-latest`, but with `scikit-learn` installed.

```dockerfile
FROM prefecthq/prefect:2-latest

RUN pip install scikit-learn
```

### Choosing an Image Strategy

The options described above have different complexity (and performance) characteristics. For choosing a strategy, we provide the following recommendations:

- If your flow only makes use of tasks defined in the same file as the flow, or tasks that are part of `prefect` itself, then you can rely on the default provided `prefecthq/prefect` image.

- If your flow requires a few extra dependencies found on PyPI, you can use the default `prefecthq/prefect` image and set `prefect.deployments.steps.pip_install_requirements:` in the `pull`step to install these dependencies at runtime.

- If the installation process requires compiling code or other expensive operations, you may be better off building a custom image instead.

- If your flow (or flows) require extra dependencies or shared libraries, we recommend building a shared custom image with all the extra dependencies and shared task definitions you need. Your flows can then all rely on the same image, but have their source stored externally. This option can ease development, as the shared image only needs to be rebuilt when dependencies change, not when the flow source changes.

## Next steps

You've seen how to use Docker to deploy Prefect flows.
You've also learned about Docker image options for Prefect deployments.

Docker containers are the basis for most Prefect work pool options, including [Kubernetes](/guides/deployment/kubernetes), [serverless cloud provider options such as ECS, Cloud Run, and ACI](/guides/aci/), and serverless [push-based work pools](/guides/push-work-pools/) that don't require a worker.

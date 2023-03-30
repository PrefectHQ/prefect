---
description: Learn how Prefect projects allow you to easily manage your code and deployments.
tags:
    - work pools
    - workers
    - orchestration
    - flow runs
    - deployments
    - projects
    - storage
    - infrastructure
    - blocks
    - tutorial
---

# Projects<span class="badge beta"></span>

Prefect projects are the recommended way to organize and manage Prefect deployments; projects provide a minimally opinionated way to organize your code and configuration that is transparent and easy to debug.

A project is a directory of code and configuration for your workflows that can be customized for portability.

The main ingredients of a project are 3 files / directories:

- `.prefect/`: a hidden directory that designates the root for your project; basic metadata about the workflows within this project are stored here
- `deployment.yaml`: a YAML file that can be used to persist settings for one or more flow deployments
- `prefect.yaml`: a YAML file that contains procedural instructions for how to build relevant artifacts for this project's deployments, push those artifacts, and retrieve them at runtime by a Prefect worker


!!! tip "Projects require workers"
    Note that using a project to manage your deployments requires the use of workers.

## Initializing a project

Initializing a project is simple: within any directory that you plan to develop flow code, run:

<div class="terminal">
```bash
$ prefect project init
```
</div>

Note that you can run this command in a non-empty directory where you already have work as well.

This command will create your `.prefect/` directory along with the two YAML files `deployment.yaml` and `prefect.yaml`; if any of these files or directories already exist, they will not be altered or overwritten.

This command also attempts to pre-populate `prefect.yaml` with steps based on information already present within the directory; for example, if you initialize a project within a git repository, Prefect will automatically populate a `pull` step for you.

## Creating a basic deployment

Projects are most useful for creating deployments; let's walk through some examples right now.  

!!! note "Deployments require workers"
    The following examples require a worker to be running; for local examples you can start a local worker with `prefect worker start -t process -p local-work` and for examples that require Docker run `prefect worker start -t docker -p docker-work`.

### Local deployment

In this example, we'll create a project from scratch that runs locally.  Let's start by creating a new directory and making that our working directory and initializing a project:

<div class="terminal">
```bash
$ mkdir my-first-project
$ cd my-first-project
$ prefect project init
```
</div>

Next, let's create a flow by saving the following code in a new file called `api_flow.py`:

```python
# contents of my-first-project/api_flow.py

import requests
from prefect import flow


@flow(name="Call API", log_prints=True)
def call_api(url: str = "http://time.jsontest.com/"):
    """Sends a GET request to the provided URL and returns the JSON response"""
    resp = requests.get(url).json()
    print(resp)
    return resp
```

You can experiment by importing and running this flow in your favorite REPL; let's now elevate this flow to a [deployment](/tutorials/deployments) via the `prefect deploy` CLI command:

<div class="terminal">
```bash
$ prefect deploy ./api_flow.py:call_api \
    -n my-first-deployment \
    -p local-work
```
</div>

This command will create a new deployment for your `"Call API"` flow with the name `"my-first-deployment"` that is attached to the `local-work` work pool.

Note that Prefect has automatically done a few things for you:

- registered the existence of this flow with your local project
- created a description for this deployment based on the docstring of your flow function
- parsed the parameter schema for this flow function in order to expose an API for running this flow

You can customize all of this either by manually editing `deployment.yaml` or by providing more flags to the `prefect deploy` CLI command; CLI inputs will always be prioritized over hard-coded values in your deployment's YAML file.

Let's create two ad-hoc runs for this deployment and confirm things are healthy:
<div class="terminal">
```bash
$ prefect deployment run 'Call API/my-first-deployment'
$ prefect deployment run 'Call API/my-first-deployment' \
    --param url=https://cat-fact.herokuapp.com/facts/
```
</div>

You should now be able to monitor and confirm these runs were created and ran via your [server UI](/ui).

!!! tip "Flow registration"
    `prefect deploy` will automatically register your flow with your local project; you can register flows yourself explicitly with the `prefect project register-flow` command:
    <div class="terminal">
    ```bash
    $ prefect project register-flow ./api_flow.py:call_api
    ```
    </div>

    This pre-registration allows you to deploy based on name instead of entrypoint path:
    <div class="terminal">
    ```bash
    $ prefect deploy -f 'Call API' \
        -n my-first-deployment \
        -p local-work
    ```
    </div>

### Git-based deployment

In this example, we'll initialize a project from [a pre-built GitHub repository](https://github.com/PrefectHQ/hello-projects) and see how it is automatically portable across machines.

We start by cloning the remote repository and initializing a project within the root of the repo directory:

<div class="terminal">
```bash
$ git clone https://github.com/PrefectHQ/hello-projects
$ cd hello-projects
$ prefect project init
```
</div>

We can now proceed with the same steps as above to create a new deployment:

<div class="terminal">
```bash
$ git clone https://github.com/PrefectHQ/hello-projects
$ cd hello-projects
$ prefect project init
```
</div>


### Dockerized deployment

In this example, we extend the above two by dockerizing our setup and executing runs with the Docker Worker.

## Customizing the steps

For more information on what can be customized with `prefect.yaml`, check out the [Projects concept doc](/concepts/projects).

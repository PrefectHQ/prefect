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
    - recipes
---

# Projects<span class="badge beta"></span>

Prefect projects are the recommended way to organize and manage Prefect deployments; projects provide a minimally opinionated, transparent way to organize your code and configuration so that its easy to debug.

A project is a directory of code and configuration for your workflows that can be customized for portability.

The main components of a project are 3 files:

- [`deployment.yaml`](/concepts/projects/#the-deployment-yaml-file): a YAML file that can be used to specify settings for one or more flow deployments
- [`prefect.yaml`](/concepts/projects/#the-prefect-yaml-file): a YAML file that contains procedural instructions for building artifacts for this project's deployments, pushing those artifacts, and retrieving them at runtime by a Prefect worker
- [`.prefect/`](/concepts/projects/#the-prefect-directory): a hidden directory that designates the root for your project; basic metadata about the workflows within this project are stored here

<a name="worker-tip"></a>
!!! tip "Projects require workers"
    Note that using a project to manage your deployments requires the use of workers.  This tutorial assumes that you have already set up two work pools, each with a worker, which only requires a single CLI command for each:

    - **Local**: `prefect worker start -t process -p local-work`
    - **Docker**: `prefect worker start -t docker -p docker-work`

    Each command will automatically create an appropriately typed work pool with default settings.

## Initializing a project

Initializing a project is simple: within any directory that you plan to develop flow code, run:

<div class="terminal">
```bash
$ prefect project init
```
</div>

Note that you can safely run this command in a non-empty directory where you already have work, as well.

This command will create your `.prefect/` directory along with the two YAML files `deployment.yaml` and `prefect.yaml`; if any of these files or directories already exist, they will not be altered or overwritten.

!!! tip "Project Recipes"
    Prefect ships with multiple project recipes, which allow you to initialize a project with a more opinionated structure suited to a particular use.  You can see all available recipes by running:

    <div class="terminal">
    ```bash
    $ prefect project recipe ls
    ```
    </div>

    And you can use recipes with the `--recipe` flag:

    <div class="terminal">
    ```bash
    $ prefect project init --recipe docker
    ```
    </div>

    Providing this flag will prompt you for required variables needed to make the recipe work properly.  If you want to run this CLI programmatically, these required fields can be provided via the `--field` flag: `prefect project init --recipe docker --field image_name=my-image/foo --field tag=dev`.

    If no recipe is provided, the `init` command makes an intelligent choice of recipe based on local configuration; for example, if you initialize a project within a git repository, Prefect will automatically use the `git` recipe.


## Creating a basic deployment

Projects are most useful for creating deployments; let's walk through some examples.  


### Local deployment

In this example, we'll create a project from scratch that runs locally.  Let's start by creating a new directory, making that our working directory, and initializing a project:

<div class="terminal">
```bash
$ mkdir my-first-project
$ cd my-first-project
$ prefect project init --recipe local
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

- registered the existence of this flow [with your local project](/concepts/projects/#the-prefect-directory)
- created a description for this deployment based on the docstring of your flow function
- parsed the parameter schema for this flow function in order to expose an API for running this flow

You can customize all of this either by [manually editing `deployment.yaml`](/concepts/projects/#the-deployment-yaml-file) or by providing more flags to the `prefect deploy` CLI command; CLI inputs will always be prioritized over hard-coded values in your deployment's YAML file.

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
$ prefect project init --recipe git
```
</div>

We can now proceed with the same steps as above to create a new deployment:

<div class="terminal">
```bash
$ prefect deploy -f 'log-flow' \
    -n my-git-deployment \
    -p local-work
```
</div>

Notice that we were able to deploy based on flow name alone; this is because the repository owner [pre-registered the `log-flow` for us](https://github.com/PrefectHQ/hello-projects/blob/main/.prefect/flows.json).  Alternatively, if we knew the full entrypoint path, we could run `prefect deploy ./flows/log_flow.py:log_flow`.


Let's run this flow and discuss it's output:
<div class="terminal">
```bash
$ prefect deployment run 'log-flow/my-git-deployment'
```
</div>

In your worker process, you should see output that looks something like this:
<div class="terminal">
```bash
Cloning into 'hello-projects'...
...
12:01:43.188 | INFO    | Task run 'log_task-0' - Hello Marvin!
12:01:43.189 | INFO    | Task run 'log_task-0' - Prefect Version = 2.8.7+84.ge479b48b6.dirty 🚀
12:01:43.189 | INFO    | Task run 'log_task-0' - Hello from another file
...
12:01:43.236 | INFO    | Task run 'log_config-0' - Found config {'some-piece-of-config': 100}
...
12:01:43.266 | INFO    | Flow run 'delicate-labrador' - Finished in state Completed('All states completed.')
```
</div>

A few important notes on what we're looking at here:

- You'll notice the message "Hello from another file"; this flow imports code from [other related files](https://github.com/PrefectHQ/hello-projects/tree/main/flows) within the project. Prefect takes care of migrating the _entire_ project directory for you, which includes files that you may import from
- Similarly, the configuration that is logged is located within [the root directory](https://github.com/PrefectHQ/hello-projects/blob/main/config.json) of this project; you can always consider this root directory your working directory both locally and when this deployment is executed remotely
- Lastly, note the top line "Cloning into 'hello-projects'..."; because this project is based out of a GitHub repository, it is _automatically_ portable to any remote location where both `git` and `prefect` are configured! You can convince yourself of this by either running a new local worker on a different machine, or by switching this deployment to run with your docker work pool (more on this shortly).

!!! note "`prefect.yaml`"
    The above process worked out-of-the-box because of the information stored within `prefect.yaml`; if you open this file up in a text editor, you'll find that is not empty.  Specifically, it contains the following `pull` step that was automatically populated when you first ran `prefect project init`:
    ```yaml
    pull:
    - prefect.projects.steps.git_clone_project:
        repository: https://github.com/PrefectHQ/hello-projects.git
        branch: main
        access_token: null
    ```
    These `pull` steps are the instructions sent to your worker's runtime environment that allow it to clone your project in remote locations. For more information, see [the project concept documentation](/concepts/projects/).


### Dockerized deployment

In this example, we extend the examples above by dockerizing our setup and executing runs with a Docker Worker.  Building off the [git-based example above](#git-based-deployment), let's switch our deployment to submit work to the `docker-work` work pool that [we started at the beginning](#worker-tip):

<div class="terminal">
```bash
$ prefect deploy -f 'log-flow' \
    -n my-docker-git-deployment \
    -p docker-work
$ prefect deployment run 'log-flow/my-docker-git-deployment'
```
</div>

As promised above, this worked out of the box!  

Let's deploy a new flow from this project that requires additional dependencies that might not be available in the default image our work pool is using; this flow requires both `pandas` and `numpy` as a dependency, which we will install locally first to confirm the flow is working:

<div class="terminal">
```bash
$ pip install -r requirements.txt
$ python flows/pandas_flow.py
```
</div>

We now have two options for how to manage these dependencies in our worker's environment:

- setting the `EXTRA_PIP_PACKAGES` environment variable or using another hook to install the dependencies at runtime
- building a custom Docker image with the dependencies baked in

In this tutorial, we will focus on building a custom Docker image. First, we need to configure a `build` step within our `prefect.yaml` file as follows (Note: if starting from scratch we could use the `docker-git` recipe):

```yaml
# partial contents of prefect.yaml

build:
- prefect_docker.projects.steps.build_docker_image:
    image_name: local-only/testing
    tag: dev
    dockerfile: auto
    push: false

pull:
- prefect.projects.steps.git_clone_project:
    repository: https://github.com/PrefectHQ/hello-projects.git
    branch: main
    access_token: null
```

A few notes:

- [each step](/concepts/projects/#the-prefect-yaml-file) references a function with inputs and outputs
- in this case, we are using `dockerfile: auto` to tell Prefect to automatically create a `Dockerfile` for us; otherwise we could write our own and pass its location as a path to the `dockerfile` kwarg
- to avoid dealing with real image registries, we are not pushing this image; in most use cases you will want `push: true` (which is the default)

All that's left to do is create our deployment and specify our image name to instruct the worker what image to pull:

<div class="terminal">
```bash
$ prefect deploy -f 'pandas-flow' \
    -n docker-build-deployment \
    -p docker-work \
    -v image=local-only/testing:dev
$ prefect deployment run 'log-flow/my-docker-git-deployment'
```
</div>

Your run should complete succsessfully, logs and all!  Note that the `-v` flag represents a job variable, which are the allowed pieces of infrastructure configuration on a given work pool.  Each work pool can customize the fields they accept here.

!!! tip "Templating values"
    As a matter of best practice, you should avoid hardcoding the image name and tag in both your `prefect.yaml` and CLI. Instead, you should [use variable templating](/concepts/projects/#templating-options).

#### Dockerizing a local deployment

Revisiting [our local deployment above](#local-deployment), let's begin by switching it to submit work to our `docker-work` work pool by re-running `prefect deploy` to see what happens:

<div class="terminal">
```bash
$ prefect deploy ./api_flow.py:call_api \
    -n my-second-deployment \
    -p docker-work
$ prefect deployment run 'Call API/my-second-deployment'
```
</div>

This fails with the following error:
<div class="terminal">
```bash
ERROR: FileNotFoundError: [Errno 2] No such file or directory: '/Users/chris/dev/my-first-project'
```
</div>

The reason this occurs is because our deployment has a fundamentally local `pull` step; inspecting `prefect.yaml` we find:

```yaml
pull:
- prefect.projects.steps.set_working_directory:
    directory: /Users/chris/dev/my-first-project
```

In order to successfully submit such a project to a dockerized environment, we need to either:

- [`push` this project](/concepts/projects/#the-push-section) to a remote location (such as a Cloud storage bucket)
- [`build` this project](/concepts/projects/#the-build-section) into a Docker image artifact 

!!! tip "Advanced: `push` steps"
    Populating a `push` step is considered an advanced feature of projects that requires additional considerations to ensure the `pull` step is compatible with the `push` step; as such it is out of scope for this tutorial.

Following the same structure as above, we will include a new `build` step as well as alter our `pull` step to be compatible with the built image's filesystem:

```yaml
# partial contents of prefect.yaml

build:
- prefect_docker.projects.steps.build_docker_image:
    image_name: local-only/testing
    tag: dev2
    dockerfile: auto
    push: false

pull:
- prefect.projects.steps.set_working_directory:
    directory: /opt/prefect/hello-projects
```

Rerunning the same `deploy` command above now makes this a healthy deployment!


## Customizing the steps

For more information on what can be customized with `prefect.yaml`, check out the [Projects concept doc](/concepts/projects/).

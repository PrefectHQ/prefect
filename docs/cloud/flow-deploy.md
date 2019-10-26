---
sidebarDepth: 1
---

# Prefect Cloud: Deploying a Flow

Now that you understand the basic building blocks of Prefect Cloud and have locally authenticated with the Cloud API, let's walk through a real flow deployment.  Before we begin, make sure:
- you have a working Python 3.5.2+ environment with the latest version of Prefect installed
- you have [Docker](https://www.docker.com) up and running, and have authenticated with a Docker registry that you have push access to

## Write a Flow

The first step in flow deployment is obviously to write a flow!  We've prepared the following parametrized flow for you to edit as you wish.  Note that it relies on the [`pyfiglet` Python package](https://github.com/pwaller/pyfiglet) which is not included in a standard install of Prefect.

```python
import pyfiglet

import prefect
from prefect import task, Flow, Parameter

@task(name="Say Hi")
def say_hello(name):
    ascii_name = pyfiglet.figlet_format("Hi {}!".format(name))
    task_logger = prefect.context['logger']
    for line in ascii_name.split("\n"):
        task_logger.info(line)

with Flow("Greetings Flow") as flow:
    name = Parameter("name")
    say_hello(name)
```

You can now run this flow locally by passing the `name` parameter directly to `flow.run` or via the `parameters` keyword argument:

```python
flow.run(name="Marvin")
# or 
flow.run(parameters={"name": "Marvin"})
```

## Dockerize your Flow

In order to deploy this flow to Prefect Cloud, we need to create a Docker image containing the flow.  There are two ways of doing this:

### Create a Docker storage object

The most explicit way of configuring a Docker container for Prefect is to instantiate a `Docker` storage object:

```python
from prefect.environments.storage import Docker

storage = Docker(
    base_image="python:3.6",
    python_dependencies=["pyfiglet"],
    registry_url="prefecthq",
    image_name="flows",
    image_tag="first-flow",
)
```
There are other configuration settings - see the [API reference documentation](https://docs.prefect.io/api/unreleased/environments/storage.html#docker) for additional information.  Let's review the keyword arguments we have set above:
- `base_image`: the base Docker image to build on top of; if you don't provide one, Prefect will auto-detect properties of your environment and choose a sane default.  Configuring a base image that contains your Flow's dependencies (both Python and non-Python) is a popular way of sharing configuration amongst your team.
- `python_dependencies`: when Prefect builds your Flow's image, all of these packages will be `pip` installed into the image.  Note that if you require non-[PyPI](https://pypi.org) dependencies, you should choose a base image containing them instead of providing them here.  We will make sure `prefect` is always installed, so this keyword is reserved for non-`prefect` dependencies such as `pyfiglet` in our example.
- `registry_url`, `image_name` and `image_tag`: these options configure where the image will be pushed to.  Note that different registries require different configurations here.  For example, the code snippet above is configured for Prefect's [DockerHub registry](https://hub.docker.com/u/prefecthq).  If we were instead pushing to Google Cloud Registry we might have provided `registry_url="gcr.io/my-teams-registry/flows"` and let Prefect autogenerate an image name and tag. 

::: tip You can keep your images local
If no `registry_url` is provided, your Flow's image will _not_ be pushed anywhere and can only be run through local agents on the same machine.
:::

Attaching storage objects to your flows can be done at Flow initialization or by directly setting the attribute:

```python
with Flow("Greetings Flow", storage=storage) as flow:
    name = Parameter("name")
    say_hello(name)

# or 

flow.storage = storage
```

### Provide configuration settings at deploy time

Alternatively, Prefect simplifies this interface by allowing you provide _all Docker storage initialization keyword arguments_ at deploy time via `flow.deploy`:

```python
## this accomplishes the exact same thing as our example above:
flow.deploy(
    "My Project",
    base_image="python:3.6",
    python_dependencies=["pyfiglet"],
    registry_url="prefecthq",
    image_name="flows",
    image_tag="first-flow",
)
```

## Deploy your Flow 

Now that we have our flow built, all that's left is to deploy it using `flow.deploy`!  Whenever you deploy a flow, you always need to provide a project name for a pre-existing [Cloud project](concepts/projects.html#creating-a-new-project).  In this case, assuming we have created a `Docker` storage object explicitly, we can simply call:

```python
flow.deploy("My Project")
```
and watch Prefect build and push our Docker image, followed by sending the appropriate metadata to Prefect Cloud.  This method will return the Cloud ID for this flow, which is useful information when interacting with Cloud's GraphQL API.

::: tip Only metadata is sent to Cloud
Note that your Flow code is stored in your Docker image alone.  This gives you full control over permissioning and access for your Flows.  Whenever this Flow is picked up by a Prefect Agent, that agent will also need pull access from the registry in which your flow's image lives.
:::

## Run your Flow using an Agent

"Deploying" a Prefect Flow to Cloud is essentially registering it with Cloud.  If we had included a [Prefect Schedule](../core/concepts/schedules.html) on our Flow, the Prefect Scheduler would immediately begin creating scheduled runs for execution (this can be avoided by setting `set_schedule_active=False` in `flow.deploy`).  Because we did not provide a schedule, our flow will only run when we create a flow run for it.

There are numerous ways to create flow run:
- via GraphQL
- via the Prefect CLI
- via the UI
- via the Prefect Client

All of these are described in the corresponding [Cloud concept documentation](concepts/flow_runs.html).  Note that the `name` parameter is _always required_ on our Flow, so any attempt at creating a flow run must provide a value for this parameter.

Once a flow run has been created in a `Scheduled` state, all active Agents will now see it and only one will be able to submit it for execution.  For reference material on running Prefect Agents, see the [Up and Running documentation](upandrunning.html#start-local-agent) and the [Agent overview documentation](agent/overview.html).

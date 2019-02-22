# Environments

## Overview

Environments are serializable objects that describe how to run a flow. By using an appropriate `Environment`, users can store, execute, and share flows in a variety of storage and compute locations.


## Environment Lifecycle

At first glance the lifecycle of an environment may seem complicated however it only consists of four functions that are called at different stages. In this example we will be using a `DockerOnKubernetesEnvironment` which will look something like:

```python
from prefect import task, Flow
from prefect.environments.kubernetes import DockerOnKubernetesEnvironment

env = DockerOnKubernetesEnvironment(registry_url="https://my-registry.io/")

@task
def my_task():
    return "my task"

with Flow('Environment Example', environment=env) as flow:
    t = my_task()

flow.deploy(project_name="example_project")
```

In this snippet we create a basic flow with only a single task who's sole responsibility is to return the string _"my task"_. We attach a `DockerOnKubernetesEnvironment` to the flow which gives us all of the logic needed to take this flow, build it, package it up, store it, and provide it with instructions on how to deploy itself to our Kubernetes cluster.

Here is the process that completes the lifecycle of this environment. First, `flow.deploy()` builds the environment which is attached to the flow. In this case, the `DockerOnKubernetesEnvironment` is a subclass of the base `DockerEnvironment` who's `build()` function is responsible for taking this flow, serializing it into a `LocalEnvironment`, building a Docker image, placing that serialized local environment inside of that image, and (if a registry url is provided) pushing that image to a registry. Then the metadata surrounding this `DockerOnKubernetesEnvironment` is sent to Prefect Cloud.

::: tip Metadata Storage
Prefect Cloud does not store any of the code from the flow nor does it have the ability to access it. By only storing metadata surrounding the environment we are able to provide users with a mechanism of hybrid deployment.
:::

Once a flow is set to run (either manually or by the Prefect scheduler) your Kubernetes agent creates a job which is given the basic Prefect Docker image and it is provided the metadata that was stored from the flow's environment. It uses that metadata to deserialize an environment and in this case it is the `DockerOnKubernetesEnvironment`. Now it runs the environment's `setup()` and `execute()` functions. The setup portion is responsible for creating any infrastructure requirements that this environment may have. In the `DockerOnKubernetesEnvironment` there are no pre-existing infrastructure requirements so the setup just passes. Other environments such as `DaskOnKubernetes` will require the setup function to create both a dask scheduler and dask workers. Once setup is done the execute function's job is to actually tell the flow how and where to run. The `DockerOnKubernetesEnvironment`'s execute function creates a Kubernetes job that calls the run function of the `LocalEnvironment` that was serialized inside of the Docker image we built earlier. That run function is where the flow actually starts running and it is also the place where Prefect executors will come into play.

::: tip Executors and Environments
Executors and environments work hand-in-hand. If your flow has a `DaskExecutor` then upon deployment it should have a `DaskOnKubernetesEnvironment` attached so the executor can make use of the resources created during setup.
:::

Once the flow has entered a finished state then any resources created during `setup` and `execute` are cleaned up for that particular run.

## Environment Hierarchy

![environment hierarchy](/environment_structure.png)

There are four main functions to an environment that are implemented at different levels of inheritance: build, run, setup, and execute.

#### Build and Run
Build is implemented at the base environment level of the hierarchy. It is responsible for quite literally building the environment. As an example, the `DockerEnvironment`'s build builds a Docker image and (optionally) pushes it to a registry.

Run is also implemented at the base environment level. The goal of `run` is to run the flow using whichever executor the flow has attached to it.

#### Setup and Execute
Setup is implemented in the platform environments and is responsible for creating any infrastructure requirements that the flow needs in order to be ran. Execute is also defined in the platform environments who's job it is to create the method of execution for which the `run` function is called.

::: warning Platform Requirements
Each platform that Prefect supports has its own set of requirements. As an example, the Kubernetes environments will require the `execute` function to call `run` inside of a Kubernetes job w/ relative identifier labels such as UUIDs. This way the jobs and all of their supporting infrastructure can be cleaned up after completion.
:::

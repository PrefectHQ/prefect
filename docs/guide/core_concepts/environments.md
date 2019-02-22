# Environments

## Overview

Environments are serializable objects that describe how to run a flow. By using an appropriate `Environment`, users can store, execute, and share flows in a variety of storage and compute locations.


## Environment Design

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

In this snippet we create a basic flow with only a single task who's sole responsibility is to return the string _"my task"_. We attach a `DockerOnKubernetesEnvironment` to the flow which gives us all of the logic needed to take this flow, build it, package it up, store it, and deploy it.

## Environment Hierarchy

![environment hierarchy](/environment_structure.png)

There are four main functions to an environment that are implemented at different levels of inheritance: build, run, setup, and execute.

#### Build and Run
Build is implemented at the base environment level of the hierarchy. It is responsible for quite literally building the environment. As an example, the `DockerEnvironment`'s build builds a Docker image and (optionally) pushes it to a registry.

Run is also implemented at the base environment level. The goal of `run` is to run the flow using whichever executor the flow has attached to it.

#### Setup and Execute
Setup is implemented in the platform environments and is responsible for creating any infrastructure requirements that the flow needs in order to be ran. Execute is also defined in the platform environments who's job it is to create the method of execution for which the `run` function is called.

---
sidebarDepth: 1
---

# Environments
---
 ## Environment

### <span style="background-color:rgba(27,31,35,0.05);font-size:0.85em;">class</span> ```prefect.environments.Environment(secrets=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/environments.py#L32)</span>
Base class for Environments

 ####  ```prefect.environments.Environment.build()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/environments.py#L42)</span>
Build the environment


 ## Container

### <span style="background-color:rgba(27,31,35,0.05);font-size:0.85em;">class</span> ```prefect.environments.Container(image, tag=None, python_dependencies=None, secrets=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/environments.py#L47)</span>
Container class used to represent a Docker container

 ####  ```prefect.environments.Container.build()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/environments.py#L75)</span>
Build the Docker container

**Args**:


None

**Returns**:

tuple with (docker.models.images.Image, iterable logs)

 ####  ```prefect.environments.Container.create_dockerfile(directory=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/environments.py#L133)</span>
Creates a dockerfile to use as the container.

In order for the docker python library to build a container it needs a
Dockerfile that it can use to define the container. This function takes the
image and python_dependencies then writes them to a file called Dockerfile.

**Args**:


directory: A directory where the Dockerfile will be created

**Returns**:

None

 ####  ```prefect.environments.Container.pull_image()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/environments.py#L118)</span>
Pull the image specified so it can be built.

In order for the docker python library to use a base image it must be pulled
from either the main docker registry or a separate registry that must be set in
the environment variables.

**Args**:


None

**Returns**:

None

 ####  ```prefect.environments.Container.run(command=None, tty=False)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/environments.py#L95)</span>
Run the flow in the Docker container

**Args**:


command: An initial command that will be executed on container run
tty: Sets whether the container stays active once it is started

**Returns**:

A docker.models.containers.Container object



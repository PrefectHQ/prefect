---
sidebarDepth: 1
---

# Environments
---
 ## Environment

### <span style="background-color:rgba(27,31,35,0.05);font-size:0.85em;">class</span> ```prefect.environments.Environment(secrets=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/environments.py#L34)</span>
Base class for Environments

 ####  ```prefect.environments.Environment.build()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/environments.py#L44)</span>
Build the environment


 ## ContainerEnvironment

### <span style="background-color:rgba(27,31,35,0.05);font-size:0.85em;">class</span> ```prefect.environments.ContainerEnvironment(image, tag=None, python_dependencies=None, secrets=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/environments.py#L49)</span>
Container class used to represent a Docker container

 ####  ```prefect.environments.ContainerEnvironment.build()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/environments.py#L77)</span>
Build the Docker container

**Args**:
None

**Returns**:
tuple with (docker.models.images.Image, iterable logs)

 ####  ```prefect.environments.ContainerEnvironment.create_dockerfile(directory=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/environments.py#L135)</span>
Creates a dockerfile to use as the container.

In order for the docker python library to build a container it needs a
Dockerfile that it can use to define the container. This function takes the
image and python_dependencies then writes them to a file called Dockerfile.

**Args**:
directory: A directory where the Dockerfile will be created

**Returns**:
None

 ####  ```prefect.environments.ContainerEnvironment.pull_image()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/environments.py#L120)</span>
Pull the image specified so it can be built.

In order for the docker python library to use a base image it must be pulled
from either the main docker registry or a separate registry that must be set in
the environment variables.

**Args**:
None

**Returns**:
None

 ####  ```prefect.environments.ContainerEnvironment.run(command=None, tty=False)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/environments.py#L97)</span>
Run the flow in the Docker container

**Args**:
command: An initial command that will be executed on container run
tty: Sets whether the container stays active once it is started

**Returns**:
A docker.models.containers.Container object


 ## PickleEnvironment

### <span style="background-color:rgba(27,31,35,0.05);font-size:0.85em;">class</span> ```prefect.environments.PickleEnvironment(encryption_key=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/environments.py#L184)</span>
A pickle environment type for pickling a flow

 ####  ```prefect.environments.PickleEnvironment.build(flow)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/environments.py#L196)</span>
Pickles a flow and returns the bytes

**Args**:
- `flow`: A `prefect.Flow` object

**Returns**:
An encrypted pickled flow

 ####  ```prefect.environments.PickleEnvironment.info(pickle)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/environments.py#L214)</span>
Returns the serialized flow from a pickle

**Args**:
- `pickle`: A pickled `Flow` object

**Returns**:
A dictionary of the serialized flow

**Raises**:
`TypeError` if the unpickeld object is not a `Flow`

 ####  ```prefect.environments.PickleEnvironment.run()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/environments.py#L210)</span>
Run



# Managing Docker Images

Several Prefect Agents rely on [Docker images](https://docs.docker.com) for
distributing dependencies. These include the
[Docker](/orchestration/agents/docker.md),
[Kubernetes](/orchestration/agents/kubernetes.md), and [AWS
ECS](/orchestration/agents/ecs.md) agents. Here we discuss the options and
requirements for building and configuring docker images across these platforms.

## Dependency Requirements

When executing Prefect flows, Python code is loaded from two locations:

- The *flow's source* is loaded from the flow's configured
  [storage](./storage.md). Depending on your configuration, this may be a
  Python script or a pickled flow object. Either way, this contains the
  structure of the flow itself, along with any tasks defined in the same `.py`
  file.
- The *flow's dependencies* are loaded from the flow's execution environment.
  If running in a container, the dependencies need to be part of the docker
  image. Dependencies include `prefect`, as well as any other Python libraries
  you imported from within your flow script.

An example may help clarify the distinction here. Given the following flow

```python
from prefect import Flow, task
from prefect.storage import GitHub

import numpy
from my_task_library import task_1

@task
def task_2(x):
    return numpy.sum(x)

with Flow("example") as flow:
    x = task_1()
    y = task_2(x)

flow.storage = GitHub(repo="my_username/my_repo", path="path/to/flow.py")
```

This flow makes use of [GitHub storage](./storage.md#github), meaning that the
flow's source will be loaded at runtime from GitHub (and thus doesn't need to
be part of the Docker image). This means that the definition of `task_2` and
the flow itself don't need to be part of the built image.

The flow also uses two non-`prefect` imports:
- `numpy`: an external library this flow depends on
- `my_task_library.task_1`: a Prefect task defined in another python file/module

Both `numpy` and `my_task_library` need to be installed as part of the image.

## Prefect Provided Images

Every release of Prefect comes with a few built-in images. These images are all
named [prefecthq/prefect](https://hub.docker.com/r/prefecthq/prefect), but have
a few different tag options:

| Tag              |     Prefect Version      | Python Version |
| ---------------- | :----------------------: | -------------: |
| latest           | most recent PyPi version |            3.7 |
| master           |       master build       |            3.7 |
| latest-python3.8 | most recent PyPi version |            3.8 |
| latest-python3.7 | most recent PyPi version |            3.7 |
| latest-python3.6 | most recent PyPi version |            3.6 |
| X.Y.Z            |          X.Y.Z           |            3.7 |
| X.Y.Z-python3.8  |          X.Y.Z           |            3.8 |
| X.Y.Z-python3.7  |          X.Y.Z           |            3.7 |
| X.Y.Z-python3.6  |          X.Y.Z           |            3.6 |
| core             | most recent PyPi version |            3.8 |
| core-X.Y.Z       |          X.Y.Z           |            3.8 |

The images can be broken into a few categories:

- `core`: These images contain only `prefect` and its [core
  dependencies](https://github.com/PrefectHQ/prefect/blob/master/requirements.txt).

- `X.Y.Z`: These images contain `prefect`, as well as all "common" dependencies
  required for deploying Prefect on common platforms. This includes all
  dependencies required all builtin agents, as well as all `RunConfig`,
  `Storage`, and `Result` classes. Each `X.Y.Z.` image corresponds to a
  specific `prefect` release.

- `latest`: These are the same as the `X.Y.Z` images above, but always
  correspond to the latest `prefect` release.

If you don't specify an image to use with your flow via a [run
config](./run_configs.md), Prefect will use the `prefecthq/prefect:X.Y.Z`
image corresponding to the `prefect` version used to register your flow.

Using the default image is a good option if your flow only relies on tasks
defined in the same file as the flow, or tasks provided as part of the
`prefect` library itself. If your task requires additional external
dependencies, you'll need to build and manage your own images.

### Installing Extra Dependencies at Runtime

If you're using the `prefecthq/prefect` image (or an image based on
`prefecthq/prefect`), you can make use of the `EXTRA_PIP_PACKAGES` environment
variable to install dependencies at runtime. If defined, `pip install
${EXTRA_PIP_PACKAGES}` is executed before the flow run starts.

For example, here we configure a flow running on Kubernetes to install
`scikit-learn` and `matplotlib` at runtime.

```python
from prefect.run_configs import KubernetesRun

flow.run_config = KubernetesRun(env={"EXTRA_PIP_PACKAGES": "scikit-learn matplotlib"})
```

For production deploys we recommend building a custom image (as described
below). Installing dependencies during each flow run can be costly (since
you're downloading from PyPI on each execution) and adds another opportunity
for failure. Use of `EXTRA_PIP_PACKAGES` can be useful during development
though, as it allows you to iterate on dependencies without building a new
image each time.

## Building your Own Image

If your flow relies on dependencies not found in the default
`prefecthq/prefect` images, you'll want to build your own image. You can either
base it off of one of the provided `prefecthq/prefect` images, or build your
own from scratch.

**Extending the `prefecthq/prefect` image**

Here we provide an example `Dockerfile` for building an image based on
`prefecthq/prefect:0.14.10`, but with `scikit-learn` installed.

```dockerfile
FROM prefecthq/prefect:0.14.10

RUN pip install scikit-learn
```

**Building a new image from scratch**

Alternatively, you can build your own image without relying on the provided
`prefecthq/prefect` images. The only requirement is that `prefect` is installed
and on `$PATH`.

Here we provide an example `Dockerfile` for building an image with `prefect`
(with the `github` extra), as well as `scikit-learn` and `matplotlib`. We use the
[python:3.8-buster](https://hub.docker.com/_/python) image as the base image.

```dockerfile
FROM python:3.8-buster

RUN pip install prefect[github] scikit-learn matplotlib
```

In either case, after you've built the image and pushed it to a registry, you
can configure your flow to use it via the `image` field in your flow's [run
config](./run_configs.md). For example, here we configure a flow deployed on
Kubernetes to use the `my_org/my_custom_image:latest` image.

```python
from prefect.run_configs import KubernetesRun

flow.run_configs = KubernetesRun(image="my_org/my_custom_image:latest")
```

## Using Docker Storage

Note that neither of the above examples install the flow source as part of the
image - they assume your flow is distributed external to the image (using e.g.
[GitHub storage](./storage.md#github). If you want to distribute your flow
source as part of your docker image itself you'll want to make use of [Docker
storage](./storage.md#docker).

Since a new docker image will need to be built and pushed every time you change
your flow source, using Docker storage isn't always the most ergonomic of
options. When possible, we recommend relying on [a different storage
mechanism](./storage.md) for managing your flow source. This allows you to only
rebuild any associated image when a flow's dependencies have changed, not the
flow source itself. Still, `Docker` storage has a place in some deployments.

Here we configure a flow to use `Docker` storage. When registered, this will
build a custom docker image (based on the corresponding `prefecthq/prefect`
image) that contains your flow source, as well as all specified python
dependencies.

```python
from prefect.storage import Docker

flow.storage = Docker(python_dependencies=["scikit-learn", "matplotlib"])
```

For more information, see the [Docker Storage](./storage.md#docker) documentation.

## Choosing an Image Strategy

The options described above have different complexity (and performance)
characteristics. For choosing a strategy, we provide the following
recommendations:

- If your flow only makes use of tasks defined in the same file as the flow, or
  tasks that are part of `prefect` itself, then you can rely on the default
  provided `prefecthq/prefect` image.

- If your flow requires a few extra dependencies found on PyPI, we recommend
  using the default `prefecthq/prefect` image and setting `EXTRA_PIP_PACKAGES`
  to install these dependencies at runtime. This makes the most sense for small
  dependencies that are quick to install. If the installation process requires
  compiling code or other expensive operations, you may be better off building
  a custom image instead.

- If your flow (or flows) require extra dependencies or shared libraries, we
  recommend building a shared custom image with all the extra dependencies and
  shared task definitions you need. Your flows can then all rely on the same
  image, but have their source stored externally (in e.g. [GitHub
  storage](./storage.md#github)). This can ease development, as the shared
  image only needs to be rebuilt when dependencies change, not when the flow
  source changes.

- If you want to distribute your flow as a docker image alone (without relying
  on any extra infrastructure), we recommend using [Docker](./storage#docker)
  storage. This will build a new docker image every time you register your flow.

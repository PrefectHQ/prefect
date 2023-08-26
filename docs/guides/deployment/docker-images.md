---
description: Docker Images
tags:
    - Docker
    - Images
search:
  boost: 2
---

# Docker Images

Every release of Prefect results in several new Docker images.
These images are all named [prefecthq/prefect](https://hub.docker.com/r/prefecthq/prefect) and their
**tags** identify their differences.

In this guide, you'll learn how to choose which Docker image to specify in your work pool or deployment.

## Image tags

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

Conda flavored images are based on `continuumio/miniconda3`. Prefect is installed into a conda environment named `prefect`.

Note, Conda support for Python 3.11 is not available so we cannot build an image yet.

TK - this appears to no longer be true, but it doesn't look like we are building 3.11 images yet!! - create an issue
TK - add netlifly.toml redirect to the old subheading maybe
TK - add mkdocs.yaml nav and guides/index entries

| Tag                         |       Prefect Version       | Python Version  |
| --------------------------- | :-------------------------: | -------------:  |
| 2-latest-conda              | most recent v2 PyPi version |            3.10 |
| 2-python3.10-conda          | most recent v2 PyPi version |            3.10 |
| 2-python3.9-conda           | most recent v2 PyPi version |            3.9  |
| 2-python3.8-conda           | most recent v2 PyPi version |            3.8  |
| 2.X-python3.10-conda        |             2.X             |            3.10 |
| 2.X-python3.9-conda         |             2.X             |            3.9  |
| 2.X-python3.8-conda         |             2.X             |            3.8  |
| sha-&lt;hash&gt;-python3.10-conda |            &lt;hash&gt;           |            3.10 |
| sha-&lt;hash&gt;-python3.9-conda  |            &lt;hash&gt;           |            3.9  |
| sha-&lt;hash&gt;-python3.8-conda  |            &lt;hash&gt;           |            3.8  |

## Installing extra dependencies at runtime

If you're using the `prefecthq/prefect` image (or an image based on
`prefecthq/prefect`), you can make use of the `EXTRA_PIP_PACKAGES` environment
variable to install dependencies at runtime. If defined, `pip install
${EXTRA_PIP_PACKAGES}` is executed before the flow run starts.

TK update below section

For production deploys we recommend building a custom image (as described
below). Installing dependencies during each flow run can be costly (since
you're downloading from PyPI on each execution) and adds another opportunity
for failure. Use of `EXTRA_PIP_PACKAGES` can be useful during development
though, as it allows you to iterate on dependencies without building a new
image each time.

## Building your own image

If your flow relies on dependencies not found in the default
`prefecthq/prefect` images, you'll want to build your own image. You can either
base it off of one of the provided `prefecthq/prefect` images, or build your
own from scratch.

### Extending the `prefecthq/prefect` image

Here we provide an example `Dockerfile` for building an image based on
`prefecthq/prefect:2-latest`, but with `scikit-learn` installed.

```dockerfile
FROM prefecthq/prefect:2-latest

RUN pip install scikit-learn
```

### Choosing an Image Strategy

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
  image, but have their source stored externally. This can ease development, as the shared
  image only needs to be rebuilt when dependencies change, not when the flow
  source changes.

## Next steps

You've learned about Docker image options for Prefect deployments.

Docker containers are the basis for most Prefect work pool options, including [Kubernetes](/guides/deployment/kubernetes), [serverless cloud provider options such as ECS, Cloud Run, and ACI](/guides/aci/), and serverless [push-based work pools](/guides/push-work-pools/) that don't require a worker.

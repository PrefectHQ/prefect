# prefect-docker

The prefect-docker library provides functionality for running flows in Docker containers through Docker work pools.
This library is necessary for creating deployments that will run in Docker containers in most Prefect work pool infrastructure types.
See the the [Docker guide](/guides/deployment/docker/) for a walkthrough of creating and running a deployment with a Docker work pool.

That functionality is how most users will interact with this library.
However, the library also provides additional functionality that we explore below.

## Getting started

### Prerequisites

- [Prefect installed](/getting-started/installation/) in a virtual environment.
- [Docker installed](https://www.docker.com/) and running.

### Install prefect-docker

<div class="terminal">
```bash
pip install prefect-docker
```
</div>

### Register newly installed blocks types

Register the block types in the prefect-docker module to make them available for use.

<div class = "terminal">
```bash
prefect block register -m prefect_docker
```
</div>

## Examples

Create a block [through code](https://docs.prefect.io/concepts/blocks/#saving-blocks), the UI, or the API, before using it in the examples below.

!!! note
    The `DockerRegistryCredentials` block type in `prefect-docker` is a separate block type from the `DockerRegistry` that comes pre-installed with `prefect`.

## Pull an image and create, start, log, stop, and remove a Docker container

Run the following script to manually pull the latest Prefect image, and then start, stop, and remove a container.

```python
from prefect import flow, get_run_logger
from prefect_docker.images import pull_docker_image
from prefect_docker.containers import (
    create_docker_container,
    start_docker_container,
    get_docker_container_logs,
    stop_docker_container,
    remove_docker_container,
)


@flow
def docker_flow():
    logger = get_run_logger()
    pull_docker_image("prefecthq/prefect", "latest")
    container = create_docker_container(
        image="prefecthq/prefect", command="echo 'hello world!' && sleep 60"
    )
    start_docker_container(container_id=container.id)
    logs = get_docker_container_logs(container_id=container.id)
    logger.info(logs)
    stop_docker_container(container_id=container.id)
    remove_docker_container(container_id=container.id)
    return container

if __name__ == "__main__":
    docker_flow()
```

## Use a custom Docker Host to create a Docker container

Run the following script that uses a custom Docker host.

```python
from prefect import flow
from prefect_docker import DockerHost
from prefect_docker.containers import create_docker_container

@flow
def create_docker_container_flow():
    docker_host = DockerHost(
        base_url="tcp://127.0.0.1:1234",
        max_pool_size=4
    )
    container = create_docker_container(
        docker_host=docker_host,
        image="prefecthq/prefect",
        command="echo 'hello world!'"
    )

if __name__ == "__main__":
    create_docker_container_flow()
```

## Resources

For assistance using Docker, consult the [Docker documentation](https://docs.docker.com/).

Refer to the prefect-docker API documentation linked in the sidebar to explore all the capabilities of the prefect-docker library.

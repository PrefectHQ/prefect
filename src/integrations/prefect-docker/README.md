# prefect-docker

<p align="center">
    <a href="https://pypi.python.org/pypi/prefect-docker/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect-docker?color=26272B&labelColor=090422"></a>
    <a href="https://pepy.tech/badge/prefect-docker/" alt="Downloads">
        <img src="https://img.shields.io/pypi/dm/prefect-docker?color=26272B&labelColor=090422" /></a>
</p>

## Welcome!

Prefect integrations for working with Docker.

Note! The `DockerRegistryCredentials` in `prefect-docker` is a unique block, separate from the `DockerRegistry` in `prefect` core. While `DockerRegistry` implements a few functionality from both `DockerHost` and `DockerRegistryCredentials` for convenience, it does not allow much configuration to interact with a Docker host.

Do not use `DockerRegistry` with this collection. Instead, use `DockerHost` and `DockerRegistryCredentials`.

## Getting Started

### Python setup

Requires an installation of Python 3.8+.

We recommend using a Python virtual environment manager such as pipenv, conda, or virtualenv.

These tasks are designed to work with Prefect 2. For more information about how to use Prefect, please refer to the [Prefect documentation](https://docs.prefect.io/).

### Installation

Install `prefect-docker` with `pip`:

```bash
pip install prefect-docker
```

Then, register to [view the block](https://docs.prefect.io/concepts/blocks/) on Prefect Cloud:

```bash
prefect block register -m prefect_docker
```

Note, to use the `load` method on Blocks, you must already have a block document [saved through code](https://docs.prefect.io/concepts/blocks/#saving-blocks) or saved through the UI.

### Pull image, and create, start, log, stop, and remove Docker container

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
```

### Use a custom Docker Host to create a Docker container
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

create_docker_container_flow()
```

## Resources

If you encounter any bugs while using `prefect-docker`, feel free to open an issue in the [prefect](https://github.com/PrefectHQ/prefect) repository.

If you have any questions or issues while using `prefect-docker`, you can find help in the [Prefect Slack community](https://prefect.io/slack).

## Development

If you'd like to install a version of `prefect-docker` for development, clone the repository and perform an editable install with `pip`:

```bash
git clone https://github.com/PrefectHQ/prefect-docker.git

cd prefect-docker/

pip install -e ".[dev]"

# Install linting pre-commit hooks
pre-commit install
```

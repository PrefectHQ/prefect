from pathlib import Path
from typing import Generator

import pytest
from docker import DockerClient
from docker.errors import ImageNotFound
from typer.testing import CliRunner

import prefect
from prefect.cli.dev import dev_app
from prefect.docker import docker_client
from prefect.flow_runners.base import get_prefect_image_name


@pytest.fixture
def contexts() -> Path:
    return Path(__file__).parent / "contexts"


@pytest.fixture(scope="module")
def docker() -> Generator[DockerClient, None, None]:
    with docker_client() as client:
        yield client


@pytest.fixture(scope="module")
def prefect_base_image(docker: DockerClient):
    """Ensure that the prefect dev image is available and up-to-date"""
    image_name = get_prefect_image_name()

    image_exists, version_is_right = False, False

    try:
        image_exists = bool(docker.images.get(image_name))
    except ImageNotFound:
        pass

    if image_exists:
        version = docker.containers.run(image_name, ["prefect", "--version"])
        version_is_right = version.decode().strip() == prefect.__version__

    if not image_exists or not version_is_right:
        CliRunner().invoke(dev_app, ["build-image"])

    return image_name

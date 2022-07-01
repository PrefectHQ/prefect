from typing import Generator

import pytest
from typer.testing import CliRunner

import prefect
from prefect.cli.dev import dev_app
from prefect.docker import (
    IMAGE_LABELS,
    Container,
    DockerClient,
    ImageNotFound,
    NotFound,
    docker_client,
    silence_docker_warnings,
)
from prefect.flow_runners.base import get_prefect_image_name
from prefect.flow_runners.docker import CONTAINER_LABELS


@pytest.fixture(scope="session")
def docker() -> Generator[DockerClient, None, None]:
    with docker_client() as client:
        yield client


@pytest.fixture(scope="session", autouse=True)
def cleanup_all_new_docker_objects(docker: DockerClient, worker_id: str):
    IMAGE_LABELS["io.prefect.test-worker"] = worker_id
    CONTAINER_LABELS["io.prefect.test-worker"] = worker_id
    try:
        yield
    finally:
        for container in docker.containers.list(all=True):
            if container.labels.get("io.prefect.test-worker") == worker_id:
                container.remove(force=True)
            elif container.labels.get("io.prefect.delete-me"):
                container.remove(force=True)

        filters = {"label": f"io.prefect.test-worker={worker_id}"}
        for image in docker.images.list(filters=filters):
            for tag in image.tags:
                docker.images.remove(tag, force=True)


@pytest.mark.timeout(120)
@pytest.fixture(scope="session")
def prefect_base_image(pytestconfig: pytest.Config, docker: DockerClient):
    """Ensure that the prefect dev image is available and up-to-date"""
    image_name = get_prefect_image_name()

    image_exists, version_is_right = False, False

    try:
        image_exists = bool(docker.images.get(image_name))
    except ImageNotFound:
        pass

    if image_exists:
        output = docker.containers.run(
            image_name, ["prefect", "--version"], remove=True
        )
        image_version = output.decode().strip()
        version_is_right = image_version == prefect.__version__

    if not image_exists or not version_is_right:
        if pytestconfig.getoption("--disable-docker-image-builds"):
            if not image_exists:
                raise Exception(
                    "The --disable-docker-image-builds flag is set, but "
                    f"there is no local {image_name} image"
                )
            if not version_is_right:
                raise Exception(
                    "The --disable-docker-image-builds flag is set, but "
                    f"{image_name} includes {image_version}, not {prefect.__version__}"
                )
        else:
            CliRunner().invoke(dev_app, ["build-image"])

    return image_name


@pytest.fixture(scope="module")
def registry(docker: DockerClient) -> Generator[str, None, None]:
    """Starts a Docker registry locally, returning its URL"""

    with silence_docker_warnings():
        # Clean up any previously-created registry:
        try:
            preexisting: Container = docker.containers.get("orion-test-registry")
            preexisting.remove(force=True)  # pragma: no cover
        except NotFound:
            pass

        container: Container = docker.containers.run(
            "registry:2",
            detach=True,
            remove=True,
            name="orion-test-registry",
            ports={"5000/tcp": 5555},
        )
        try:
            yield "http://localhost:5555"
        finally:
            container.remove(force=True)

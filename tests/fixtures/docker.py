import sys
from contextlib import contextmanager
from typing import Generator

import pytest
from typer.testing import CliRunner

import prefect
from prefect.cli.dev import dev_app
from prefect.docker import (
    IMAGE_LABELS,
    docker_client,
    get_prefect_image_name,
    silence_docker_warnings,
)
from prefect.infrastructure.docker import CONTAINER_LABELS

with silence_docker_warnings():
    from docker import DockerClient
    from docker.errors import APIError, ImageNotFound, NotFound
    from docker.models.containers import Container


def _safe_remove_container(container: Container):
    try:
        container.remove(force=True)
    except APIError:
        pass


@pytest.fixture(scope="session")
def docker(worker_id: str) -> Generator[DockerClient, None, None]:
    context = docker_client()
    try:
        client = context.__enter__()
    except Exception as exc:
        raise RuntimeError(
            "Failed to create Docker client. Exclude tests that require Docker with "
            "'--exclude-service docker'."
        ) from exc

    try:
        with cleanup_all_new_docker_objects(client, worker_id):
            yield client
    finally:
        context.__exit__(*sys.exc_info())


@contextmanager
def cleanup_all_new_docker_objects(docker: DockerClient, worker_id: str):
    IMAGE_LABELS["io.prefect.test-worker"] = worker_id
    CONTAINER_LABELS["io.prefect.test-worker"] = worker_id
    try:
        yield
    finally:
        for container in docker.containers.list(all=True):
            if container.labels.get("io.prefect.test-worker") == worker_id:
                _safe_remove_container(container)
            elif container.labels.get("io.prefect.delete-me"):
                _safe_remove_container(container)

        filters = {"label": f"io.prefect.test-worker={worker_id}"}
        for image in docker.images.list(filters=filters):
            for tag in image.tags:
                docker.images.remove(tag, force=True)


@pytest.mark.timeout(120)
@pytest.fixture(scope="session")
def prefect_base_image(pytestconfig: "pytest.Config", docker: DockerClient):
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
            _safe_remove_container(preexisting)  # pragma: no cover
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

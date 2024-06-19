import sys
import time
from contextlib import contextmanager
from typing import Generator

import pytest
import requests
from typer.testing import CliRunner

import prefect
from prefect.cli.dev import dev_app
from prefect.logging import get_logger
from prefect.utilities.dockerutils import (
    CONTAINER_LABELS,
    IMAGE_LABELS,
    docker_client,
    get_prefect_image_name,
    silence_docker_warnings,
)

with silence_docker_warnings():
    from docker import DockerClient
    from docker.errors import APIError, ImageNotFound, NotFound
    from docker.models.containers import Container


logger = get_logger(__name__)


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
        try:
            for container in docker.containers.list(all=True):
                if container.labels.get("io.prefect.test-worker") == worker_id:
                    _safe_remove_container(container)
                elif container.labels.get("io.prefect.delete-me"):
                    _safe_remove_container(container)

            filters = {"label": f"io.prefect.test-worker={worker_id}"}
            for image in docker.images.list(filters=filters):
                for tag in image.tags:
                    docker.images.remove(tag, force=True)
        except NotFound:
            logger.warning("Failed to clean up Docker objects")


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


def _wait_for_registry(url: str, timeout: int = 30) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = requests.get(f"{url}/v2/")
            if response.status_code == 200:
                return True
        except requests.ConnectionError:
            pass
        time.sleep(1)
    return False


@pytest.fixture
def registry() -> Generator[str, None, None]:
    """Return the URL for the local Docker registry."""
    registry_url = "http://localhost:5555"
    if not _wait_for_registry(registry_url):
        raise RuntimeError(
            "Docker registry did not become ready in time. If you're running "
            "the tests locally, make sure you have the registry running with "
            "`docker compose up -d`."
        )

    yield registry_url

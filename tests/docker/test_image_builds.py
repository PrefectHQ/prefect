import io
import re
import sys
from pathlib import Path
from typing import Generator

import pytest
from _pytest.capture import CaptureFixture
from docker import DockerClient
from docker.errors import ImageNotFound
from typer.testing import CliRunner

import prefect
from prefect.cli.dev import dev_app
from prefect.docker import (
    BuildError,
    build_image,
    derive_from_prefect_image,
    docker_client,
)
from prefect.flow_runners.base import get_prefect_image_name


@pytest.fixture
def contexts() -> Path:
    return Path(__file__).parent / "contexts"


@pytest.fixture(scope="module")
def docker() -> Generator[DockerClient, None, None]:
    with docker_client() as client:
        yield client


IMAGE_ID_PATTERN = re.compile("^sha256:[a-fA-F0-9]{64}$")


@pytest.mark.service("docker")
def test_builds_tiny_hello_image(contexts: Path, docker: DockerClient):
    image_id = build_image(contexts / "tiny")
    assert IMAGE_ID_PATTERN.match(image_id)

    image = docker.images.get(image_id)
    assert image

    output = docker.containers.run(image, remove=True)
    assert output == b"Can't bear oceans.\n"


@pytest.mark.service("docker")
def test_builds_alternate_dockerfiles(contexts: Path, docker: DockerClient):
    image_a = build_image(contexts / "alternate", dockerfile="Dockerfile.a")
    assert IMAGE_ID_PATTERN.match(image_a)

    output = docker.containers.run(image_a, remove=True)
    assert output == b"from Dockerfile.a!\n"

    image_b = build_image(contexts / "alternate", dockerfile="Dockerfile.b")
    assert IMAGE_ID_PATTERN.match(image_b)

    assert image_a != image_b

    output = docker.containers.run(image_b, remove=True)
    assert output == b"from Dockerfile.b!\n"


def test_streams_progress_nowhere_by_default(contexts: Path, capsys: CaptureFixture):
    image_id = build_image(contexts / "tiny")
    assert IMAGE_ID_PATTERN.match(image_id)

    captured = capsys.readouterr()
    assert not captured.err
    assert not captured.out


@pytest.mark.service("docker")
def test_streams_progress_to_stdout(contexts: Path, capsys: CaptureFixture):
    image_id = build_image(contexts / "tiny", stream_progress_to=sys.stdout)
    assert IMAGE_ID_PATTERN.match(image_id)

    captured = capsys.readouterr()
    assert not captured.err

    output = captured.out

    # spot check a few things we should expect to find in the output
    assert "COPY hello.txt" in output

    _, _, image_hash = image_id.partition(":")
    assert f"Successfully built {image_hash[:12]}" in output


@pytest.mark.service("docker")
def test_streams_progress_to_given_stream(contexts: Path):
    my_stream = io.StringIO()

    image_id = build_image(contexts / "tiny", stream_progress_to=my_stream)
    assert IMAGE_ID_PATTERN.match(image_id)

    output = my_stream.getvalue()

    # spot check a few things we should expect to find in the output
    assert "COPY hello.txt" in output

    _, _, image_hash = image_id.partition(":")
    assert f"Successfully built {image_hash[:12]}" in output


def test_requires_path(contexts: Path):
    with pytest.raises(ValueError, match="context required"):
        build_image(None)


def test_requires_existing_path(contexts: Path):
    with pytest.raises(ValueError, match="does not exist"):
        build_image(contexts / "missing")


def test_requires_real_dockerfile(contexts: Path):
    with pytest.raises(ValueError, match="not found"):
        build_image(contexts / "tiny", dockerfile="Nowhere")


@pytest.mark.service("docker")
def test_raises_exception_on_build_error(contexts: Path):
    with pytest.raises(BuildError, match="returned a non-zero code"):
        build_image(contexts / "broken", stream_progress_to=sys.stdout)


@pytest.fixture
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


@pytest.mark.service("docker")
def test_from_prefect_image(docker: DockerClient, prefect_base_image: str):
    image_id = derive_from_prefect_image(
        dockerfile_lines=[
            "RUN echo Woooo, building",
            'ENTRYPOINT [ "prefect", "--version" ]',
        ]
    )
    assert IMAGE_ID_PATTERN.match(image_id)

    output = docker.containers.run(image_id, remove=True)
    assert output.decode().strip() == prefect.__version__

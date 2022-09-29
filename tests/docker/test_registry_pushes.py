import io
import sys
from pathlib import Path
from uuid import uuid4

import pendulum
import pytest
from _pytest.capture import CaptureFixture

from prefect.docker import ImageBuilder, PushError, push_image, silence_docker_warnings
from prefect.utilities.slugify import slugify

with silence_docker_warnings():
    from docker import DockerClient
    from docker.errors import NotFound

pytestmark = pytest.mark.service("docker")


@pytest.fixture
def contexts() -> Path:
    return Path(__file__).parent / "contexts"


@pytest.fixture(scope="module")
def howdy(docker: DockerClient, worker_id: str) -> str:
    # Give the image something completely unique so that we know it will generate a
    # new image each time
    message = f"hello from the registry, {str(uuid4())}!"
    with ImageBuilder("busybox") as image:
        image.add_line(f"LABEL io.prefect.test-worker {worker_id}")
        image.add_line(f'ENTRYPOINT [ "echo", "{message}" ]')
        image_id = image.build()

    greeting = docker.containers.run(image_id, remove=True).decode().strip()
    assert greeting == message

    # Give the image a unit tag for this run we we can confirm it is only untagged but
    # not removed by the process of pushing it to the registry
    test_run_tag = str(uuid4())
    docker.images.get(image_id).tag(test_run_tag)

    return image_id


def test_pushing_to_registry(docker: DockerClient, registry: str, howdy: str):
    tag_prefix = slugify(pendulum.now("utc").isoformat())[:20]

    registry_tag = push_image(howdy, registry, "howdy")
    assert registry_tag.startswith(f"localhost:5555/howdy:{tag_prefix}")

    greeting = docker.containers.run(registry_tag, remove=True).decode().strip()
    assert greeting.startswith("hello from the registry")


def test_pushing_to_registry_with_tag(docker: DockerClient, registry: str, howdy: str):
    registry_tag = push_image(howdy, registry, "howdy", tag="my-tag")
    assert registry_tag.startswith("localhost:5555/howdy:my-tag")

    greeting = docker.containers.run(registry_tag, remove=True).decode().strip()
    assert greeting.startswith("hello from the registry")


def test_pushing_with_owner(docker: DockerClient, registry: str, howdy: str):
    tag_prefix = slugify(pendulum.now("utc").isoformat())[:20]

    registry_tag = push_image(howdy, registry, "prefecthq/howdy")
    assert registry_tag.startswith(f"localhost:5555/prefecthq/howdy:{tag_prefix}")

    greeting = docker.containers.run(registry_tag, remove=True).decode().strip()
    assert greeting.startswith("hello from the registry")


def test_does_not_leave_registry_tag_locally(
    docker: DockerClient, registry: str, howdy: str
):
    tag_prefix = slugify(pendulum.now("utc").isoformat())[:20]

    registry_tag = push_image(howdy, registry, "howdy")
    assert registry_tag.startswith(f"localhost:5555/howdy:{tag_prefix}")

    with pytest.raises(NotFound):
        docker.images.get(registry_tag)


def test_registry_error(howdy: str):
    with pytest.raises(PushError, match="lookup.+nowhere"):
        push_image(howdy, "http://nowhere:5678", "howdy")


def test_streams_nowhere_by_default(howdy: str, registry: str, capsys: CaptureFixture):
    push_image(howdy, registry, "howdy")

    captured = capsys.readouterr()
    assert not captured.err
    assert not captured.out


def test_streams_progress_to_stdout(howdy: str, registry: str, capsys: CaptureFixture):
    push_image(howdy, registry, "howdy", stream_progress_to=sys.stdout)

    captured = capsys.readouterr()
    assert not captured.err

    output = captured.out

    # spot check a few things we should expect to find in the output
    assert "push refers to repository" in output
    assert "\nPreparing" in output
    assert "\nPushing [" in output or "\nLayer already exists" in output


def test_streams_progress_to_given_stream(howdy: str, registry: str):
    my_stream = io.StringIO()

    push_image(howdy, registry, "howdy", stream_progress_to=my_stream)

    output = my_stream.getvalue()

    # spot check a few things we should expect to find in the output
    assert "push refers to repository" in output
    assert "\nPreparing" in output
    assert "\nPushing [" in output or "\nLayer already exists" in output

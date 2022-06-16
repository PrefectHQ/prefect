import json
import warnings
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Generator, Iterable, Optional, TextIO

from docker import DockerClient

from prefect.flow_runners.base import get_prefect_image_name


@contextmanager
def docker_client() -> Generator[DockerClient, None, None]:
    """Get the environmentally-configured Docker client"""
    with warnings.catch_warnings():
        # Silence warnings due to use of deprecated methods within dockerpy
        # See https://github.com/docker/docker-py/pull/2931
        warnings.filterwarnings(
            "ignore",
            message="distutils Version classes are deprecated.*",
            category=DeprecationWarning,
        )

        client = DockerClient.from_env()

    try:
        yield client
    finally:
        client.close()


def _event_stream(
    api_response_stream: Generator[bytes, None, None]
) -> Generator[Dict, None, None]:
    """Given a Docker SDK low-level API response stream, decode and produce the
    individual JSON events from the stream as they happen"""
    for chunk in api_response_stream:
        events = chunk.split(b"\r\n")
        for event in events:
            if not event.strip():
                continue

            event = json.loads(event)
            yield event


class BuildError(Exception):
    """Raised when a Docker build fails"""


def build_image(
    context: Path,
    dockerfile: str = "Dockerfile",
    stream_progress_to: Optional[TextIO] = None,
) -> str:
    """Builds a Docker image, returning the image ID

    Args:
        context: the root directory for the Docker build context
        dockerfile: the path to the Dockerfile, relative to the context
        stream_progress_to: an optional stream (like sys.stdout, or an io.TextIO) that
            will collect the build output as it is reported by Docker

    Returns:
        The image ID
    """

    if not context:
        raise ValueError("context required to build an image")
    if not context.exists():
        raise ValueError(f"Context path {context} does not exist")
    if not (context / dockerfile).exists():
        raise ValueError(f"Dockerfile {dockerfile} not found in {context}")

    image_id = None
    with docker_client() as client:
        stream = client.api.build(
            path=str(context),
            dockerfile=dockerfile,
        )

        for event in _event_stream(stream):
            if "stream" in event:
                if not stream_progress_to:
                    continue
                stream_progress_to.write(event["stream"])
                stream_progress_to.flush()
            elif "aux" in event:
                image_id = event["aux"]["ID"]
            elif "error" in event:
                raise BuildError(event["error"])
            elif "message" in event:
                raise BuildError(event["message"])

    assert image_id, "The Docker daemon did not return an image ID"
    return image_id


def derive_from_prefect_image(
    prefect_image: str = None,
    dockerfile_lines: Iterable[str] = None,
    stream_progress_to: Optional[TextIO] = None,
) -> str:
    """Build a new Docker iamge from the given prefect base image

    Args:
        prefect_image: the prefect base image to use (or None to autodetect)
        dockerfile_lines: additional lines to add to the Dockerfile
        stream_progress_to: an optional stream (like sys.stdout, or an io.TextIO) that
            will collect the build output as it is reported by Docker

    Returns:
        The image ID
    """
    prefect_image = prefect_image or get_prefect_image_name()

    dockerfile_lines = [f"FROM {prefect_image}"] + (dockerfile_lines or [])

    with TemporaryDirectory() as temporary_directory:
        context = Path(temporary_directory)

        with (context / "Dockerfile").open("w") as dockerfile:
            dockerfile.writelines(line + "\n" for line in dockerfile_lines)

        return build_image(context, stream_progress_to=stream_progress_to)

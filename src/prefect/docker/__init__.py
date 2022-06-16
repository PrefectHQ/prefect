import json
import os
import shutil
import warnings
from contextlib import contextmanager
from multiprocessing.sharedctypes import Value
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from types import TracebackType
from typing import Dict, Generator, Iterable, List, Optional, TextIO, Type, Union

from docker import DockerClient
from docker.errors import APIError
from typing_extensions import Self


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

    image_id = None
    with docker_client() as client:
        stream = client.api.build(
            path=str(context),
            dockerfile=dockerfile,
        )

        try:
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
        except APIError as e:
            raise BuildError(e.explanation) from e

    assert image_id, "The Docker daemon did not return an image ID"
    return image_id


class ImageBuilder:
    """An interface for preparing Docker build contexts and building images"""

    base_directory: Path
    context: Optional[Path]
    dockerfile_lines: List[str]

    def __init__(
        self,
        base_image: str,
        base_directory: Path = None,
        context: Path = None,
    ):
        """Create an ImageBuilder

        Args:
            base_image: the base image to use
            base_directory: the starting point on your host for relative file locations,
                defaulting to the current directory
            context: use this path as the build context (if not provided, will create a
                temporary directory for the context)

        Returns:
            The image ID
        """
        self.base_directory = base_directory or context or Path().absolute()
        self.temporary_directory = None
        self.context = context
        self.dockerfile_lines = []

        if self.context:
            dockerfile_path: Path = self.context / "Dockerfile"
            if dockerfile_path.exists():
                raise ValueError(f"There is already a Dockerfile at {context}")

        self.add_line(f"FROM {base_image}")

    def __enter__(self) -> Self:
        if self.context and not self.temporary_directory:
            return self

        self.temporary_directory = TemporaryDirectory()
        self.context = Path(self.temporary_directory.__enter__())
        return self

    def __exit__(
        self, exc: Type[BaseException], value: BaseException, traceback: TracebackType
    ) -> None:
        if not self.temporary_directory:
            return

        self.temporary_directory.__exit__(exc, value, traceback)
        self.temporary_directory = None
        self.context = None

    def add_line(self, line: str) -> None:
        """Add a line to this image's Dockerfile"""
        self.add_lines([line])

    def add_lines(self, lines: Iterable[str]) -> None:
        """Add lines to this image's Dockerfile"""
        self.dockerfile_lines.extend(lines)

    def copy(self, source: Union[str, Path], destination: Union[str, PurePosixPath]):
        """Copy a file to this image"""
        if not self.context:
            raise Exception("No context available")

        if not isinstance(destination, PurePosixPath):
            destination = PurePosixPath(destination)

        if not isinstance(source, Path):
            source = Path(source)

        if source.is_absolute():
            source = source.relative_to(self.base_directory)

        if self.temporary_directory:
            os.makedirs(self.context / source.parent, exist_ok=True)

            if source.is_dir():
                shutil.copytree(self.base_directory / source, self.context / source)
            else:
                shutil.copy2(self.base_directory / source, self.context / source)

        self.add_line(f"COPY {source} {destination}")

    def build(self, stream_progress_to: Optional[TextIO] = None) -> str:
        """Build the Docker image from the current state of the ImageBuilder

        Args:
            stream_progress_to: an optional stream (like sys.stdout, or an io.TextIO)
                that will collect the build output as it is reported by Docker

        Returns:
            The image ID
        """
        dockerfile_path: Path = self.context / "Dockerfile"

        with dockerfile_path.open("w") as dockerfile:
            dockerfile.writelines(line + "\n" for line in self.dockerfile_lines)

        try:
            return build_image(self.context, stream_progress_to=stream_progress_to)
        finally:
            os.unlink(dockerfile_path)

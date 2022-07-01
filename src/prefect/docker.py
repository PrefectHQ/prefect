import hashlib
import os
import shutil
import warnings
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from types import TracebackType
from typing import Generator, Iterable, List, Optional, TextIO, Type, Union
from urllib.parse import urlsplit

import pendulum
from slugify import slugify
from typing_extensions import Self

import prefect


@contextmanager
def silence_docker_warnings() -> Generator[None, None, None]:
    with warnings.catch_warnings():
        # Silence warnings due to use of deprecated methods within dockerpy
        # See https://github.com/docker/docker-py/pull/2931
        warnings.filterwarnings(
            "ignore",
            message="distutils Version classes are deprecated.*",
            category=DeprecationWarning,
        )

        warnings.filterwarnings(
            "ignore",
            message="The distutils package is deprecated and slated for removal.*",
            category=DeprecationWarning,
        )

        yield


# docker-py has some deprecation warnings that fire off during import, and we don't
# want to have those popping up in various modules and test suites.  Instead,
# consolidate the imports we need here, and expose them via this module.
with silence_docker_warnings():
    from docker import DockerClient
    from docker.errors import APIError, ImageNotFound, NotFound  # noqa: F401
    from docker.models.containers import Container  # noqa: F401
    from docker.models.images import Image


@contextmanager
def docker_client() -> Generator[DockerClient, None, None]:
    """Get the environmentally-configured Docker client"""
    with silence_docker_warnings():
        client = DockerClient.from_env()

    try:
        yield client
    finally:
        client.close()


class BuildError(Exception):
    """Raised when a Docker build fails"""


# Labels to apply to all images built with Prefect
IMAGE_LABELS = {
    "io.prefect.version": prefect.__version__,
}


@silence_docker_warnings()
def build_image(
    context: Path,
    dockerfile: str = "Dockerfile",
    pull: bool = False,
    stream_progress_to: Optional[TextIO] = None,
) -> str:
    """Builds a Docker image, returning the image ID

    Args:
        context: the root directory for the Docker build context
        dockerfile: the path to the Dockerfile, relative to the context
        pull: True to pull the base image during the build
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
        events = client.api.build(
            path=str(context),
            dockerfile=dockerfile,
            pull=pull,
            decode=True,
            labels=IMAGE_LABELS,
        )

        try:
            for event in events:
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
            source = source.resolve().relative_to(self.base_directory)

        if self.temporary_directory:
            os.makedirs(self.context / source.parent, exist_ok=True)

            if source.is_dir():
                shutil.copytree(self.base_directory / source, self.context / source)
            else:
                shutil.copy2(self.base_directory / source, self.context / source)

        self.add_line(f"COPY {source} {destination}")

    def write_text(self, text: str, destination: Union[str, PurePosixPath]):
        if not self.context:
            raise Exception("No context available")

        if not isinstance(destination, PurePosixPath):
            destination = PurePosixPath(destination)

        source_hash = hashlib.sha256(text.encode()).hexdigest()
        (self.context / f".{source_hash}").write_text(text)
        self.add_line(f"COPY .{source_hash} {destination}")

    def build(
        self, pull: bool = False, stream_progress_to: Optional[TextIO] = None
    ) -> str:
        """Build the Docker image from the current state of the ImageBuilder

        Args:
            pull: True to pull the base image during the build
            stream_progress_to: an optional stream (like sys.stdout, or an io.TextIO)
                that will collect the build output as it is reported by Docker

        Returns:
            The image ID
        """
        dockerfile_path: Path = self.context / "Dockerfile"

        with dockerfile_path.open("w") as dockerfile:
            dockerfile.writelines(line + "\n" for line in self.dockerfile_lines)

        try:
            return build_image(
                self.context, pull=pull, stream_progress_to=stream_progress_to
            )
        finally:
            os.unlink(dockerfile_path)

    def assert_has_line(self, line: str) -> None:
        """Asserts that the given line is in the Dockerfile"""
        all_lines = "\n".join(
            [f"  {i+1:>3}: {line}" for i, line in enumerate(self.dockerfile_lines)]
        )
        message = (
            f"Expected {line!r} not found in Dockerfile.  Dockerfile:\n{all_lines}"
        )
        assert line in self.dockerfile_lines, message

    def assert_line_absent(self, line: str) -> None:
        """Asserts that the given line is absent from the Dockerfile"""
        if line not in self.dockerfile_lines:
            return

        i = self.dockerfile_lines.index(line)

        surrounding_lines = "\n".join(
            [
                f"  {i+1:>3}: {line}"
                for i, line in enumerate(self.dockerfile_lines[i - 2 : i + 2])
            ]
        )
        message = (
            f"Unexpected {line!r} found in Dockerfile at line {i+1}.  "
            f"Surrounding lines:\n{surrounding_lines}"
        )

        assert line not in self.dockerfile_lines, message

    def assert_line_before(self, first: str, second: str) -> None:
        """Asserts that the first line appears before the second line"""
        self.assert_has_line(first)
        self.assert_has_line(second)

        first_index = self.dockerfile_lines.index(first)
        second_index = self.dockerfile_lines.index(second)

        surrounding_lines = "\n".join(
            [
                f"  {i+1:>3}: {line}"
                for i, line in enumerate(
                    self.dockerfile_lines[second_index - 2 : first_index + 2]
                )
            ]
        )

        message = (
            f"Expected {first!r} to appear before {second!r} in the Dockerfile, but "
            f"{first!r} was at line {first_index+1} and {second!r} as at line "
            f"{second_index+1}.  Surrounding lines:\n{surrounding_lines}"
        )

        assert first_index < second_index, message

    def assert_line_after(self, second: str, first: str) -> None:
        """Asserts that the second line appears after the first line"""
        self.assert_line_before(first, second)

    def assert_has_file(self, source: Path, container_path: PurePosixPath) -> None:
        """Asserts that the given file or directory will be copied into the container
        at the given path"""
        if source.is_absolute():
            source = source.relative_to(self.base_directory)

        self.assert_has_line(f"COPY {source} {container_path}")


class PushError(Exception):
    """Raised when a Docker image push fails"""


@silence_docker_warnings()
def push_image(
    image_id: str,
    registry_url: str,
    name: str,
    tag: Optional[str] = None,
    stream_progress_to: Optional[TextIO] = None,
) -> str:
    """Pushes a local image to a Docker registry, returning the registry-qualified tag
    for that image

    This assumes that the environment's Docker daemon is already authenticated to the
    given registry, and currently makes no attempt to authenticate.

    Args:
        image_id (str): a Docker image ID
        registry_url (str): the URL of a Docker registry
        name (str): the name of this image
        tag (str): the tag to give this image (defaults to a short representation of
            the image's ID)
        stream_progress_to: an optional stream (like sys.stdout, or an io.TextIO) that
            will collect the build output as it is reported by Docker

    Returns:
        A registry-qualified tag, like my-registry.example.com/my-image:abcdefg
    """

    if not tag:
        tag = slugify(pendulum.now("utc").isoformat())

    _, registry, _, _, _ = urlsplit(registry_url)
    repository = f"{registry}/{name}"

    with docker_client() as client:
        image: Image = client.images.get(image_id)
        image.tag(repository, tag=tag)
        events = client.api.push(repository, tag=tag, stream=True, decode=True)
        try:
            for event in events:
                if "status" in event:
                    if not stream_progress_to:
                        continue
                    stream_progress_to.write(event["status"])
                    if "progress" in event:
                        stream_progress_to.write(" " + event["progress"])
                    stream_progress_to.write("\n")
                    stream_progress_to.flush()
                elif "error" in event:
                    raise PushError(event["error"])
        finally:
            client.api.remove_image(f"{repository}:{tag}", noprune=True)

    return f"{repository}:{tag}"


def to_run_command(command: List[str]) -> str:
    """
    Convert a process-style list of command arguments to a single Dockerfile RUN
    instruction.
    """
    if not command:
        return ""

    run_command = f"RUN {command[0]}"
    if len(command) > 1:
        run_command += " " + " ".join([repr(arg) for arg in command[1:]])

    # TODO: Consider performing text-wrapping to improve readability of the generated
    #       Dockerfile
    # return textwrap.wrap(
    #     run_command,
    #     subsequent_indent=" " * 4,
    #     break_on_hyphens=False,
    #     break_long_words=False
    # )

    return run_command

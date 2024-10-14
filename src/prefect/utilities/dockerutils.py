import hashlib
import os
import shutil
import sys
import warnings
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Any,
    Generator,
    Iterable,
    List,
    Optional,
    TextIO,
    Tuple,
    Type,
    Union,
)
from urllib.parse import urlsplit

import pendulum
from packaging.version import Version
from typing_extensions import Self

import prefect
from prefect.utilities.importtools import lazy_import
from prefect.utilities.slugify import slugify

CONTAINER_LABELS = {
    "io.prefect.version": prefect.__version__,
}


def python_version_minor() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def python_version_micro() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def get_prefect_image_name(
    prefect_version: Optional[str] = None,
    python_version: Optional[str] = None,
    flavor: Optional[str] = None,
) -> str:
    """
    Get the Prefect image name matching the current Prefect and Python versions.

    Args:
        prefect_version: An optional override for the Prefect version.
        python_version: An optional override for the Python version; must be at the
            minor level e.g. '3.9'.
        flavor: An optional alternative image flavor to build, like 'conda'
    """
    parsed_version = Version(prefect_version or prefect.__version__)
    is_prod_build = parsed_version.local is None
    prefect_version = (
        parsed_version.base_version
        if is_prod_build
        else "sha-" + prefect.__version_info__["full-revisionid"][:7]
    )

    python_version = python_version or python_version_minor()

    tag = slugify(
        f"{prefect_version}-python{python_version}" + (f"-{flavor}" if flavor else ""),
        lowercase=False,
        max_length=128,
        # Docker allows these characters for tag names
        regex_pattern=r"[^a-zA-Z0-9_.-]+",
    )

    image = "prefect" if is_prod_build else "prefect-dev"
    return f"prefecthq/{image}:{tag}"


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
    if TYPE_CHECKING:
        import docker
        from docker import DockerClient
    else:
        docker = lazy_import("docker")


@contextmanager
def docker_client() -> Generator["DockerClient", None, None]:
    """Get the environmentally-configured Docker client"""
    client = None
    try:
        with silence_docker_warnings():
            client = docker.DockerClient.from_env()

            yield client
    except docker.errors.DockerException as exc:
        raise RuntimeError(
            "This error is often thrown because Docker is not running. Please ensure Docker is running."
        ) from exc
    finally:
        client is not None and client.close()


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
    tag: Optional[str] = None,
    pull: bool = False,
    platform: Optional[str] = None,
    stream_progress_to: Optional[TextIO] = None,
    **kwargs: Any,
) -> str:
    """Builds a Docker image, returning the image ID

    Args:
        context: the root directory for the Docker build context
        dockerfile: the path to the Dockerfile, relative to the context
        tag: the tag to give this image
        pull: True to pull the base image during the build
        stream_progress_to: an optional stream (like sys.stdout, or an io.TextIO) that
            will collect the build output as it is reported by Docker

    Returns:
        The image ID
    """

    if not context:
        raise ValueError("context required to build an image")

    if not Path(context).exists():
        raise ValueError(f"Context path {context} does not exist")

    kwargs = {key: kwargs[key] for key in kwargs if key not in ["decode", "labels"]}

    image_id = None
    with docker_client() as client:
        events = client.api.build(
            path=str(context),
            tag=tag,
            dockerfile=dockerfile,
            pull=pull,
            decode=True,
            labels=IMAGE_LABELS,
            platform=platform,
            **kwargs,
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
        except docker.errors.APIError as e:
            raise BuildError(e.explanation) from e

    assert image_id, "The Docker daemon did not return an image ID"
    return image_id


class ImageBuilder:
    """An interface for preparing Docker build contexts and building images"""

    base_directory: Path
    context: Optional[Path]
    platform: Optional[str]
    dockerfile_lines: List[str]

    def __init__(
        self,
        base_image: str,
        base_directory: Path = None,
        platform: Optional[str] = None,
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
        self.platform = platform
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
                self.context,
                platform=self.platform,
                pull=pull,
                stream_progress_to=stream_progress_to,
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
        image: "docker.Image" = client.images.get(image_id)
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


def parse_image_tag(name: str) -> Tuple[str, Optional[str]]:
    """
    Parse Docker Image String

    - If a tag exists, this function parses and returns the image registry and tag,
      separately as a tuple.
      - Example 1: 'prefecthq/prefect:latest' -> ('prefecthq/prefect', 'latest')
      - Example 2: 'hostname.io:5050/folder/subfolder:latest' -> ('hostname.io:5050/folder/subfolder', 'latest')
    - Supports parsing Docker Image strings that follow Docker Image Specification v1.1.0
      - Image building tools typically enforce this standard

    Args:
        name (str): Name of Docker Image

    Return:
        tuple: image registry, image tag
    """
    tag = None
    name_parts = name.split("/")
    # First handles the simplest image names (DockerHub-based, index-free, potentionally with a tag)
    # - Example: simplename:latest
    if len(name_parts) == 1:
        if ":" in name_parts[0]:
            image_name, tag = name_parts[0].split(":")
        else:
            image_name = name_parts[0]
    else:
        # 1. Separates index (hostname.io or prefecthq) from path:tag (folder/subfolder:latest or prefect:latest)
        # 2. Separates path and tag (if tag exists)
        # 3. Reunites index and path (without tag) as image name
        index_name = name_parts[0]
        image_path = "/".join(name_parts[1:])
        if ":" in image_path:
            image_path, tag = image_path.split(":")
        image_name = f"{index_name}/{image_path}"
    return image_name, tag


def split_repository_path(repository_path: str) -> Tuple[Optional[str], str]:
    """
    Splits a Docker repository path into its namespace and repository components.

    Args:
        repository_path: The Docker repository path to split.

    Returns:
        Tuple[Optional[str], str]: A tuple containing the namespace and repository components.
            - namespace (Optional[str]): The Docker namespace, combining the registry and organization. None if not present.
            - repository (Optionals[str]): The repository name.
    """
    parts = repository_path.split("/", 2)

    # Check if the path includes a registry and organization or just organization/repository
    if len(parts) == 3 or (len(parts) == 2 and ("." in parts[0] or ":" in parts[0])):
        # Namespace includes registry and organization
        namespace = "/".join(parts[:-1])
        repository = parts[-1]
    elif len(parts) == 2:
        # Only organization/repository provided, so namespace is just the first part
        namespace = parts[0]
        repository = parts[1]
    else:
        # No namespace provided
        namespace = None
        repository = parts[0]

    return namespace, repository


def format_outlier_version_name(version: str):
    """
    Formats outlier docker version names to pass `packaging.version.parse` validation
    - Current cases are simple, but creates stub for more complicated formatting if eventually needed.
    - Example outlier versions that throw a parsing exception:
      - "20.10.0-ce" (variant of community edition label)
      - "20.10.0-ee" (variant of enterprise edition label)

    Args:
        version (str): raw docker version value

    Returns:
        str: value that can pass `packaging.version.parse` validation
    """
    return version.replace("-ce", "").replace("-ee", "")


@contextmanager
def generate_default_dockerfile(context: Optional[Path] = None):
    """
    Generates a default Dockerfile used for deploying flows. The Dockerfile is written
    to a temporary file and yielded. The temporary file is removed after the context
    manager exits.

    Args:
        - context: The context to use for the Dockerfile. Defaults to
            the current working directory.
    """
    if not context:
        context = Path.cwd()
    lines = []
    base_image = get_prefect_image_name()
    lines.append(f"FROM {base_image}")
    dir_name = context.name

    if (context / "requirements.txt").exists():
        lines.append(f"COPY requirements.txt /opt/prefect/{dir_name}/requirements.txt")
        lines.append(
            f"RUN python -m pip install -r /opt/prefect/{dir_name}/requirements.txt"
        )

    lines.append(f"COPY . /opt/prefect/{dir_name}/")
    lines.append(f"WORKDIR /opt/prefect/{dir_name}/")

    temp_dockerfile = context / "Dockerfile"
    if Path(temp_dockerfile).exists():
        raise RuntimeError(
            "Failed to generate Dockerfile. Dockerfile already exists in the"
            " current directory."
        )

    with Path(temp_dockerfile).open("w") as f:
        f.writelines(line + "\n" for line in lines)

    try:
        yield temp_dockerfile
    finally:
        temp_dockerfile.unlink()

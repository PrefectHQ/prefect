import sys
from pathlib import Path
from typing import Any, Optional, TextIO

from prefect.settings import (
    PREFECT_DEFAULT_DOCKER_BUILD_NAMESPACE,
)
from prefect.types._datetime import now
from prefect.utilities.dockerutils import (
    PushError,
    build_image,
    docker_client,
    generate_default_dockerfile,
    parse_image_tag,
    split_repository_path,
)
from prefect.utilities.slugify import slugify


class DockerImage:
    """
    Configuration used to build and push a Docker image for a deployment.

    Attributes:
        name: The name of the Docker image to build, including the registry and
            repository.
        tag: The tag to apply to the built image.
        dockerfile: The path to the Dockerfile to use for building the image. If
            not provided, a default Dockerfile will be generated.
        **build_kwargs: Additional keyword arguments to pass to the Docker build request.
            See the [`docker-py` documentation](https://docker-py.readthedocs.io/en/stable/images.html#docker.models.images.ImageCollection.build)
            for more information.

    """

    def __init__(
        self,
        name: str,
        tag: Optional[str] = None,
        dockerfile: str = "auto",
        stream_progress_to: Optional[TextIO] = sys.stdout,
        **build_kwargs: Any,
    ):
        image_name, image_tag = parse_image_tag(name)
        if tag and image_tag:
            raise ValueError(
                f"Only one tag can be provided - both {image_tag!r} and {tag!r} were"
                " provided as tags."
            )
        namespace, repository = split_repository_path(image_name)
        # if the provided image name does not include a namespace (registry URL or user/org name),
        # use the default namespace
        if not namespace:
            namespace = PREFECT_DEFAULT_DOCKER_BUILD_NAMESPACE.value()
        # join the namespace and repository to create the full image name
        # ignore namespace if it is None
        self.name: str = "/".join(filter(None, [namespace, repository]))
        self.tag: str = tag or image_tag or slugify(now("UTC").isoformat())
        self.dockerfile: str = dockerfile
        self.stream_progress_to: Optional[TextIO] = stream_progress_to
        self.build_kwargs: dict[str, Any] = build_kwargs

    @property
    def reference(self) -> str:
        return f"{self.name}:{self.tag}"

    def build(self) -> None:
        full_image_name = self.reference
        build_kwargs = self.build_kwargs.copy()
        if "context" not in build_kwargs:
            build_kwargs["context"] = Path.cwd()
        build_kwargs["tag"] = full_image_name
        build_kwargs["pull"] = build_kwargs.get("pull", True)
        build_kwargs["stream_progress_to"] = self.stream_progress_to

        if self.dockerfile == "auto":
            with generate_default_dockerfile():
                build_image(**build_kwargs)
        else:
            build_kwargs["dockerfile"] = self.dockerfile
            build_image(**build_kwargs)

    def push(self) -> None:
        with docker_client() as client:
            events = client.api.push(
                repository=self.name, tag=self.tag, stream=True, decode=True
            )
            for event in events:
                if "error" in event:
                    raise PushError(event["error"])
                if self.stream_progress_to and "status" in event:
                    self.stream_progress_to.write(event["status"])
                    if "progress" in event:
                        self.stream_progress_to.write(" " + event["progress"])
                    self.stream_progress_to.write("\n")
                    self.stream_progress_to.flush()

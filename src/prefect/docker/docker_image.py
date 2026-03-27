import sys
from pathlib import Path
from typing import Any, Literal, Optional, TextIO

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


def _ensure_buildx_extra() -> None:
    """Raise a clear error if the buildx extra is not installed."""
    try:
        import python_on_whales  # noqa: F401
    except ImportError:
        raise ImportError(
            "The 'python-on-whales' package is required for the buildx backend "
            "but is not installed. Install it with:\n\n"
            "  pip install prefect[buildx]"
        )


class DockerImage:
    """
    Configuration used to build and push a Docker image for a deployment.

    Attributes:
        name: The name of the Docker image to build, including the registry and
            repository.
        tag: The tag to apply to the built image.
        dockerfile: The path to the Dockerfile to use for building the image. If
            not provided, a default Dockerfile will be generated.
        stream_progress_to: A stream to write build and push progress output to.
            Defaults to sys.stdout. Set to None to suppress output.
        build_backend: The backend to use for building images. `"docker-py"`
            (default) uses the docker-py library.  `"buildx"` uses
            python-on-whales for BuildKit/buildx support, enabling features
            like build secrets, SSH forwarding, and multi-platform builds.
        **build_kwargs: Additional keyword arguments to pass to the Docker build
            request.  When `build_backend="docker-py"`, these are forwarded to
            docker-py's `client.api.build()`.
            When `build_backend="buildx"`, these are forwarded to
            `python_on_whales.docker.buildx.build()` and may include
            `secrets`, `ssh`, `cache_from`, `cache_to`, `platforms`,
            and `push`.

    """

    def __init__(
        self,
        name: str,
        tag: Optional[str] = None,
        dockerfile: str = "auto",
        stream_progress_to: Optional[TextIO] = sys.stdout,
        build_backend: Literal["docker-py", "buildx"] = "docker-py",
        **build_kwargs: Any,
    ):
        if build_backend not in ("docker-py", "buildx"):
            raise ValueError(
                f"Invalid build_backend {build_backend!r}. "
                "Must be 'docker-py' or 'buildx'."
            )
        if build_backend == "buildx":
            _ensure_buildx_extra()

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
        self.build_backend: str = build_backend
        self.build_kwargs: dict[str, Any] = build_kwargs
        self._pushed_during_build: bool = False

    @property
    def reference(self) -> str:
        return f"{self.name}:{self.tag}"

    def build(self) -> None:
        full_image_name = self.reference
        build_kwargs = self.build_kwargs.copy()

        if self.build_backend == "buildx":
            self._build_with_buildx(full_image_name, build_kwargs)
        else:
            self._build_with_docker_py(full_image_name, build_kwargs)

    def _build_with_docker_py(
        self, full_image_name: str, build_kwargs: dict[str, Any]
    ) -> None:
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

    def _build_with_buildx(
        self, full_image_name: str, build_kwargs: dict[str, Any]
    ) -> None:
        from prefect.docker._buildx import buildx_build_image

        context = build_kwargs.pop("context", Path.cwd())
        push = build_kwargs.pop("push", False)
        build_kwargs["tag"] = full_image_name
        build_kwargs["pull"] = build_kwargs.get("pull", True)
        build_kwargs["stream_progress_to"] = self.stream_progress_to

        if self.dockerfile == "auto":
            with generate_default_dockerfile():
                buildx_build_image(
                    context=context,
                    push=push,
                    **build_kwargs,
                )
        else:
            build_kwargs["dockerfile"] = self.dockerfile
            buildx_build_image(
                context=context,
                push=push,
                **build_kwargs,
            )

        if push:
            self._pushed_during_build = True

    def push(self) -> None:
        if self.build_backend == "buildx":
            self._push_with_buildx()
        else:
            self._push_with_docker_py()

    def _push_with_docker_py(self) -> None:
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

    def _push_with_buildx(self) -> None:
        if self._pushed_during_build:
            return

        from prefect.docker._buildx import buildx_push_image

        buildx_push_image(
            name=self.name,
            tag=self.tag,
            stream_progress_to=self.stream_progress_to,
        )

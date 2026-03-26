"""
BuildKit/buildx backend for Docker image building via python-on-whales.

This module provides an alternative build backend that wraps the Docker CLI's
buildx functionality through python-on-whales, enabling BuildKit features such
as build secrets, SSH forwarding, multi-platform builds, and `--mount` syntax.

Users opt in by setting `build_backend="buildx"` on `DockerImage` or
`build_docker_image()`.  The `python-on-whales` package must be installed
separately — install it via `pip install python-on-whales>=0.81`.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Optional, TextIO

try:
    import python_on_whales
    import python_on_whales.exceptions
except ImportError:
    python_on_whales = None  # type: ignore[assignment]

from prefect.utilities.dockerutils import (
    _BUILD_MAX_RETRIES,
    _BUILD_RETRY_DELAY_BASE,
    IMAGE_LABELS,
    BuildError,
    _is_transient_build_error,
)

logger: logging.Logger = logging.getLogger(__name__)


def buildx_build_image(
    context: Path,
    dockerfile: str = "Dockerfile",
    tag: Optional[str] = None,
    pull: bool = False,
    platform: Optional[str] = None,
    stream_progress_to: Optional[TextIO] = None,
    push: bool = False,
    **kwargs: Any,
) -> str:
    """Build a Docker image using BuildKit via python-on-whales.

    Args:
        context: The root directory for the Docker build context.
        dockerfile: The path to the Dockerfile, relative to the context.
        tag: The tag to give this image.
        pull: Whether to pull the base image during the build.
        platform: Target platform(s) for the build.  Can be a single string
            like `"linux/amd64"` or a list of strings for multi-platform
            builds.
        stream_progress_to: An optional stream that will collect build output.
        push: If `True`, push the image as part of the build step
            (`docker buildx build --push`).  Required for multi-platform
            builds.
        **kwargs: Additional keyword arguments forwarded to
            `python_on_whales.docker.buildx.build()`, such as `secrets`,
            `ssh`, `cache_from`, `cache_to`.

    Returns:
        The image ID string (e.g. `"sha256:abc..."`).

    Raises:
        BuildError: If the build fails.
        ValueError: If multi-platform is requested without `push=True`.
    """
    if not context:
        raise ValueError("context required to build an image")

    if not Path(context).exists():
        raise ValueError(f"Context path {context} does not exist")

    # Validate multi-platform + push constraint
    platforms = kwargs.pop("platforms", None)
    if platform and not platforms:
        platforms = [platform] if isinstance(platform, str) else platform
    if platforms and len(platforms) > 1 and not push:
        raise ValueError(
            "Multi-platform builds require push=True because buildx cannot "
            "load multi-platform results into the local Docker daemon. "
            "Either set push=True or build for a single platform."
        )

    # Merge labels
    labels = {**kwargs.pop("labels", {}), **IMAGE_LABELS}

    # Remove keys that don't apply to python-on-whales
    kwargs.pop("decode", None)

    last_error: Optional[BuildError] = None
    for attempt in range(_BUILD_MAX_RETRIES + 1):
        try:
            return _buildx_build_once(
                context=context,
                dockerfile=dockerfile,
                tag=tag,
                pull=pull,
                platforms=platforms,
                stream_progress_to=stream_progress_to,
                push=push,
                labels=labels,
                **kwargs,
            )
        except BuildError as e:
            last_error = e
            if attempt < _BUILD_MAX_RETRIES and _is_transient_build_error(str(e)):
                delay = _BUILD_RETRY_DELAY_BASE ** (attempt + 1)
                logger.warning(
                    "Buildx build encountered transient error (attempt"
                    " %d/%d): %s. Retrying in %ds...",
                    attempt + 1,
                    _BUILD_MAX_RETRIES + 1,
                    e,
                    delay,
                )
                time.sleep(delay)
            else:
                raise

    assert last_error is not None
    raise last_error


def _buildx_build_once(
    context: Path,
    dockerfile: str = "Dockerfile",
    tag: Optional[str] = None,
    pull: bool = False,
    platforms: Optional[list[str]] = None,
    stream_progress_to: Optional[TextIO] = None,
    push: bool = False,
    labels: Optional[dict[str, str]] = None,
    **kwargs: Any,
) -> str:
    """Execute a single buildx build attempt."""
    tags = [tag] if tag else []

    build_kwargs: dict[str, Any] = {
        "context_path": str(context),
        "file": str(Path(context) / dockerfile),
        "tags": tags,
        "pull": pull,
        "labels": labels or {},
        "push": push,
        **kwargs,
    }

    if platforms:
        build_kwargs["platforms"] = platforms

    try:
        output = python_on_whales.docker.buildx.build(**build_kwargs)
    except python_on_whales.exceptions.DockerException as e:
        raise BuildError(str(e)) from e

    # When push=True with multi-platform, python-on-whales returns None
    # (the image exists only in the registry, not locally).
    # For single-platform non-push builds, it returns an Image object.
    if output is None:
        # Multi-platform push — no local image ID available.
        # Return a synthetic identifier so callers know the build succeeded.
        return tag or ""

    # python-on-whales returns an Image object with an .id attribute
    image_id: str = output.id
    if stream_progress_to:
        stream_progress_to.write(f"Built image: {image_id}\n")
        stream_progress_to.flush()

    return image_id


def buildx_push_image(
    name: str,
    tag: Optional[str] = None,
    stream_progress_to: Optional[TextIO] = None,
) -> None:
    """Push a locally-built image using python-on-whales.

    This is used for single-platform images that were built without
    `push=True`.  For multi-platform builds, use `push=True` in
    `buildx_build_image()` instead.

    Args:
        name: The image name (repository), e.g. `"registry/repo"`.
        tag: The tag to push.
        stream_progress_to: An optional stream for progress output.

    """
    full_name = f"{name}:{tag}" if tag else name

    if stream_progress_to:
        stream_progress_to.write(f"Pushing {full_name}...\n")
        stream_progress_to.flush()

    try:
        python_on_whales.docker.image.push(full_name)
    except python_on_whales.exceptions.DockerException as e:
        raise OSError(str(e)) from e

    if stream_progress_to:
        stream_progress_to.write(f"Pushed {full_name}\n")
        stream_progress_to.flush()

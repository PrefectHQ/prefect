from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prefect.docker.docker_image import DockerImage

__all__ = ["DockerImage"]

_public_api: dict[str, tuple[str, str]] = {
    "DockerImage": ("prefect.docker.docker_image", "DockerImage"),
}


def __getattr__(name: str) -> object:
    from importlib import import_module

    if name in _public_api:
        module, attr = _public_api[name]
        return getattr(import_module(module), attr)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

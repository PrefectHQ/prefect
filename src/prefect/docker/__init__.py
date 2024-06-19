from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prefect.docker.deployment_image import DeploymentImage

__all__ = ["DeploymentImage"]

_public_api: dict[str, tuple[str, str]] = {
    "DeploymentImage": ("prefect.docker.deployment_image", "DeploymentImage"),
}


def __getattr__(name: str) -> object:
    from importlib import import_module

    if name in _public_api:
        module, attr = _public_api[name]
        return getattr(import_module(module), attr)

    raise ImportError(f"module {__name__!r} has no attribute {name!r}")

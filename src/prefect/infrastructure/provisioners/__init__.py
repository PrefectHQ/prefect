from typing import TYPE_CHECKING, Any, Dict, Optional, Protocol, Type

import rich.console

from prefect._internal.lazy import LazyDict

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient


def _load_provisioners() -> dict[str, type]:
    """Lazy load provisioners to avoid importing heavy cloud SDKs at module import time."""
    from prefect.infrastructure.provisioners.coiled import CoiledPushProvisioner
    from prefect.infrastructure.provisioners.modal import ModalPushProvisioner

    from .cloud_run import CloudRunPushProvisioner
    from .container_instance import ContainerInstancePushProvisioner
    from .ecs import ElasticContainerServicePushProvisioner

    return {
        "cloud-run:push": CloudRunPushProvisioner,
        "cloud-run-v2:push": CloudRunPushProvisioner,
        "azure-container-instance:push": ContainerInstancePushProvisioner,
        "ecs:push": ElasticContainerServicePushProvisioner,
        "modal:push": ModalPushProvisioner,
        "coiled:push": CoiledPushProvisioner,
    }


_provisioners_lazy: LazyDict[str, type] = LazyDict(_load_provisioners)


def __getattr__(name: str) -> LazyDict[str, type]:
    """Lazy load module attributes."""
    if name == "_provisioners":
        return _provisioners_lazy
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class Provisioner(Protocol):
    @property
    def console(self) -> rich.console.Console: ...

    @console.setter
    def console(self, value: rich.console.Console) -> None: ...

    async def provision(
        self,
        work_pool_name: str,
        base_job_template: Dict[str, Any],
        client: Optional["PrefectClient"] = None,
    ) -> Dict[str, Any]: ...


def get_infrastructure_provisioner_for_work_pool_type(
    work_pool_type: str,
) -> Type[Provisioner]:
    """
    Retrieve an instance of the infrastructure provisioner for the given work pool type.

    Args:
        work_pool_type: the work pool type

    Returns:
        an instance of the infrastructure provisioner for the given work pool type

    Raises:
        ValueError: if the work pool type is not supported
    """
    provisioner = _provisioners_lazy.get(work_pool_type)
    if provisioner is None:
        raise ValueError(f"Unsupported work pool type: {work_pool_type}")
    return provisioner()

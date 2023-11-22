from typing import Any, Dict, Optional, Protocol

from prefect.client.orchestration import PrefectClient
from .cloud_run import CloudRunPushProvisioner
import rich.console

_provisioners = {
    "cloud-run:push": CloudRunPushProvisioner,
}


class Provisioner(Protocol):
    @property
    def console(self) -> rich.console.Console:
        ...

    @console.setter
    def console(self, value: rich.console.Console) -> None:
        ...

    async def provision(
        self,
        work_pool_name: str,
        base_job_template: Dict[str, Any],
        client: Optional[PrefectClient] = None,
    ) -> Dict[str, Any]:
        ...


def get_infrastructure_provisioner_for_work_pool_type(
    work_pool_type: str,
) -> Provisioner:
    """
    Retrieve an instance of the infrastructure provisioner for the given work pool type.

    Args:
        work_pool_type: the work pool type

    Returns:
        an instance of the infrastructure provisioner for the given work pool type

    Raises:
        ValueError: if the work pool type is not supported
    """
    provisioner = _provisioners.get(work_pool_type)
    if provisioner is None:
        raise ValueError(f"Unsupported work pool type: {work_pool_type}")
    return provisioner()

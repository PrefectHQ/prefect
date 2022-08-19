import abc
from typing import Dict, List, Optional

import pydantic
from anyio.abc import TaskStatus

from prefect.blocks.core import Block
from prefect.logging import get_logger
from prefect.settings import get_current_settings


class InfrastructureResult(pydantic.BaseModel, abc.ABC):
    identifier: str
    status_code: int

    def __bool__(self):
        return self.status_code == 0


class Infrastructure(Block, abc.ABC):
    _block_schema_capabilities = ["run-infrastructure"]

    type: str

    env: Dict[str, str] = pydantic.Field(
        default_factory=dict,
        description="Environment variables to set in the configured infrastructure.",
    )
    labels: Dict[str, str] = pydantic.Field(
        default_factory=dict,
        description="Labels applied to the infrastructure for metadata purposes.",
    )
    name: Optional[str] = pydantic.Field(
        None, description="Display name for the configured infrastructure."
    )
    command: List[str] = pydantic.Field(
        ["python", "-m", "prefect.engine"],
        description="A list of strings specifying the command to run in the to start the flow run. In most cases you should not change this.",
    )

    @abc.abstractmethod
    async def run(
        self,
        task_status: TaskStatus = None,
    ) -> InfrastructureResult:
        """
        Run the infrastructure.

        If provided a `task_status`, the status will be reported as started when the
        infrastructure is successfully created. The status return value will be an
        identifier for the infrastructure.

        The call will then monitor the created infrastructure, returning a result at
        the end containing a status code indicating if the infrastructure exited cleanly\
        or encountered an error.
        """

    @abc.abstractmethod
    def preview(self) -> str:
        """
        View a preview of the infrastructure that would be run.
        """

    @property
    def logger(self):
        return get_logger(f"prefect.infrastructure.{self.type}")

    @classmethod
    def _base_environment(cls) -> Dict[str, str]:
        """
        Environment variables that should be passed to all created infrastructure.

        These values should be overridable with the `env` field.
        """
        return get_current_settings().to_environment_variables(exclude_unset=True)

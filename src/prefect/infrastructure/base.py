import abc
from typing import TYPE_CHECKING, Dict, List, Optional

import anyio.abc
import pydantic
from typing_extensions import Self

import prefect
from prefect.blocks.core import Block
from prefect.logging import get_logger
from prefect.settings import get_current_settings

MIN_COMPAT_PREFECT_VERSION = "2.0b12"


if TYPE_CHECKING:
    from prefect.orion.schemas.core import FlowRun


class InfrastructureResult(pydantic.BaseModel, abc.ABC):
    identifier: str
    status_code: int

    def __bool__(self):
        return self.status_code == 0


class Infrastructure(Block, abc.ABC):
    _block_schema_capabilities = ["run-infrastructure"]

    type: str

    env: Dict[str, Optional[str]] = pydantic.Field(
        default_factory=dict,
        title="Environment",
        description="Environment variables to set in the configured infrastructure.",
    )
    labels: Dict[str, str] = pydantic.Field(
        default_factory=dict,
        description="Labels applied to the infrastructure for metadata purposes.",
    )
    name: Optional[str] = pydantic.Field(
        None, description="Name applied to the infrastructure for identification."
    )
    command: Optional[List[str]] = pydantic.Field(
        None,
        description="The command to run in the infrastructure.",
    )

    @abc.abstractmethod
    async def run(
        self,
        task_status: anyio.abc.TaskStatus = None,
    ) -> InfrastructureResult:
        """
        Run the infrastructure.

        If provided a `task_status`, the status will be reported as started when the
        infrastructure is successfully created. The status return value will be an
        identifier for the infrastructure.

        The call will then monitor the created infrastructure, returning a result at
        the end containing a status code indicating if the infrastructure exited cleanly
        or encountered an error.
        """
        # Note: implementations should include `sync_compatible`

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

    def prepare_for_flow_run(
        self: Self,
        flow_run: "FlowRun",
    ) -> Self:
        """
        Return an infrastructure block that is prepared to execute a flow run.
        """
        return self.copy(
            update={
                "env": {**self._base_flow_run_environment(flow_run), **self.env},
                "labels": {**self._base_flow_run_labels(flow_run), **self.labels},
                "name": self.name or flow_run.name,
                "command": self.command or self._base_flow_run_command(),
            }
        )

    @staticmethod
    def _base_flow_run_command() -> List[str]:
        """
        Generate a command for a flow run job.
        """
        return ["python", "-m", "prefect.engine"]

    @staticmethod
    def _base_flow_run_labels(flow_run: "FlowRun") -> Dict[str, str]:
        """
        Generate a dictionary of labels for a flow run job.
        """
        return {
            "prefect.io/flow-run-id": str(flow_run.id),
            "prefect.io/flow-run-name": flow_run.name,
            "prefect.io/version": prefect.__version__,
        }

    @staticmethod
    def _base_flow_run_environment(flow_run: "FlowRun") -> Dict[str, str]:
        """
        Generate a dictionary of environment variables for a flow run job.
        """
        environment = {}
        environment["PREFECT__FLOW_RUN_ID"] = flow_run.id.hex
        return environment

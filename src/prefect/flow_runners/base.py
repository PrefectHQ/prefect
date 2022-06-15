import sys
from typing import Dict, Optional, Type, TypeVar

from anyio.abc import TaskStatus
from pydantic import BaseModel, Field
from slugify import slugify
from typing_extensions import Literal

import prefect
import prefect.settings
from prefect.logging import get_logger
from prefect.orion.schemas.core import FlowRun, FlowRunnerSettings
from prefect.settings import get_current_settings

_FLOW_RUNNERS: Dict[str, "FlowRunner"] = {}
FlowRunnerT = TypeVar("FlowRunnerT", bound=Type["FlowRunner"])


def python_version_minor() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def python_version_micro() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def get_prefect_image_name(
    prefect_version: str = None, python_version: str = None, flavor: str = None
) -> str:
    """
    Get the Prefect image name matching the current Prefect and Python versions.

    Args:
        prefect_version: An optional override for the Prefect version.
        python_version: An optional override for the Python version; must be at the
            minor level e.g. '3.9'.
        flavor: An optional alternative image flavor to build, like 'conda'
    """
    parsed_version = (prefect_version or prefect.__version__).split("+")
    prefect_version = parsed_version[0] if len(parsed_version) == 1 else "dev"

    python_version = python_version or python_version_minor()

    tag = slugify(
        f"{prefect_version}-python{python_version}" + (f"-{flavor}" if flavor else ""),
        lowercase=False,
        max_length=128,
        # Docker allows these characters for tag names
        regex_pattern=r"[^a-zA-Z0-9_.-]+",
    )

    return f"prefecthq/prefect:{tag}"


def base_flow_run_environment() -> Dict[str, str]:
    """
    Generate a dictionary of environment variables for a flow run job.
    """
    return get_current_settings().to_environment_variables(exclude_unset=True)


class FlowRunner(BaseModel):
    """
    Flow runners are responsible for creating infrastructure for flow runs and starting
    execution.

    This base implementation manages casting to and from the API representation of
    flow runner settings and defines the interface for `submit_flow_run`. It cannot
    be used to run flows.
    """

    typename: str

    def to_settings(self) -> FlowRunnerSettings:
        return FlowRunnerSettings(
            type=self.typename, config=self.dict(exclude={"typename"})
        )

    @classmethod
    def from_settings(cls, settings: FlowRunnerSettings) -> "FlowRunner":
        subcls = lookup_flow_runner(settings.type)
        return subcls(**(settings.config or {}))

    @property
    def logger(self):
        return get_logger(f"flow_runner.{self.typename}")

    async def submit_flow_run(
        self,
        flow_run: FlowRun,
        task_status: TaskStatus = None,
    ) -> Optional[bool]:
        """
        Implementations should:

        - Create flow run infrastructure.
        - Start the flow run within it.
        - Call `task_status.started()` to indicate that submission was successful

        The method can then exit or continue to monitor the flow run asynchronously.

        The method _may_ return a boolean indicating successful completion of the run.
        This return value is not intended for general consumption and is primarily
        useful for testing.
        """
        raise NotImplementedError()

    async def preview(self, flow_run: FlowRun) -> str:
        """
        Produce a textual preview of a FlowRun, if it were to run on this FlowRunner.

        Implementations can produce output in any textual format that makes sense for
        their target execution environment.  That may be a YAML or JSON manifest, a
        shell command-line, or other formats.

        Args:
            flow_run: The flow run

        """
        raise NotImplementedError()

    class Config:
        extra = "forbid"


def register_flow_runner(cls: FlowRunnerT) -> FlowRunnerT:
    _FLOW_RUNNERS[cls.__fields__["typename"].default] = cls
    return cls


def lookup_flow_runner(typename: str) -> FlowRunner:
    """Return the flow runner class for the given `typename`"""
    try:
        return _FLOW_RUNNERS[typename]
    except KeyError:
        raise ValueError(f"Unregistered flow runner {typename!r}")


@register_flow_runner
class UniversalFlowRunner(FlowRunner):
    """
    The universal flow runner contains configuration options that can be used by any
    Prefect flow runner implementation.

    This flow runner cannot be used at runtime and should be converted into a subtype.

    Attributes:
        env: Environment variables to provide to the flow run
    """

    typename: Literal["universal"] = "universal"
    env: Dict[str, str] = Field(default_factory=dict)

    async def submit_flow_run(
        self,
        flow_run: FlowRun,
        task_status: TaskStatus,
    ) -> Optional[bool]:
        raise RuntimeError(
            "The universal flow runner cannot be used to submit flow runs. If a flow "
            "run has a universal flow runner, it should be updated to the default "
            "runner type by the agent or user."
        )

    async def preview(self, flow_run: FlowRun) -> str:
        """
        Produce a textual preview of the given FlowRun.

        Args:
            flow_run: The flow run

        Returns:
            A YAML string
        """
        return repr(self)

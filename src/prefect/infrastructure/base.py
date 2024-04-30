"""
DEPRECATION WARNING:

This module is deprecated as of March 2024 and will not be available after September 2024.
Infrastructure blocks have been replaced by workers, which offer enhanced functionality and better performance.

For upgrade instructions, see https://docs.prefect.io/latest/guides/upgrade-guide-agents-to-workers/.
"""
import abc
import shlex
import warnings
from typing import TYPE_CHECKING, Dict, List, Optional

import anyio.abc

from prefect._internal.compatibility.deprecated import deprecated_class
from prefect._internal.compatibility.experimental import (
    EXPERIMENTAL_WARNING,
    ExperimentalFeature,
    experiment_enabled,
)
from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.exceptions import ObjectAlreadyExists

if HAS_PYDANTIC_V2:
    import pydantic.v1 as pydantic
else:
    import pydantic

from rich.console import Console
from typing_extensions import Self

import prefect
from prefect.blocks.core import Block, BlockNotSavedError
from prefect.logging import get_logger
from prefect.settings import (
    PREFECT_EXPERIMENTAL_WARN,
    PREFECT_EXPERIMENTAL_WARN_ENHANCED_CANCELLATION,
    PREFECT_UI_URL,
    get_current_settings,
)
from prefect.utilities.asyncutils import sync_compatible

MIN_COMPAT_PREFECT_VERSION = "2.0b12"


if TYPE_CHECKING:
    from prefect.client.schemas.objects import Deployment, Flow, FlowRun


class InfrastructureResult(pydantic.BaseModel, abc.ABC):
    identifier: str
    status_code: int

    def __bool__(self):
        return self.status_code == 0


@deprecated_class(
    start_date="Mar 2024",
    help="Use the `BaseWorker` class to create custom infrastructure integrations instead."
    " Refer to the upgrade guide for more information:"
    " https://docs.prefect.io/latest/guides/upgrade-guide-agents-to-workers/.",
)
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
        default=None,
        description="Name applied to the infrastructure for identification.",
    )
    command: Optional[List[str]] = pydantic.Field(
        default=None,
        description="The command to run in the infrastructure.",
    )

    async def generate_work_pool_base_job_template(self):
        if self._block_document_id is None:
            raise BlockNotSavedError(
                "Cannot publish as work pool, block has not been saved. Please call"
                " `.save()` on your block before publishing."
            )

        block_schema = self.__class__.schema()
        return {
            "job_configuration": {"block": "{{ block }}"},
            "variables": {
                "type": "object",
                "properties": {
                    "block": {
                        "title": "Block",
                        "description": (
                            "The infrastructure block to use for job creation."
                        ),
                        "allOf": [{"$ref": f"#/definitions/{self.__class__.__name__}"}],
                        "default": {
                            "$ref": {"block_document_id": str(self._block_document_id)}
                        },
                    }
                },
                "required": ["block"],
                "definitions": {self.__class__.__name__: block_schema},
            },
        }

    def get_corresponding_worker_type(self):
        return "block"

    @sync_compatible
    async def publish_as_work_pool(self, work_pool_name: Optional[str] = None):
        """
        Creates a work pool configured to use the given block as the job creator.

        Used to migrate from a agents setup to a worker setup.

        Args:
            work_pool_name: The name to give to the created work pool. If not provided, the name of the current
                block will be used.
        """

        base_job_template = await self.generate_work_pool_base_job_template()
        work_pool_name = work_pool_name or self._block_document_name

        if work_pool_name is None:
            raise ValueError(
                "`work_pool_name` must be provided if the block has not been saved."
            )

        console = Console()

        try:
            async with prefect.get_client() as client:
                work_pool = await client.create_work_pool(
                    work_pool=WorkPoolCreate(
                        name=work_pool_name,
                        type=self.get_corresponding_worker_type(),
                        base_job_template=base_job_template,
                    )
                )
        except ObjectAlreadyExists:
            console.print(
                (
                    f"Work pool with name {work_pool_name!r} already exists, please use"
                    " a different name."
                ),
                style="red",
            )
            return

        console.print(
            f"Work pool {work_pool.name} created!",
            style="green",
        )
        if PREFECT_UI_URL:
            console.print(
                "You see your new work pool in the UI at"
                f" {PREFECT_UI_URL.value()}/work-pools/work-pool/{work_pool.name}"
            )

        deploy_script = (
            "my_flow.deploy(work_pool_name='{work_pool.name}', image='my_image:tag')"
        )
        if not hasattr(self, "image"):
            deploy_script = (
                "my_flow.from_source(source='https://github.com/org/repo.git',"
                f" entrypoint='flow.py:my_flow').deploy(work_pool_name='{work_pool.name}')"
            )
        console.print(
            "\nYou can deploy a flow to this work pool by calling"
            f" [blue].deploy[/]:\n\n\t{deploy_script}\n"
        )
        console.print(
            "\nTo start a worker to execute flow runs in this work pool run:\n"
        )
        console.print(f"\t[blue]prefect worker start --pool {work_pool.name}[/]\n")

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

    @property
    def is_using_a_runner(self):
        return self.command is not None and "prefect flow-run execute" in shlex.join(
            self.command
        )

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
        deployment: Optional["Deployment"] = None,
        flow: Optional["Flow"] = None,
    ) -> Self:
        """
        Return an infrastructure block that is prepared to execute a flow run.
        """
        if deployment is not None:
            deployment_labels = self._base_deployment_labels(deployment)
        else:
            deployment_labels = {}

        if flow is not None:
            flow_labels = self._base_flow_labels(flow)
        else:
            flow_labels = {}

        return self.copy(
            update={
                "env": {**self._base_flow_run_environment(flow_run), **self.env},
                "labels": {
                    **self._base_flow_run_labels(flow_run),
                    **deployment_labels,
                    **flow_labels,
                    **self.labels,
                },
                "name": self.name or flow_run.name,
                "command": self.command or self._base_flow_run_command(),
            }
        )

    @staticmethod
    def _base_flow_run_command() -> List[str]:
        """
        Generate a command for a flow run job.
        """
        if experiment_enabled("enhanced_cancellation"):
            if (
                PREFECT_EXPERIMENTAL_WARN
                and PREFECT_EXPERIMENTAL_WARN_ENHANCED_CANCELLATION
            ):
                warnings.warn(
                    EXPERIMENTAL_WARNING.format(
                        feature="Enhanced flow run cancellation",
                        group="enhanced_cancellation",
                        help="",
                    ),
                    ExperimentalFeature,
                    stacklevel=3,
                )
            return ["prefect", "flow-run", "execute"]

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
        environment["PREFECT__FLOW_RUN_ID"] = str(flow_run.id)
        return environment

    @staticmethod
    def _base_deployment_labels(deployment: "Deployment") -> Dict[str, str]:
        labels = {
            "prefect.io/deployment-name": deployment.name,
        }
        if deployment.updated is not None:
            labels["prefect.io/deployment-updated"] = deployment.updated.in_timezone(
                "utc"
            ).to_iso8601_string()
        return labels

    @staticmethod
    def _base_flow_labels(flow: "Flow") -> Dict[str, str]:
        return {
            "prefect.io/flow-name": flow.name,
        }

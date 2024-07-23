import shlex
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import anyio
import anyio.abc

from prefect._internal.compatibility.deprecated import deprecated_class
from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect._internal.schemas.validators import validate_block_is_infrastructure
from prefect.blocks.core import Block
from prefect.client.schemas.objects import BlockDocument
from prefect.utilities.collections import get_from_dict
from prefect.workers.base import BaseWorker, BaseWorkerResult

if HAS_PYDANTIC_V2:
    from pydantic.v1 import BaseModel, Field, PrivateAttr, validator
else:
    from pydantic import BaseModel, Field, PrivateAttr, validator

from prefect.client.orchestration import PrefectClient
from prefect.client.utilities import inject_client
from prefect.events import RelatedResource
from prefect.events.related import object_as_related_resource, tags_as_related_resources
from prefect.utilities.templating import apply_values

if TYPE_CHECKING:
    from prefect.client.schemas.objects import Flow, FlowRun
    from prefect.client.schemas.responses import DeploymentResponse


@deprecated_class(
    start_date="Jun 2024",
    help="Refer to the upgrade guide for more information: https://docs.prefect.io/latest/guides/upgrade-guide-agents-to-workers/",
)
class BlockWorkerJobConfiguration(BaseModel):
    block: Block = Field(
        default=..., description="The infrastructure block to use for job creation."
    )

    @validator("block")
    def _validate_infrastructure_block(cls, v):
        return validate_block_is_infrastructure(v)

    _related_objects: Dict[str, Any] = PrivateAttr(default_factory=dict)

    @property
    def is_using_a_runner(self):
        return (
            self.block.command is not None
            and "prefect flow-run execute" in shlex.join(self.block.command)
        )

    @staticmethod
    def _get_base_config_defaults(variables: dict) -> dict:
        """Get default values from base config for all variables that have them."""
        defaults = dict()
        for variable_name, attrs in variables.items():
            if "default" in attrs:
                defaults[variable_name] = attrs["default"]

        return defaults

    @classmethod
    @inject_client
    async def from_template_and_values(
        cls, base_job_template: dict, values: dict, client: "PrefectClient" = None
    ):
        """Creates a valid worker configuration object from the provided base
        configuration and overrides.

        Important: this method expects that the base_job_template was already
        validated server-side.
        """
        job_config: Dict[str, Any] = base_job_template["job_configuration"]
        variables_schema = base_job_template["variables"]
        variables = cls._get_base_config_defaults(
            variables_schema.get("properties", {})
        )
        variables.update(values)

        populated_configuration = apply_values(template=job_config, values=variables)

        block_document_id = get_from_dict(
            populated_configuration, "block.$ref.block_document_id"
        )
        if not block_document_id:
            raise ValueError(
                "Base job template is invalid for this worker type because it does not"
                " contain a block_document_id after variable resolution."
            )

        block_document = await client.read_block_document(
            block_document_id=block_document_id
        )
        infrastructure_block = Block._from_block_document(block_document)

        populated_configuration["block"] = infrastructure_block

        return cls(**populated_configuration)

    @classmethod
    def json_template(cls) -> dict:
        """Returns a dict with job configuration as keys and the corresponding templates as values

        Defaults to using the job configuration parameter name as the template variable name.

        e.g.
        {
            key1: '{{ key1 }}',     # default variable template
            key2: '{{ template2 }}', # `template2` specifically provide as template
        }
        """
        configuration = {}
        properties = cls.schema()["properties"]
        for k, v in properties.items():
            if v.get("template"):
                template = v["template"]
            else:
                template = "{{ " + k + " }}"
            configuration[k] = template

        return configuration

    def _related_resources(self) -> List[RelatedResource]:
        tags = set()
        related = []

        for kind, obj in self._related_objects.items():
            if obj is None:
                continue
            if hasattr(obj, "tags"):
                tags.update(obj.tags)
            related.append(object_as_related_resource(kind=kind, role=kind, object=obj))

        return related + tags_as_related_resources(tags)

    def prepare_for_flow_run(
        self,
        flow_run: "FlowRun",
        deployment: Optional["DeploymentResponse"] = None,
        flow: Optional["Flow"] = None,
    ):
        self.block = self.block.prepare_for_flow_run(
            flow_run=flow_run, deployment=deployment, flow=flow
        )


class BlockWorkerResult(BaseWorkerResult):
    """Result of a block worker job"""


@deprecated_class(
    start_date="Jun 2024",
    help="Refer to the upgrade guide for more information: https://docs.prefect.io/latest/guides/upgrade-guide-agents-to-workers/",
)
class BlockWorker(BaseWorker):
    type = "block"
    job_configuration = BlockWorkerJobConfiguration

    _description = "Execute flow runs using an infrastructure block as the job creator."
    _display_name = "Block"

    async def run(
        self,
        flow_run: "FlowRun",
        configuration: BlockWorkerJobConfiguration,
        task_status: Optional[anyio.abc.TaskStatus] = None,
    ):
        block = configuration.block

        # logic for applying infra overrides taken from src/prefect/agent.py
        deployment = await self._client.read_deployment(flow_run.deployment_id)
        flow = await self._client.read_flow(deployment.flow_id)
        infra_document = await self._client.read_block_document(
            configuration.block._block_document_id
        )

        # this piece of logic applies any overrides that may have been set on the
        # deployment; overrides are defined as dot.delimited paths on possibly nested
        # attributes of the infrastructure block
        doc_dict = infra_document.dict()
        infra_dict = doc_dict.get("data", {})
        for override, value in (deployment.job_variables or {}).items():
            nested_fields = override.split(".")
            if nested_fields == ["command"]:
                value = shlex.split(value)
            data = infra_dict
            for field in nested_fields[:-1]:
                data = data[field]

            # once we reach the end, set the value
            data[nested_fields[-1]] = value

        # reconstruct the infra block
        doc_dict["data"] = infra_dict
        infra_document = BlockDocument(**doc_dict)
        block = Block._from_block_document(infra_document)

        block = block.prepare_for_flow_run(
            flow_run=flow_run, deployment=deployment, flow=flow
        )

        result = await block.run(
            task_status=task_status,
        )
        return BlockWorkerResult(
            identifier=result.identifier, status_code=result.status_code
        )

    async def kill_infrastructure(
        self,
        infrastructure_pid: str,
        configuration: BlockWorkerJobConfiguration,
        grace_seconds: int = 30,
    ):
        block = configuration.block
        if not hasattr(block, "kill"):
            self._logger.error(
                f"Flow run infrastructure block {block.type!r} "
                "does not support killing created infrastructure. "
                "Cancellation cannot be guaranteed."
            )
            return

        await block.kill(
            infrastructure_pid=infrastructure_pid, grace_seconds=grace_seconds
        )

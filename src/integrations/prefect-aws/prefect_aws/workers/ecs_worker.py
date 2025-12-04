"""
Prefect worker for executing flow runs as ECS tasks.

Get started by creating a work pool:

```
$ prefect work-pool create --type ecs my-ecs-pool
```

Then, you can start a worker for the pool:

```
$ prefect worker start --pool my-ecs-pool
```

It's common to deploy the worker as an ECS task as well. However, you can run the worker
locally to get started.

The worker may work without any additional configuration, but it is dependent on your
specific AWS setup and we'd recommend opening the work pool editor in the UI to see the
available options.

By default, the worker will register a task definition for each flow run and run a task
in your default ECS cluster using AWS Fargate. Fargate requires tasks to configure
subnets, which we will infer from your default VPC. If you do not have a default VPC,
you must provide a VPC ID or manually setup the network configuration for your tasks.

Note, the worker caches task definitions for each deployment to avoid excessive
registration. The worker will check that the cached task definition is compatible with
your configuration before using it.

The launch type option can be used to run your tasks in different modes. For example,
`FARGATE_SPOT` can be used to use spot instances for your Fargate tasks or `EC2` can be
used to run your tasks on a cluster backed by EC2 instances.

Generally, it is very useful to enable CloudWatch logging for your ECS tasks; this can
help you debug task failures. To enable CloudWatch logging, you must provide an
execution role ARN with permissions to create and write to log streams. See the
`configure_cloudwatch_logs` field documentation for details.

The worker can be configured to use an existing task definition by setting the task
definition arn variable or by providing a "taskDefinition" in the task run request. When
a task definition is provided, the worker will never create a new task definition which
may result in variables that are templated into the task definition payload being
ignored.
"""

from __future__ import annotations

import copy
import json
import logging
import shlex
from copy import deepcopy
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    NamedTuple,
    Optional,
    Tuple,
    cast,
)
from uuid import UUID

import anyio
import anyio.abc
import yaml
from pydantic import BaseModel, Field, model_validator
from slugify import slugify
from tenacity import retry, stop_after_attempt, wait_fixed, wait_random
from typing_extensions import Literal, Self

from prefect.client.schemas.objects import FlowRun
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.dockerutils import get_prefect_image_name
from prefect.utilities.templating import find_placeholders
from prefect.workers.base import (
    BaseJobConfiguration,
    BaseVariables,
    BaseWorker,
    BaseWorkerResult,
)
from prefect_aws.credentials import AwsCredentials
from prefect_aws.observers.ecs import start_observer, stop_observer

if TYPE_CHECKING:
    from mypy_boto3_ecs import ECSClient
    from mypy_boto3_ecs.type_defs import TaskDefinitionTypeDef

    from prefect.client.schemas.objects import APIFlow, DeploymentResponse, WorkPool

ECS_DEFAULT_CONTAINER_NAME = "prefect"
ECS_DEFAULT_CPU = 1024
ECS_DEFAULT_COMMAND = "python -m prefect.engine"
ECS_DEFAULT_MEMORY = 2048
ECS_DEFAULT_LAUNCH_TYPE = "FARGATE"
ECS_DEFAULT_FAMILY = "prefect"
ECS_POST_REGISTRATION_FIELDS = [
    "compatibilities",
    "taskDefinitionArn",
    "revision",
    "status",
    "requiresAttributes",
    "registeredAt",
    "registeredBy",
    "deregisteredAt",
]

DEFAULT_TASK_DEFINITION_TEMPLATE = """
containerDefinitions:
- image: "{{ image }}"
  name: "{{ container_name }}"
cpu: "{{ cpu }}"
family: "{{ family }}"
memory: "{{ memory }}"
executionRoleArn: "{{ execution_role_arn }}"
"""

DEFAULT_TASK_RUN_REQUEST_TEMPLATE = """
launchType: "{{ launch_type }}"
cluster: "{{ cluster }}"
overrides:
  containerOverrides:
    - name: "{{ container_name }}"
      command: "{{ command }}"
      environment: "{{ env }}"
      cpu: "{{ cpu }}"
      memory: "{{ memory }}"
  cpu: "{{ cpu }}"
  memory: "{{ memory }}"
  taskRoleArn: "{{ task_role_arn }}"
tags: "{{ labels }}"
taskDefinition: "{{ task_definition_arn }}"
capacityProviderStrategy: "{{ capacity_provider_strategy }}"
"""

# Create task run retry settings
MAX_CREATE_TASK_RUN_ATTEMPTS = 3
CREATE_TASK_RUN_MIN_DELAY_SECONDS = 1
CREATE_TASK_RUN_MIN_DELAY_JITTER_SECONDS = 0
CREATE_TASK_RUN_MAX_DELAY_JITTER_SECONDS = 3

_TASK_DEFINITION_CACHE: Dict[UUID, str] = {}
_TAG_REGEX = r"[^a-zA-Z0-9_./=+:@-]"


class ECSIdentifier(NamedTuple):
    """
    The identifier for a running ECS task.
    """

    cluster: str
    task_arn: str


def _default_task_definition_template() -> dict:
    """
    The default task definition template for ECS jobs.
    """
    return yaml.safe_load(DEFAULT_TASK_DEFINITION_TEMPLATE)


def _default_task_run_request_template() -> dict:
    """
    The default task run request template for ECS jobs.
    """
    return yaml.safe_load(DEFAULT_TASK_RUN_REQUEST_TEMPLATE)


def _drop_empty_keys_from_dict(taskdef: dict):
    """
    Recursively drop keys with 'empty' values from a task definition dict.

    Mutates the task definition in place. Only supports recursion into dicts and lists.
    """
    for key, value in tuple(taskdef.items()):
        if not value:
            taskdef.pop(key)
        if isinstance(value, dict):
            _drop_empty_keys_from_dict(value)
        if isinstance(value, list) and key != "capacity_provider_strategy":
            for v in value:
                if isinstance(v, dict):
                    _drop_empty_keys_from_dict(v)


def _get_container(
    containers: list[dict[str, Any]], name: str
) -> Optional[dict[str, Any]]:
    """
    Extract a container from a list of containers or container definitions.
    If not found, `None` is returned.
    """
    for container in containers:
        if container.get("name") == name:
            return container
    return None


def _container_name_from_task_definition(task_definition: dict) -> Optional[str]:
    """
    Attempt to infer the container name from a task definition.

    If not found, `None` is returned.
    """
    if task_definition:
        container_definitions = task_definition.get("containerDefinitions", [])
    else:
        container_definitions = []

    if _get_container(container_definitions, ECS_DEFAULT_CONTAINER_NAME):
        # Use the default container name if present
        return ECS_DEFAULT_CONTAINER_NAME
    elif container_definitions:
        # Otherwise, if there's at least one container definition try to get the
        # name from that
        return container_definitions[0].get("name")

    return None


def parse_identifier(identifier: str) -> ECSIdentifier:
    """
    Splits identifier into its cluster and task components, e.g.
    input "cluster_name::task_arn" outputs ("cluster_name", "task_arn").
    """
    cluster, task = identifier.split("::", maxsplit=1)
    return ECSIdentifier(cluster, task)


def mask_sensitive_env_values(
    task_run_request: dict, values: List[str], keep_length=3, replace_with="***"
):
    for container in task_run_request.get("overrides", {}).get(
        "containerOverrides", []
    ):
        for env_var in container.get("environment", []):
            if (
                "name" not in env_var
                or "value" not in env_var
                or env_var["name"] not in values
            ):
                continue
            if len(env_var["value"]) > keep_length:
                # Replace characters beyond the keep length
                env_var["value"] = env_var["value"][:keep_length] + replace_with
    return task_run_request


def mask_api_key(task_run_request):
    return mask_sensitive_env_values(
        deepcopy(task_run_request),
        ["PREFECT_API_KEY", "PREFECT_API_AUTH_STRING"],
        keep_length=6,
    )


class CapacityProvider(BaseModel):
    """
    The capacity provider strategy to use when running the task.
    """

    capacityProvider: str
    weight: int
    base: int


class ECSJobConfiguration(BaseJobConfiguration):
    """
    Job configuration for an ECS worker.
    """

    aws_credentials: Optional[AwsCredentials] = Field(default_factory=AwsCredentials)
    task_definition: Dict[str, Any] = Field(
        default_factory=dict,
        json_schema_extra=dict(template=_default_task_definition_template()),
    )
    task_run_request: Dict[str, Any] = Field(
        default_factory=dict,
        json_schema_extra=dict(template=_default_task_run_request_template()),
    )
    configure_cloudwatch_logs: Optional[bool] = Field(default=None)
    cloudwatch_logs_options: Dict[str, str] = Field(default_factory=dict)
    cloudwatch_logs_prefix: Optional[str] = Field(default=None)
    network_configuration: Dict[str, Any] = Field(default_factory=dict)
    stream_output: Optional[bool] = Field(
        default=None,
        json_schema_extra=dict(template=False),
        deprecated="This field is no longer used and will be removed in a future release.",
    )
    task_start_timeout_seconds: int = Field(
        default=300,
        json_schema_extra=dict(template=0),
        deprecated="This field is no longer used and will be removed in a future release.",
    )
    task_watch_poll_interval: float = Field(
        default=5.0,
        json_schema_extra=dict(template=0),
        deprecated="This field is no longer used and will be removed in a future release.",
    )
    auto_deregister_task_definition: bool = Field(default=False)
    vpc_id: Optional[str] = Field(default=None)
    container_name: Optional[str] = Field(default=None)
    cluster: Optional[str] = Field(default=None)
    match_latest_revision_in_family: bool = Field(default=False)
    prefect_api_key_secret_arn: Optional[str] = Field(default=None)
    prefect_api_auth_string_secret_arn: Optional[str] = Field(default=None)

    execution_role_arn: Optional[str] = Field(
        title="Execution Role ARN",
        default=None,
        description=(
            "An execution role to use for the task. This controls the permissions of "
            "the task when it is launching. If this value is not null, it will "
            "override the value in the task definition. An execution role must be "
            "provided to capture logs from the container."
        ),
    )

    @classmethod
    def json_template(cls) -> dict[str, Any]:
        """Returns a dict with job configuration as keys and the corresponding templates as values

        Defaults to using the job configuration parameter name as the template variable name.

        e.g.
        ```python
        {
            key1: '{{ key1 }}',     # default variable template
            key2: '{{ template2 }}', # `template2` specifically provide as template
        }
        ```
        """
        # This is overridden because the base class was incorrectly handling `False`
        # TODO: Update the base class, remove this override, and bump the minimum `prefect` version
        configuration: dict[str, Any] = {}
        properties = cls.model_json_schema()["properties"]
        for k, v in properties.items():
            if v.get("template") is not None:
                template = v["template"]
            else:
                template = "{{ " + k + " }}"
            configuration[k] = template

        return configuration

    def prepare_for_flow_run(
        self,
        flow_run: "FlowRun",
        deployment: "DeploymentResponse | None" = None,
        flow: "APIFlow | None" = None,
        work_pool: "WorkPool | None" = None,
        worker_name: str | None = None,
    ) -> None:
        super().prepare_for_flow_run(flow_run, deployment, flow, work_pool, worker_name)
        if self.prefect_api_key_secret_arn:
            # Remove the PREFECT_API_KEY from the environment variables because it will be provided via a secret
            del self.env["PREFECT_API_KEY"]
        if self.prefect_api_auth_string_secret_arn:
            # Remove the PREFECT_API_AUTH_STRING from the environment variables because it will be provided via a secret
            if "PREFECT_API_AUTH_STRING" in self.env:
                del self.env["PREFECT_API_AUTH_STRING"]

    @model_validator(mode="after")
    def task_run_request_requires_arn_if_no_task_definition_given(self) -> Self:
        """
        If no task definition is provided, a task definition ARN must be present on the
        task run request.
        """
        if (
            not (self.task_run_request or {}).get("taskDefinition")
            and not self.task_definition
        ):
            raise ValueError(
                "A task definition must be provided if a task definition ARN is not "
                "present on the task run request."
            )
        return self

    @model_validator(mode="after")
    def container_name_default_from_task_definition(self) -> Self:
        """
        Infers the container name from the task definition if not provided.
        """
        if self.container_name is None:
            self.container_name = _container_name_from_task_definition(
                self.task_definition
            )

            # We may not have a name here still; for example if someone is using a task
            # definition arn. In that case, we'll perform similar logic later to find
            # the name to treat as the "orchestration" container.

        return self

    @model_validator(mode="after")
    def configure_cloudwatch_logs_requires_execution_role_arn(
        self,
    ) -> Self:
        """
        Enforces that an execution role arn is provided (or could be provided by a
        runtime task definition) when configuring logging.
        """
        if (
            self.configure_cloudwatch_logs
            and not self.execution_role_arn
            # TODO: Does not match
            # Do not raise if they've linked to another task definition or provided
            # it without using our shortcuts
            and not (self.task_run_request or {}).get("taskDefinition")
            and not (self.task_definition or {}).get("executionRoleArn")
        ):
            raise ValueError(
                "An `execution_role_arn` must be provided to use "
                "`configure_cloudwatch_logs` or `stream_logs`."
            )
        return self

    @model_validator(mode="after")
    def cloudwatch_logs_options_requires_configure_cloudwatch_logs(
        self,
    ) -> Self:
        """
        Enforces that an execution role arn is provided (or could be provided by a
        runtime task definition) when configuring logging.
        """
        if self.cloudwatch_logs_options and not self.configure_cloudwatch_logs:
            raise ValueError(
                "`configure_cloudwatch_log` must be enabled to use "
                "`cloudwatch_logs_options`."
            )
        return self

    @model_validator(mode="after")
    def network_configuration_requires_vpc_id(self) -> Self:
        """
        Enforces a `vpc_id` is provided when custom network configuration mode is
        enabled for network settings.
        """
        if self.network_configuration and not self.vpc_id:
            raise ValueError(
                "You must provide a `vpc_id` to enable custom `network_configuration`."
            )
        return self


class ECSVariables(BaseVariables):
    """
    Variables for templating an ECS job.
    """

    task_definition_arn: Optional[str] = Field(
        title="Task Definition ARN",
        default=None,
        description=(
            "An identifier for an existing task definition to use. If set, options that"
            " require changes to the task definition will be ignored. All contents of "
            "the task definition in the job configuration will be ignored."
        ),
    )
    env: Dict[str, Optional[str]] = Field(
        title="Environment Variables",
        default_factory=dict,
        description=(
            "Environment variables to provide to the task run. These variables are set "
            "on the Prefect container at task runtime. These will not be set on the "
            "task definition."
        ),
    )
    aws_credentials: AwsCredentials = Field(
        title="AWS Credentials",
        default_factory=AwsCredentials,
        description=(
            "The AWS credentials to use to connect to ECS. If not provided, credentials"
            " will be inferred from the local environment following AWS's boto client's"
            " rules."
        ),
    )
    cluster: Optional[str] = Field(
        default=None,
        description=(
            "The ECS cluster to run the task in. An ARN or name may be provided. If "
            "not provided, the default cluster will be used."
        ),
    )
    family: Optional[str] = Field(
        default=None,
        description=(
            "A family for the task definition. If not provided, it will be inferred "
            "from the task definition. If the task definition does not have a family, "
            "the name will be generated. When flow and deployment metadata is "
            "available, the generated name will include their names. Values for this "
            "field will be slugified to match AWS character requirements."
        ),
    )
    launch_type: Literal["FARGATE", "EC2", "EXTERNAL", "FARGATE_SPOT"] = Field(
        default=ECS_DEFAULT_LAUNCH_TYPE,
        description=(
            "The type of ECS task run infrastructure that should be used. Note that"
            " 'FARGATE_SPOT' is not a formal ECS launch type, but we will configure"
            " the proper capacity provider strategy if set here."
        ),
    )
    capacity_provider_strategy: List[CapacityProvider] = Field(
        default_factory=list,
        description=(
            "The capacity provider strategy to use when running the task. "
            "If a capacity provider strategy is specified, the selected launch"
            " type will be ignored."
        ),
    )
    image: Optional[str] = Field(
        default=None,
        description=(
            "The image to use for the Prefect container in the task. If this value is "
            "not null, it will override the value in the task definition. This value "
            "defaults to a Prefect base image matching your local versions."
        ),
    )
    cpu: Optional[int] = Field(
        title="CPU",
        default=None,
        description=(
            "The amount of CPU to provide to the ECS task. Valid amounts are "
            "specified in the AWS documentation. If not provided, a default value of "
            f"{ECS_DEFAULT_CPU} will be used unless present on the task definition."
        ),
    )
    memory: Optional[int] = Field(
        default=None,
        description=(
            "The amount of memory to provide to the ECS task. Valid amounts are "
            "specified in the AWS documentation. If not provided, a default value of "
            f"{ECS_DEFAULT_MEMORY} will be used unless present on the task definition."
        ),
    )
    container_name: Optional[str] = Field(
        default=None,
        description=(
            "The name of the container flow run orchestration will occur in. If not "
            f"specified, a default value of {ECS_DEFAULT_CONTAINER_NAME} will be used "
            "and if that is not found in the task definition the first container will "
            "be used."
        ),
    )
    prefect_api_key_secret_arn: Optional[str] = Field(
        title="Prefect API Key Secret ARN",
        default=None,
        description=(
            "An ARN of an AWS secret containing a Prefect API key. This key will be used "
            "to authenticate ECS tasks with Prefect Cloud. If not provided, the "
            "PREFECT_API_KEY environment variable will be used if the worker has one."
        ),
    )
    prefect_api_auth_string_secret_arn: Optional[str] = Field(
        title="Prefect API Auth String Secret ARN",
        default=None,
        description=(
            "An ARN of an AWS secret containing a Prefect API auth string. This string will be used "
            "to authenticate ECS tasks with Prefect Cloud. If not provided, the "
            "PREFECT_API_AUTH_STRING environment variable will be used if the worker has one."
        ),
    )
    task_role_arn: Optional[str] = Field(
        title="Task Role ARN",
        default=None,
        description=(
            "A role to attach to the task run. This controls the permissions of the "
            "task while it is running."
        ),
    )
    execution_role_arn: Optional[str] = Field(
        title="Execution Role ARN",
        default=None,
        description=(
            "An execution role to use for the task. This controls the permissions of "
            "the task when it is launching. If this value is not null, it will "
            "override the value in the task definition. An execution role must be "
            "provided to capture logs from the container."
        ),
    )
    vpc_id: Optional[str] = Field(
        title="VPC ID",
        default=None,
        description=(
            "The AWS VPC to link the task run to. This is only applicable when using "
            "the 'awsvpc' network mode for your task. FARGATE tasks require this "
            "network  mode, but for EC2 tasks the default network mode is 'bridge'. "
            "If using the 'awsvpc' network mode and this field is null, your default "
            "VPC will be used. If no default VPC can be found, the task run will fail."
        ),
    )
    configure_cloudwatch_logs: Optional[bool] = Field(
        default=None,
        description=(
            "If enabled, the Prefect container will be configured to send its output "
            "to the AWS CloudWatch logs service. This functionality requires an "
            "execution role with logs:CreateLogStream, logs:CreateLogGroup, and "
            "logs:PutLogEvents permissions. The default for this field is `False`."
        ),
    )
    cloudwatch_logs_options: Dict[str, str] = Field(
        default_factory=dict,
        description=(
            "When `configure_cloudwatch_logs` is enabled, this setting may be used to"
            " pass additional options to the CloudWatch logs configuration or override"
            " the default options. See the [AWS"
            " documentation](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/using_awslogs.html#create_awslogs_logdriver_options)"  # noqa
            " for available options. "
        ),
    )
    cloudwatch_logs_prefix: Optional[str] = Field(
        default=None,
        description=(
            "When `configure_cloudwatch_logs` is enabled, this setting may be used to"
            " set a prefix for the log group. If not provided, the default prefix will"
            " be `prefect-logs_<work_pool_name>_<deployment_id>`. If"
            " `awslogs-stream-prefix` is present in `Cloudwatch logs options` this"
            " setting will be ignored."
        ),
    )

    network_configuration: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "When `network_configuration` is supplied it will override ECS Worker's"
            "awsvpcConfiguration that defined in the ECS task executing your workload. "
            "See the [AWS documentation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-service-awsvpcconfiguration.html)"  # noqa
            " for available options."
        ),
    )
    auto_deregister_task_definition: bool = Field(
        default=False,
        description=(
            "If enabled, any task definitions that are created by this block will be "
            "deregistered. Existing task definitions linked by ARN will never be "
            "deregistered. Deregistering a task definition does not remove it from "
            "your AWS account, instead it will be marked as INACTIVE."
        ),
    )
    match_latest_revision_in_family: bool = Field(
        default=False,
        description=(
            "If enabled, the most recent active revision in the task definition "
            "family will be compared against the desired ECS task configuration. "
            "If they are equal, the existing task definition will be used instead "
            "of registering a new one. If no family is specified the default family "
            f'"{ECS_DEFAULT_FAMILY}" will be used.'
        ),
    )


class ECSWorkerResult(BaseWorkerResult):
    """
    The result of an ECS job.
    """


class ECSWorker(BaseWorker[ECSJobConfiguration, ECSVariables, ECSWorkerResult]):
    """
    A Prefect worker to run flow runs as ECS tasks.
    """

    type: str = "ecs"
    job_configuration: type[ECSJobConfiguration] = ECSJobConfiguration
    job_configuration_variables: type[ECSVariables] | None = ECSVariables
    _description: str = (
        "Execute flow runs within containers on AWS ECS. Works with EC2 "
        "and Fargate clusters. Requires an AWS account."
    )
    _display_name = "AWS Elastic Container Service"
    _documentation_url = "https://docs.prefect.io/integrations/prefect-aws/"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/d74b16fe84ce626345adf235a47008fea2869a60-225x225.png"  # noqa

    async def _initiate_run(
        self,
        flow_run: "FlowRun",
        configuration: ECSJobConfiguration,
    ):
        """
        Initiates a flow run on AWS ECS. This method does not wait for the flow run to complete.
        """
        ecs_client = await run_sync_in_worker_thread(
            configuration.aws_credentials.get_client, "ecs"
        )

        logger = cast(logging.Logger, self.get_flow_run_logger(flow_run))

        await run_sync_in_worker_thread(
            self._prepare_and_create_task,
            logger,
            ecs_client,
            configuration,
            flow_run,
        )

    async def run(
        self,
        flow_run: "FlowRun",
        configuration: ECSJobConfiguration,
        task_status: Optional[anyio.abc.TaskStatus] = None,
    ) -> ECSWorkerResult:
        """
        Runs a given flow run on the current worker.
        """
        ecs_client = await run_sync_in_worker_thread(
            configuration.aws_credentials.get_client, "ecs"
        )

        logger = cast(logging.Logger, self.get_flow_run_logger(flow_run))

        (
            task_arn,
            cluster_arn,
        ) = await run_sync_in_worker_thread(
            self._prepare_and_create_task,
            logger,
            ecs_client,
            configuration,
            flow_run,
        )

        # The task identifier is "{cluster}::{task}" where we use the configured cluster
        # if set to preserve matching by name rather than arn
        # Note "::" is used despite the Prefect standard being ":" because ARNs contain
        # single colons.
        identifier = (
            (configuration.cluster if configuration.cluster else cluster_arn)
            + "::"
            + task_arn
        )

        if task_status:
            task_status.started(identifier)

        return ECSWorkerResult(
            identifier=identifier,
            # The observer will handle crash detection, so we can always return 1 if the task
            # was created successfully
            status_code=0,
        )

    def _prepare_and_create_task(
        self,
        logger: logging.Logger,
        ecs_client: "ECSClient",
        configuration: ECSJobConfiguration,
        flow_run: FlowRun,
    ) -> Tuple[str, str, dict, bool]:
        """
        Register the task definition, create the task run, and wait for it to start.

        Returns a tuple of
        - The task ARN
        - The task's cluster ARN
        - The task definition
        - A bool indicating if the task definition is newly registered
        """
        task_definition_arn = configuration.task_run_request.get("taskDefinition")
        new_task_definition_registered = False

        if not task_definition_arn:
            task_definition = self._prepare_task_definition(
                configuration, region=ecs_client.meta.region_name, flow_run=flow_run
            )

            (
                task_definition_arn,
                new_task_definition_registered,
            ) = self._get_or_register_task_definition(
                logger, ecs_client, configuration, flow_run, task_definition
            )
        else:
            task_definition = self._retrieve_task_definition(
                logger, ecs_client, task_definition_arn
            )
            if configuration.task_definition:
                template_with_placeholders = self.work_pool.base_job_template[
                    "job_configuration"
                ]["task_definition"]
                placeholders = [
                    placeholder.name
                    for placeholder in find_placeholders(template_with_placeholders)
                ]

                logger.warning(
                    "Skipping task definition construction since a task definition"
                    " ARN is provided."
                )

                if placeholders:
                    logger.warning(
                        "The following job variable references"
                        " in the task definition template will be ignored: "
                        + ", ".join(placeholders)
                    )

        # Note: _prepare_task_definition (called later) mutates the task definition so
        # validation needs to account for the mutation logic
        self._validate_task_definition(task_definition, configuration)

        if flow_run.deployment_id:
            _TASK_DEFINITION_CACHE[flow_run.deployment_id] = task_definition_arn
        else:
            _TASK_DEFINITION_CACHE[flow_run.flow_id] = task_definition_arn

        logger.info(f"Using ECS task definition {task_definition_arn!r}...")
        logger.debug(
            f"Task definition {json.dumps(task_definition, indent=2, default=str)}"
        )

        task_run_request = self._prepare_task_run_request(
            configuration,
            task_definition,
            task_definition_arn,
            new_task_definition_registered,
        )

        logger.info("Creating ECS task run...")
        logger.debug(
            "Task run request"
            f"{json.dumps(mask_api_key(task_run_request), indent=2, default=str)}"
        )

        try:
            task = self._create_task_run(ecs_client, task_run_request)
            task_arn = task["taskArn"]
            cluster_arn = task["clusterArn"]
        except Exception as exc:
            self._report_task_run_creation_failure(configuration, task_run_request, exc)
            raise

        return task_arn, cluster_arn

    def _report_task_run_creation_failure(
        self, configuration: ECSJobConfiguration, task_run: dict, exc: Exception
    ) -> None:
        """
        Wrap common AWS task run creation failures with nicer user-facing messages.
        """
        # AWS generates exception types at runtime so they must be captured a bit
        # differently than normal.
        if "ClusterNotFoundException" in str(exc):
            cluster = task_run.get("cluster", "default")
            raise RuntimeError(
                f"Failed to run ECS task, cluster {cluster!r} not found. "
                "Confirm that the cluster is configured in your region."
            ) from exc
        elif (
            "No Container Instances" in str(exc) and task_run.get("launchType") == "EC2"
        ):
            cluster = task_run.get("cluster", "default")
            raise RuntimeError(
                f"Failed to run ECS task, cluster {cluster!r} does not appear to "
                "have any container instances associated with it. Confirm that you "
                "have EC2 container instances available."
            ) from exc
        elif (
            "failed to validate logger args" in str(exc)
            and "AccessDeniedException" in str(exc)
            and configuration.configure_cloudwatch_logs
        ):
            raise RuntimeError(
                "Failed to run ECS task, the attached execution role does not appear"
                " to have sufficient permissions. Ensure that the execution role"
                f" {configuration.execution_role!r} has permissions"
                " logs:CreateLogStream, logs:CreateLogGroup, and logs:PutLogEvents."
            )
        else:
            raise

    def _get_or_register_task_definition(
        self,
        logger: logging.Logger,
        ecs_client: "ECSClient",
        configuration: ECSJobConfiguration,
        flow_run: FlowRun,
        task_definition: dict[str, Any],
    ) -> Tuple[str, bool]:
        """Get or register a task definition for the given flow run.

        Returns a tuple of the task definition ARN and a bool indicating if the task
        definition is newly registered.
        """

        cached_task_definition_arn = (
            _TASK_DEFINITION_CACHE.get(flow_run.deployment_id)
            if flow_run.deployment_id
            else _TASK_DEFINITION_CACHE.get(flow_run.flow_id)
        )
        new_task_definition_registered = False

        if cached_task_definition_arn:
            try:
                cached_task_definition = self._retrieve_task_definition(
                    logger, ecs_client, cached_task_definition_arn
                )
                if not cached_task_definition[
                    "status"
                ] == "ACTIVE" or not self._task_definitions_equal(
                    task_definition, cached_task_definition, logger
                ):
                    cached_task_definition_arn = None
            except Exception as e:
                logger.warning(
                    f"Failed to retrieve task definition for cached arn {cached_task_definition_arn!r}. "
                    f"Error: {e}"
                )
                cached_task_definition_arn = None

        if (
            not cached_task_definition_arn
            and configuration.match_latest_revision_in_family
        ):
            family_name = task_definition.get("family", ECS_DEFAULT_FAMILY)
            try:
                task_definition_from_family = self._retrieve_task_definition(
                    logger, ecs_client, family_name
                )
                if task_definition_from_family and self._task_definitions_equal(
                    task_definition, task_definition_from_family, logger
                ):
                    cached_task_definition_arn = task_definition_from_family[
                        "taskDefinitionArn"
                    ]
            except Exception as e:
                logger.warning(
                    f"Failed to retrieve task definition for family {family_name!r}. "
                    f"Error: {e}"
                )
                cached_task_definition_arn = None

        if not cached_task_definition_arn:
            task_definition_arn = self._register_task_definition(
                logger, ecs_client, task_definition
            )
            new_task_definition_registered = True
        else:
            task_definition_arn = cached_task_definition_arn

        return task_definition_arn, new_task_definition_registered

    def _validate_task_definition(
        self, task_definition: dict, configuration: ECSJobConfiguration
    ) -> None:
        """
        Ensure that the task definition is compatible with the configuration.

        Raises `ValueError` on incompatibility. Returns `None` on success.
        """
        if configuration.configure_cloudwatch_logs and not task_definition.get(
            "executionRoleArn"
        ):
            raise ValueError(
                "An execution role arn must be set on the task definition to use "
                "`configure_cloudwatch_logs` or `stream_logs` but no execution role "
                "was found on the task definition."
            )

        launch_type = configuration.task_run_request.get("launchType")
        capacity_provider_strategy = configuration.task_run_request.get(
            "capacityProviderStrategy"
        )
        requires_ec2 = "EC2" in task_definition.get("requiresCompatibilities", [])

        # Users may submit a job with a custom capacity provider strategy which requires
        # launch type to be empty. EC2 task definitions may also omit launch type to use
        # the cluster's default capacity provider.
        if not launch_type and not capacity_provider_strategy:
            if not requires_ec2:
                launch_type = ECS_DEFAULT_LAUNCH_TYPE

        # Fargate spot requires a launch type and a capacity provider strategy
        # otherwise we're valid with a capacity provider strategy alone
        if capacity_provider_strategy and launch_type != "FARGATE_SPOT":
            return

        # EC2 task definitions with null launch_type are valid - they use the cluster's
        # default capacity provider. See https://github.com/PrefectHQ/prefect/issues/19627
        if requires_ec2 and not launch_type:
            return

        # Default launch type in compatibilities to maintain functionality with
        # _prepare_task_definition which sets requiresCompatibilties to FARGATE
        # which is the default launch type.
        if launch_type != "EC2" and "FARGATE" not in task_definition.get(
            "requiresCompatibilities", [ECS_DEFAULT_LAUNCH_TYPE]
        ):
            raise ValueError(
                "Task definition does not have 'FARGATE' in 'requiresCompatibilities'"
                f" and cannot be used with launch type {launch_type!r}"
            )

        if launch_type == "FARGATE" or launch_type == "FARGATE_SPOT":
            # Only the 'awsvpc' network mode is supported when using FARGATE
            # Default to 'awsvpc' if not provided to maintain functionality with
            # _prepare_task_definition which sets network mode to 'awsvpc' if not provided.
            network_mode = task_definition.get("networkMode", "awsvpc")
            if network_mode != "awsvpc":
                raise ValueError(
                    f"Found network mode {network_mode!r} which is not compatible with "
                    f"launch type {launch_type!r}. Use either the 'EC2' launch "
                    "type or the 'awsvpc' network mode."
                )

    def _register_task_definition(
        self,
        logger: logging.Logger,
        ecs_client: "ECSClient",
        task_definition: dict,
    ) -> str:
        """
        Register a new task definition with AWS.

        Returns the ARN.
        """
        logger.info("Registering ECS task definition...")
        logger.debug(
            "Task definition request"
            f"{json.dumps(task_definition, indent=2, default=str)}"
        )

        response = ecs_client.register_task_definition(**task_definition)
        return response["taskDefinition"]["taskDefinitionArn"]

    def _retrieve_task_definition(
        self,
        logger: logging.Logger,
        ecs_client: "ECSClient",
        task_definition: str,
    ):
        """
        Retrieve an existing task definition from AWS.
        """
        if task_definition.startswith("arn:aws:ecs:"):
            logger.info(f"Retrieving ECS task definition {task_definition!r}...")
        else:
            logger.info(
                "Retrieving most recent active revision from "
                f"ECS task family {task_definition!r}..."
            )
        response = ecs_client.describe_task_definition(taskDefinition=task_definition)
        return response["taskDefinition"]

    def _get_or_generate_family(
        self, task_definition: dict[str, Any], flow_run: FlowRun
    ) -> str:
        """
        Gets or generate a family for the task definition.
        """
        family = task_definition.get("family")
        if not family:
            family_prefix = f"{ECS_DEFAULT_FAMILY}_{self._work_pool_name}"
            if flow_run.deployment_id:
                family = f"{family_prefix}_{flow_run.deployment_id}"
            else:
                family = f"{family_prefix}_{flow_run.flow_id}"
        slugify(
            family,
            max_length=255,
            regex_pattern=r"[^a-zA-Z0-9-_]+",
        )
        return family

    def _prepare_task_definition(
        self,
        configuration: ECSJobConfiguration,
        region: str,
        flow_run: FlowRun,
    ) -> dict[str, Any]:
        """
        Prepare a task definition by inferring any defaults and merging overrides.
        """
        task_definition = copy.deepcopy(configuration.task_definition)

        # Configure the Prefect runtime container
        task_definition.setdefault("containerDefinitions", [])

        # Remove empty container definitions
        task_definition["containerDefinitions"] = [
            d for d in task_definition["containerDefinitions"] if d
        ]

        container_name = configuration.container_name
        if not container_name:
            container_name = (
                _container_name_from_task_definition(task_definition)
                or ECS_DEFAULT_CONTAINER_NAME
            )

        container: dict[str, Any] | None = _get_container(
            task_definition["containerDefinitions"], container_name
        )
        if container is None:
            if container_name != ECS_DEFAULT_CONTAINER_NAME:
                raise ValueError(
                    f"Container {container_name!r} not found in task definition."
                )

            # Look for a container without a name
            for container in task_definition["containerDefinitions"]:
                if "name" not in container:
                    container["name"] = container_name
                    break
            else:
                container = {"name": container_name}
                task_definition["containerDefinitions"].append(container)

        if TYPE_CHECKING:
            assert container is not None

        # Image is required so make sure it's present
        container.setdefault("image", get_prefect_image_name())

        # Remove any keys that have been explicitly "unset"
        unset_keys = {key for key, value in configuration.env.items() if value is None}
        for item in tuple(container.get("environment", [])):
            if item["name"] in unset_keys or item["value"] is None:
                container["environment"].remove(item)

        if configuration.configure_cloudwatch_logs:
            prefix = f"prefect-logs_{self._work_pool_name}"
            if flow_run.deployment_id:
                prefix = f"{prefix}_{flow_run.deployment_id}"
            else:
                prefix = f"{prefix}_{flow_run.flow_id}"

            container["logConfiguration"] = {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-create-group": "true",
                    "awslogs-group": "prefect",
                    "awslogs-region": region,
                    "awslogs-stream-prefix": (
                        configuration.cloudwatch_logs_prefix or prefix
                    ),
                    **configuration.cloudwatch_logs_options,
                },
            }

        task_definition["family"] = self._get_or_generate_family(
            task_definition, flow_run
        )
        # CPU and memory are required in some cases, retrieve the value to use
        cpu = task_definition.get("cpu") or ECS_DEFAULT_CPU
        memory = task_definition.get("memory") or ECS_DEFAULT_MEMORY

        launch_type = configuration.task_run_request.get("launchType")

        if launch_type == "FARGATE" or launch_type == "FARGATE_SPOT":
            # Task level memory and cpu are required when using fargate
            task_definition["cpu"] = str(cpu)
            task_definition["memory"] = str(memory)

            # The FARGATE compatibility is required if it will be used as as launch type
            requires_compatibilities = task_definition.setdefault(
                "requiresCompatibilities", []
            )
            if "FARGATE" not in requires_compatibilities:
                task_definition["requiresCompatibilities"].append("FARGATE")

            # Only the 'awsvpc' network mode is supported when using FARGATE
            # However, we will not enforce that here if the user has set it
            task_definition.setdefault("networkMode", "awsvpc")

        else:
            # Container level memory and cpu are required when using non-FARGATE launch types
            container.setdefault("cpu", int(cpu))
            container.setdefault("memory", int(memory))

        # Ensure set values are cast to strings
        if task_definition.get("cpu"):
            task_definition["cpu"] = str(task_definition["cpu"])
        if task_definition.get("memory"):
            task_definition["memory"] = str(task_definition["memory"])

        _drop_empty_keys_from_dict(task_definition)

        # Handle secrets for both API key and auth string
        secrets = []
        if configuration.prefect_api_key_secret_arn:
            secrets.append(
                {
                    "name": "PREFECT_API_KEY",
                    "valueFrom": configuration.prefect_api_key_secret_arn,
                }
            )
            # Remove the PREFECT_API_KEY from the environment variables
            for item in tuple(container.get("environment", [])):
                if item["name"] == "PREFECT_API_KEY":
                    container["environment"].remove(item)  # type: ignore

        if configuration.prefect_api_auth_string_secret_arn:
            secrets.append(
                {
                    "name": "PREFECT_API_AUTH_STRING",
                    "valueFrom": configuration.prefect_api_auth_string_secret_arn,
                }
            )
            # Remove the PREFECT_API_AUTH_STRING from the environment variables
            for item in tuple(container.get("environment", [])):
                if item["name"] == "PREFECT_API_AUTH_STRING":
                    container["environment"].remove(item)  # type: ignore

        if secrets:
            container["secrets"] = secrets

        return task_definition

    def _load_network_configuration(
        self, vpc_id: Optional[str], configuration: ECSJobConfiguration
    ) -> dict:
        """
        Load settings from a specific VPC or the default VPC and generate a task
        run request's network configuration.
        """
        ec2_client = configuration.aws_credentials.get_client("ec2")
        vpc_message = "the default VPC" if not vpc_id else f"VPC with ID {vpc_id}"

        if not vpc_id:
            # Retrieve the default VPC
            describe = {"Filters": [{"Name": "isDefault", "Values": ["true"]}]}
        else:
            describe = {"VpcIds": [vpc_id]}

        vpcs = ec2_client.describe_vpcs(**describe)["Vpcs"]
        if not vpcs:
            help_message = (
                "Pass an explicit `vpc_id` or configure a default VPC."
                if not vpc_id
                else "Check that the VPC exists in the current region."
            )
            raise ValueError(
                f"Failed to find {vpc_message}. "
                "Network configuration cannot be inferred. " + help_message
            )

        vpc_id = vpcs[0]["VpcId"]
        subnets = ec2_client.describe_subnets(
            Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
        )["Subnets"]
        if not subnets:
            raise ValueError(
                f"Failed to find subnets for {vpc_message}. "
                "Network configuration cannot be inferred."
            )

        return {
            "awsvpcConfiguration": {
                "subnets": [s["SubnetId"] for s in subnets],
                "assignPublicIp": "ENABLED",
                "securityGroups": [],
            }
        }

    def _custom_network_configuration(
        self,
        vpc_id: str,
        network_configuration: dict,
        configuration: ECSJobConfiguration,
    ) -> dict:
        """
        Load settings from a specific VPC or the default VPC and generate a task
        run request's network configuration.
        """
        ec2_client = configuration.aws_credentials.get_client("ec2")
        vpc_message = f"VPC with ID {vpc_id}"

        vpcs = ec2_client.describe_vpcs(VpcIds=[vpc_id]).get("Vpcs")

        if not vpcs:
            raise ValueError(
                f"Failed to find {vpc_message}. "
                + "Network configuration cannot be inferred. "
                + "Pass an explicit `vpc_id`."
            )

        vpc_id = vpcs[0]["VpcId"]
        subnets = ec2_client.describe_subnets(
            Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
        )["Subnets"]

        if not subnets:
            raise ValueError(
                f"Failed to find subnets for {vpc_message}. "
                + "Network configuration cannot be inferred."
            )

        subnet_ids = [subnet["SubnetId"] for subnet in subnets]

        config_subnets = network_configuration.get("subnets", [])
        if not all(conf_sn in subnet_ids for conf_sn in config_subnets):
            raise ValueError(
                f"Subnets {config_subnets} not found within {vpc_message}."
                + "Please check that VPC is associated with supplied subnets."
            )

        return {"awsvpcConfiguration": network_configuration}

    def _prepare_task_run_request(
        self,
        configuration: ECSJobConfiguration,
        task_definition: dict[str, Any] | TaskDefinitionTypeDef,
        task_definition_arn: str,
        new_task_definition_registered: bool,
    ) -> dict:
        """
        Prepare a task run request payload.
        """
        task_run_request = deepcopy(configuration.task_run_request)

        task_run_request.setdefault("taskDefinition", task_definition_arn)

        assert task_run_request["taskDefinition"] == task_definition_arn, (
            f"Task definition ARN mismatch: {task_run_request['taskDefinition']!r} "
            f"!= {task_definition_arn!r}"
        )

        # Explicitly add cluster from configuration if set and not already in task_run_request
        # or if the value in task_run_request is empty/None
        # This ensures cluster is included even when template variables resolve to empty/None
        if configuration.cluster:
            existing_cluster = task_run_request.get("cluster")
            if not existing_cluster:
                task_run_request["cluster"] = configuration.cluster

        # Explicitly add launchType if missing or empty in task_run_request
        # This ensures launchType is included even when template variables resolve to empty/None
        # AWS expects camelCase "launchType" not snake_case "launch_type"
        # Default to FARGATE if not specified, which matches the default launch_type variable
        # Note: launchType may be removed later if capacityProviderStrategy is set
        # Exception: EC2 task definitions may omit launchType to use cluster capacity providers
        existing_launch_type = task_run_request.get("launchType")
        requires_ec2 = "EC2" in task_definition.get("requiresCompatibilities", [])
        if not existing_launch_type and not requires_ec2:
            # Default to FARGATE if launchType is missing, matching the default launch_type variable
            task_run_request["launchType"] = ECS_DEFAULT_LAUNCH_TYPE
        elif not existing_launch_type and requires_ec2:
            # EC2 task definitions may omit launchType to use cluster capacity providers
            # Ensure the key is removed entirely, not just set to None
            task_run_request.pop("launchType", None)

        capacityProviderStrategy = task_run_request.get("capacityProviderStrategy")

        if capacityProviderStrategy:
            # Should not be provided at all if capacityProviderStrategy is set, see https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_RunTask.html#ECS-RunTask-request-capacityProviderStrategy  # noqa
            self._logger.warning(
                "Found capacityProviderStrategy. "
                "Removing launchType from task run request."
            )
            task_run_request.pop("launchType", None)

        elif task_run_request.get("launchType") == "FARGATE_SPOT":
            # Should not be provided at all for FARGATE SPOT
            task_run_request.pop("launchType", None)

            # A capacity provider strategy is required for FARGATE SPOT
            task_run_request["capacityProviderStrategy"] = [
                {"capacityProvider": "FARGATE_SPOT", "weight": 1}
            ]
        overrides = task_run_request.get("overrides", {})
        container_overrides = overrides.get("containerOverrides", [])

        # Ensure the network configuration is present if using awsvpc for network mode
        if (
            task_definition.get("networkMode") == "awsvpc"
            and not task_run_request.get("networkConfiguration")
            and not configuration.network_configuration
        ):
            task_run_request["networkConfiguration"] = self._load_network_configuration(
                configuration.vpc_id, configuration
            )

        # Use networkConfiguration if supplied by user
        if (
            task_definition.get("networkMode") == "awsvpc"
            and configuration.network_configuration
            and configuration.vpc_id
        ):
            task_run_request["networkConfiguration"] = (
                self._custom_network_configuration(
                    configuration.vpc_id,
                    configuration.network_configuration,
                    configuration,
                )
            )

        # Ensure the container name is set if not provided at template time

        container_name = (
            configuration.container_name
            or _container_name_from_task_definition(task_definition)
            or ECS_DEFAULT_CONTAINER_NAME
        )

        if container_overrides and not container_overrides[0].get("name"):
            container_overrides[0]["name"] = container_name

        # Ensure configuration command is respected post-templating

        orchestration_container = _get_container(container_overrides, container_name)

        if orchestration_container:
            # Override the command if given on the configuration
            if configuration.command:
                orchestration_container["command"] = configuration.command

        # Clean up templated variable formatting

        for container in container_overrides:
            if isinstance(container.get("command"), str):
                container["command"] = shlex.split(container["command"])
            if isinstance(container.get("environment"), dict):
                container["environment"] = [
                    {"name": k, "value": v} for k, v in container["environment"].items()
                ]

            # Remove null values — they're not allowed by AWS
            container["environment"] = [
                item
                for item in container.get("environment", [])
                if item["value"] is not None
            ]

        if isinstance(task_run_request.get("tags"), dict):
            task_run_request["tags"] = [
                {"key": k, "value": v} for k, v in task_run_request["tags"].items()
            ]

        if overrides.get("cpu"):
            overrides["cpu"] = str(overrides["cpu"])

        if overrides.get("memory"):
            overrides["memory"] = str(overrides["memory"])

        # Ensure configuration tags and env are respected post-templating

        tags = [
            item
            for item in task_run_request.get("tags", [])
            if item["key"] not in configuration.labels.keys()
        ] + [
            {"key": k, "value": v}
            for k, v in configuration.labels.items()
            if v is not None
        ]

        # Slugify tags keys and values
        tags = [
            {
                "key": slugify(
                    item["key"],
                    regex_pattern=_TAG_REGEX,
                    allow_unicode=True,
                    lowercase=False,
                ),
                "value": slugify(
                    item["value"],
                    regex_pattern=_TAG_REGEX,
                    allow_unicode=True,
                    lowercase=False,
                ),
            }
            for item in tags
        ]
        if (
            new_task_definition_registered
            and configuration.auto_deregister_task_definition
        ):
            tags.append(
                {"key": "prefect.io/degregister-task-definition", "value": "true"}
            )

        if tags:
            task_run_request["tags"] = tags

        if orchestration_container:
            environment = [
                item
                for item in orchestration_container.get("environment", [])
                if item["name"] not in configuration.env.keys()
            ] + [
                {"name": k, "value": v}
                for k, v in configuration.env.items()
                if v is not None
            ]
            if environment:
                orchestration_container["environment"] = environment

        # Remove empty container overrides

        overrides["containerOverrides"] = [v for v in container_overrides if v]

        return task_run_request

    @retry(
        stop=stop_after_attempt(MAX_CREATE_TASK_RUN_ATTEMPTS),
        wait=wait_fixed(CREATE_TASK_RUN_MIN_DELAY_SECONDS)
        + wait_random(
            CREATE_TASK_RUN_MIN_DELAY_JITTER_SECONDS,
            CREATE_TASK_RUN_MAX_DELAY_JITTER_SECONDS,
        ),
        reraise=True,
    )
    def _create_task_run(self, ecs_client: "ECSClient", task_run_request: dict) -> str:
        """
        Create a run of a task definition.

        Returns the task run ARN.
        """
        task = ecs_client.run_task(**task_run_request)
        if task["failures"]:
            raise RuntimeError(
                f"Failed to run ECS task: {task['failures'][0]['reason']}"
            )
        elif not task["tasks"]:
            raise RuntimeError(
                "Failed to run ECS task: no tasks or failures were returned."
            )
        return task["tasks"][0]

    def _task_definitions_equal(
        self, taskdef_1, taskdef_2, logger: logging.Logger
    ) -> bool:
        """
        Compare two task definitions.

        Since one may come from the AWS API and have populated defaults, we do our best
        to homogenize the definitions without changing their meaning.
        """
        if taskdef_1 == taskdef_2:
            return True

        if taskdef_1 is None or taskdef_2 is None:
            return False

        taskdef_1 = copy.deepcopy(taskdef_1)
        taskdef_2 = copy.deepcopy(taskdef_2)

        for taskdef in (taskdef_1, taskdef_2):
            # Set defaults that AWS would set after registration
            container_definitions = taskdef.get("containerDefinitions", [])
            essential = any(
                container.get("essential") for container in container_definitions
            )
            if not essential:
                container_definitions[0].setdefault("essential", True)

            taskdef.setdefault("networkMode", "bridge")

            # Normalize ordering of lists that ECS considers unordered
            # ECS stores these in unordered data structures, so order shouldn't matter for comparison
            for container in container_definitions:
                # Sort environment variables by name for consistent comparison
                if "environment" in container:
                    container["environment"] = sorted(
                        container["environment"], key=lambda x: x.get("name", "")
                    )

                # Sort secrets by name for consistent comparison
                if "secrets" in container:
                    container["secrets"] = sorted(
                        container["secrets"], key=lambda x: x.get("name", "")
                    )

                # Sort environmentFiles by value as they don't have names
                if "environmentFiles" in container:
                    container["environmentFiles"] = sorted(
                        container["environmentFiles"], key=lambda x: x.get("value", "")
                    )

        _drop_empty_keys_from_dict(taskdef_1)
        _drop_empty_keys_from_dict(taskdef_2)

        # Clear fields that change on registration for comparison
        for field in ECS_POST_REGISTRATION_FIELDS:
            taskdef_1.pop(field, None)
            taskdef_2.pop(field, None)

        # Log differences between task definitions for debugging
        if taskdef_1 != taskdef_2:
            logger.debug(
                "The generated task definition and the retrieved task definition are not equal."
            )
            # Find and log differences in keys
            keys1 = set(taskdef_1.keys())
            keys2 = set(taskdef_2.keys())

            if keys1 != keys2:
                keys_only_in_1 = keys1 - keys2
                keys_only_in_2 = keys2 - keys1
                if keys_only_in_1:
                    logger.debug(
                        f"Keys only in generated task definition: {keys_only_in_1}"
                    )
                if keys_only_in_2:
                    logger.debug(
                        f"Keys only in retrieved task definition: {keys_only_in_2}"
                    )

            # Find and log differences in values for common keys
            common_keys = keys1.intersection(keys2)
            for key in common_keys:
                if taskdef_1[key] != taskdef_2[key]:
                    logger.debug(f"Value differs for key '{key}':")
                    logger.debug(f" Generated:  {taskdef_1[key]}")
                    logger.debug(f" Retrieved: {taskdef_2[key]}")

        return taskdef_1 == taskdef_2

    async def __aenter__(self) -> Self:
        await start_observer()
        return await super().__aenter__()

    async def __aexit__(self, *exc_info: Any) -> None:
        await stop_observer()
        return await super().__aexit__(*exc_info)

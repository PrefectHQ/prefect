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

import logging
from typing import Any, Dict, List, NamedTuple, Optional, Type, Union
from uuid import UUID

import anyio
import anyio.abc
import yaml
from pydantic import BaseModel, Field, model_validator
from typing_extensions import Literal, Self

from prefect.client.schemas.objects import FlowRun
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.workers.base import (
    BaseJobConfiguration,
    BaseVariables,
    BaseWorker,
    BaseWorkerResult,
)
from prefect_aws.credentials import AwsCredentials, ClientType
from prefect_aws.workers.ecs_worker.network import (
    custom_network_configuration,
    load_network_configuration,
)
from prefect_aws.workers.ecs_worker.task_definition import (
    get_or_register_task_definition,
    prepare_task_definition,
    retrieve_task_definition,
    validate_task_definition,
)
from prefect_aws.workers.ecs_worker.task_execution import (
    create_task_and_wait_for_start,
    create_task_run,
    prepare_task_run_request,
    watch_task_and_get_exit_code,
)
from prefect_aws.workers.ecs_worker.utils import (
    ECS_DEFAULT_FAMILY,
    ECS_DEFAULT_LAUNCH_TYPE,
)

# Internal type alias for ECS clients which are generated dynamically in botocore
_ECSClient = Any

_TASK_DEFINITION_CACHE: Dict[UUID, str] = {}


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


def parse_identifier(identifier: str) -> ECSIdentifier:
    """
    Splits identifier into its cluster and task components, e.g.
    input "cluster_name::task_arn" outputs ("cluster_name", "task_arn").
    """
    cluster, task = identifier.split("::", maxsplit=1)
    return ECSIdentifier(cluster, task)


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
    stream_output: Optional[bool] = Field(default=None)
    task_start_timeout_seconds: int = Field(default=300)
    task_watch_poll_interval: float = Field(default=5.0)
    auto_deregister_task_definition: bool = Field(default=False)
    vpc_id: Optional[str] = Field(default=None)
    container_name: Optional[str] = Field(default=None)
    cluster: Optional[str] = Field(default=None)
    match_latest_revision_in_family: bool = Field(default=False)

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
            from prefect_aws.workers.ecs_worker.utils import (
                _container_name_from_task_definition,
            )

            self.container_name = _container_name_from_task_definition(
                self.task_definition
            )

            # We may not have a name here still; for example if someone is using a task
            # definition arn. In that case, we'll perform similar logic later to find
            # the name to treat as the "orchestration" container.

        return self

    @model_validator(mode="after")
    def set_default_configure_cloudwatch_logs(self) -> Self:
        """
        Streaming output generally requires CloudWatch logs to be configured.

        To avoid entangled arguments in the simple case, `configure_cloudwatch_logs`
        defaults to matching the value of `stream_output`.
        """
        configure_cloudwatch_logs = self.configure_cloudwatch_logs
        if configure_cloudwatch_logs is None:
            self.configure_cloudwatch_logs = self.stream_output
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
            f"{1024} will be used unless present on the task definition."
        ),
    )
    memory: Optional[int] = Field(
        default=None,
        description=(
            "The amount of memory to provide to the ECS task. Valid amounts are "
            "specified in the AWS documentation. If not provided, a default value of "
            f"{2048} will be used unless present on the task definition."
        ),
    )
    container_name: Optional[str] = Field(
        default=None,
        description=(
            "The name of the container flow run orchestration will occur in. If not "
            f"specified, a default value of {'prefect'} will be used "
            "and if that is not found in the task definition the first container will "
            "be used."
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
            "logs:PutLogEvents permissions. The default for this field is `False` "
            "unless `stream_output` is set."
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

    stream_output: Optional[bool] = Field(
        default=None,
        description=(
            "If enabled, logs will be streamed from the Prefect container to the local "
            "console. Unless you have configured AWS CloudWatch logs manually on your "
            "task definition, this requires the same prerequisites outlined in "
            "`configure_cloudwatch_logs`."
        ),
    )
    task_start_timeout_seconds: int = Field(
        default=300,
        description=(
            "The amount of time to watch for the start of the ECS task "
            "before marking it as failed. The task must enter a RUNNING state to be "
            "considered started."
        ),
    )
    task_watch_poll_interval: float = Field(
        default=5.0,
        description=(
            "The amount of time to wait between AWS API calls while monitoring the "
            "state of an ECS task."
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


class ECSWorker(BaseWorker):
    """
    A Prefect worker to run flow runs as ECS tasks.
    """

    type: str = "ecs"
    job_configuration: Type[ECSJobConfiguration] = ECSJobConfiguration
    job_configuration_variables: Type[ECSVariables] = ECSVariables
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
            self._get_client, configuration, "ecs"
        )

        logger = self.get_flow_run_logger(flow_run)

        await run_sync_in_worker_thread(
            self._create_task_and_wait_for_start,
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
            self._get_client, configuration, "ecs"
        )

        logger = self.get_flow_run_logger(flow_run)

        (
            task_arn,
            cluster_arn,
            task_definition,
            is_new_task_definition,
        ) = await run_sync_in_worker_thread(
            self._create_task_and_wait_for_start,
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

        status_code = await run_sync_in_worker_thread(
            self._watch_task_and_get_exit_code,
            logger,
            configuration,
            task_arn,
            cluster_arn,
            task_definition,
            is_new_task_definition and configuration.auto_deregister_task_definition,
            ecs_client,
        )

        return ECSWorkerResult(
            identifier=identifier,
            # If the container does not start the exit code can be null but we must
            # still report a status code. We use a -1 to indicate a special code.
            status_code=status_code if status_code is not None else -1,
        )

    def _get_client(
        self, configuration: ECSJobConfiguration, client_type: Union[str, ClientType]
    ) -> _ECSClient:
        """
        Get a boto3 client of client_type. Will use a cached client if one exists.
        """
        return configuration.aws_credentials.get_client(client_type)

    def _create_task_and_wait_for_start(
        self,
        logger: logging.Logger,
        ecs_client: _ECSClient,
        configuration: ECSJobConfiguration,
        flow_run: FlowRun,
    ) -> tuple[str, str, dict, bool]:
        """
        Register the task definition, create the task run, and wait for it to start.

        Returns a tuple of
        - The task ARN
        - The task's cluster ARN
        - The task definition
        - A bool indicating if the task definition is newly registered
        """
        return create_task_and_wait_for_start(
            logger=logger,
            ecs_client=ecs_client,
            configuration=configuration,
            flow_run=flow_run,
            task_definition_cache=_TASK_DEFINITION_CACHE,
            get_or_register_task_definition_func=get_or_register_task_definition,
            prepare_task_definition_func=lambda config,
            region,
            flow_run: prepare_task_definition(
                config, region, flow_run, self._work_pool_name
            ),
            retrieve_task_definition_func=retrieve_task_definition,
            validate_task_definition_func=validate_task_definition,
            prepare_task_run_request_func=prepare_task_run_request,
            load_network_configuration_func=load_network_configuration,
            custom_network_configuration_func=custom_network_configuration,
            get_client_func=self._get_client,
            work_pool=self.work_pool,
            create_task_run_func=self._create_task_run,
        )

    def _watch_task_and_get_exit_code(
        self,
        logger: logging.Logger,
        configuration: ECSJobConfiguration,
        task_arn: str,
        cluster_arn: str,
        task_definition: dict,
        deregister_task_definition: bool,
        ecs_client: _ECSClient,
    ) -> Optional[int]:
        """
        Wait for the task run to complete and retrieve the exit code of the Prefect
        container.
        """
        logs_client = None
        if configuration.stream_output:
            logs_client = self._get_client(configuration, "logs")

        return watch_task_and_get_exit_code(
            logger=logger,
            configuration=configuration,
            task_arn=task_arn,
            cluster_arn=cluster_arn,
            task_definition=task_definition,
            deregister_task_definition=deregister_task_definition,
            ecs_client=ecs_client,
            logs_client=logs_client,
        )

    def _create_task_run(self, ecs_client: _ECSClient, task_run_request: dict):
        """
        Create a run of a task definition.

        Returns the task run.
        """
        # Call the function from task_execution module
        return create_task_run(ecs_client, task_run_request)

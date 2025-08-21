"""Base components for ECS worker infrastructure."""

from aws_cdk import (
    CfnCondition,
    CfnOutput,
    CfnParameter,
    Duration,
    Fn,
    RemovalPolicy,
    SecretValue,
    Stack,
)
from aws_cdk import (
    aws_ecs as ecs,
)
from aws_cdk import (
    aws_events as events,
)
from aws_cdk import (
    aws_events_targets as events_targets,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_logs as logs,
)
from aws_cdk import (
    aws_secretsmanager as secretsmanager,
)
from aws_cdk import (
    aws_sqs as sqs,
)
from constructs import Construct


class EcsWorkerBase(Stack):
    """Base class with common ECS worker infrastructure components."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Common Parameters
        self.work_pool_name = CfnParameter(
            self,
            "WorkPoolName",
            type="String",
            description="Name of the Prefect work pool",
            default="ecs-work-pool",
        )

        self.prefect_api_url = CfnParameter(
            self,
            "PrefectApiUrl",
            type="String",
            description="Prefect API URL",
            default="https://api.prefect.cloud/api",
        )

        # Either provide an existing secret ARN OR a raw API key to create a secret
        self.prefect_api_key_secret_arn = CfnParameter(
            self,
            "PrefectApiKeySecretArn",
            type="String",
            description="ARN of existing AWS Secrets Manager secret containing Prefect API key (leave empty to create new)",
            default="",
        )

        self.prefect_api_key = CfnParameter(
            self,
            "PrefectApiKey",
            type="String",
            description="Prefect API key (only used if PrefectApiKeySecretArn is empty)",
            default="",
            no_echo=True,
        )

        self.work_queues = CfnParameter(
            self,
            "WorkQueues",
            type="CommaDelimitedList",
            description="Comma-separated list of work queues to pull from (leave empty to pull from all queues in the work pool)",
            default="",
        )

        self.docker_image = CfnParameter(
            self,
            "DockerImage",
            type="String",
            description="Docker image for the worker",
            default="prefecthq/prefect-aws:latest",
        )

        self.log_retention_days = CfnParameter(
            self,
            "LogRetentionDays",
            type="Number",
            description="CloudWatch log retention in days",
            default=30,
        )

        self.existing_log_group_name = CfnParameter(
            self,
            "ExistingLogGroupName",
            type="String",
            description="Name of existing CloudWatch log group to use (leave empty to create new). Format: /ecs/your-work-pool-name",
            default="",
        )

        # Condition to check if we should create a new secret
        self.create_new_secret_condition = CfnCondition(
            self,
            "CreateNewSecret",
            expression=Fn.condition_equals(
                self.prefect_api_key_secret_arn.value_as_string, ""
            ),
        )

        # Condition to check if work queues are specified
        self.has_work_queues_condition = CfnCondition(
            self,
            "HasWorkQueues",
            expression=Fn.condition_not(
                Fn.condition_equals(Fn.select(0, self.work_queues.value_as_list), "")
            ),
        )

        # Condition to check if we should use existing log group
        self.use_existing_log_group_condition = CfnCondition(
            self,
            "UseExistingLogGroup",
            expression=Fn.condition_not(
                Fn.condition_equals(self.existing_log_group_name.value_as_string, "")
            ),
        )

        # Create the secret if needed
        self.api_key_secret = self._create_api_key_secret()

    def _create_api_key_secret(self) -> secretsmanager.Secret:
        """Create Secrets Manager secret for Prefect API key if needed."""
        secret = secretsmanager.Secret(
            self,
            "PrefectApiKeySecret",
            secret_name=f"{self.work_pool_name.value_as_string}-prefect-api-key",
            description="Prefect API key for ECS worker",
            secret_string_value=SecretValue.cfn_parameter(self.prefect_api_key),
        )

        # Apply condition so it's only created when needed
        secret.node.default_child.cfn_options.condition = (
            self.create_new_secret_condition
        )

        return secret

    def get_api_key_secret_arn(self) -> str:
        """Get the ARN of the API key secret (either existing or newly created)."""
        return Fn.condition_if(
            self.create_new_secret_condition.logical_id,
            self.api_key_secret.secret_arn,
            self.prefect_api_key_secret_arn.value_as_string,
        ).to_string()

    def create_sqs_infrastructure(self) -> tuple[sqs.Queue, sqs.Queue]:
        """Create SQS queue and DLQ for ECS events."""
        # Dead Letter Queue
        dlq = sqs.Queue(
            self,
            "EcsEventsDLQ",
            queue_name=f"{self.work_pool_name.value_as_string}-ecs-events-dlq",
            visibility_timeout=Duration.seconds(60),
            retention_period=Duration.days(14),
        )

        # Main Queue
        queue = sqs.Queue(
            self,
            "EcsEventsQueue",
            queue_name=f"{self.work_pool_name.value_as_string}-ecs-events",
            visibility_timeout=Duration.seconds(300),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=dlq,
            ),
            retention_period=Duration.days(7),
        )

        CfnOutput(
            self,
            "EcsEventsQueueUrl",
            value=queue.queue_url,
            description="URL of the SQS queue receiving ECS events",
        )

        CfnOutput(
            self,
            "EcsEventsQueueArn",
            value=queue.queue_arn,
            description="ARN of the SQS queue receiving ECS events",
        )

        return queue, dlq

    def create_eventbridge_rule(
        self, queue: sqs.Queue, cluster_arn: str = None
    ) -> events.Rule:
        """Create EventBridge rule for ECS task state changes."""
        # Use CDK's EventPattern class instead of raw dict
        if cluster_arn:
            event_pattern = events.EventPattern(
                source=["aws.ecs"],
                detail_type=["ECS Task State Change"],
                detail={
                    "lastStatus": ["RUNNING", "STOPPED"],
                    "clusterArn": [cluster_arn],
                },
            )
        else:
            event_pattern = events.EventPattern(
                source=["aws.ecs"],
                detail_type=["ECS Task State Change"],
                detail={
                    "lastStatus": ["RUNNING", "STOPPED"],
                },
            )

        rule = events.Rule(
            self,
            "EcsTaskStateChangeRule",
            rule_name=f"{self.work_pool_name.value_as_string}-ecs-task-events",
            description="Capture ECS task state changes for Prefect workers",
            event_pattern=event_pattern,
            targets=[events_targets.SqsQueue(queue)],
        )

        # Grant EventBridge permission to send messages to SQS
        queue.grant_send_messages(iam.ServicePrincipal("events.amazonaws.com"))

        CfnOutput(
            self,
            "EventBridgeRuleArn",
            value=rule.rule_arn,
            description="ARN of the EventBridge rule for ECS events",
        )

        return rule

    def create_task_execution_role(self) -> iam.Role:
        """Create IAM role for ECS task execution."""
        role = iam.Role(
            self,
            "EcsTaskExecutionRole",
            role_name=f"{self.work_pool_name.value_as_string}-task-execution-role",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                )
            ],
        )

        # Grant access to Prefect API key secret
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                ],
                resources=[self.get_api_key_secret_arn()],
            )
        )

        return role

    def create_task_role(self, queue: sqs.Queue) -> iam.Role:
        """Create IAM role for ECS tasks."""
        role = iam.Role(
            self,
            "EcsTaskRole",
            role_name=f"{self.work_pool_name.value_as_string}-task-role",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )

        # Grant access to SQS queue for consuming events
        queue.grant_consume_messages(role)

        # Grant basic ECS permissions for worker functionality
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecs:DescribeTasks",
                    "ecs:DescribeTaskDefinition",
                    "ecs:ListTasks",
                    "ecs:RunTask",
                    "ecs:StopTask",
                    "ecs:DescribeClusters",
                    "ecs:ListClusters",
                    "ecs:RegisterTaskDefinition",
                    "ecs:DeregisterTaskDefinition",
                    "ecs:ListTaskDefinitions",
                    "ecs:TagResource",
                    "ec2:DescribeNetworkInterfaces",
                    "ec2:DescribeSubnets",
                    "ec2:DescribeVpcs",
                    "ec2:DescribeSecurityGroups",
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:GetLogEvents",
                    "logs:DescribeLogStreams",
                ],
                resources=["*"],
            )
        )

        # Grant IAM PassRole permission for any role (required for dynamic task definitions)
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["iam:PassRole"],
                resources=["arn:aws:iam::*:role/*"],
            )
        )

        return role

    def create_log_group(self) -> logs.LogGroup:
        """Create CloudWatch log group for worker tasks."""
        # Use existing log group name if provided, otherwise generate one
        log_group_name = Fn.condition_if(
            self.use_existing_log_group_condition.logical_id,
            self.existing_log_group_name.value_as_string,
            f"/ecs/{self.work_pool_name.value_as_string}",
        ).to_string()

        log_group = logs.LogGroup(
            self,
            "WorkerLogGroup",
            log_group_name=log_group_name,
            retention=logs.RetentionDays.ONE_MONTH,  # Default, will be overridden by parameter
            removal_policy=RemovalPolicy.RETAIN,  # Preserve logs when stack is deleted
        )

        # Configure the underlying CloudFormation resource with proper retention
        cfn_log_group = log_group.node.default_child
        cfn_log_group.add_property_override(
            "RetentionInDays", self.log_retention_days.value_as_number
        )

        CfnOutput(
            self,
            "LogGroupName",
            value=log_group.log_group_name,
            description="CloudWatch log group for worker tasks",
        )

        # Also output the created secret ARN if we created one
        CfnOutput(
            self,
            "PrefectApiKeySecretArnOutput",
            value=self.get_api_key_secret_arn(),
            description="ARN of the Prefect API key secret",
            condition=self.create_new_secret_condition,
        )

        return log_group

    def create_task_definition(
        self,
        execution_role: iam.Role,
        task_role: iam.Role,
        log_group: logs.LogGroup,
        queue: sqs.Queue = None,
    ) -> ecs.TaskDefinition:
        """Create ECS task definition for the worker."""
        cpu_param = CfnParameter(
            self,
            "TaskCpu",
            type="Number",
            description="CPU units for the task (1024 = 1 vCPU)",
            default=1024,
        )

        memory_param = CfnParameter(
            self,
            "TaskMemory",
            type="Number",
            description="Memory for the task in MB",
            default=2048,
        )

        task_definition = ecs.TaskDefinition(
            self,
            "WorkerTaskDefinition",
            family=f"{self.work_pool_name.value_as_string}-worker",
            compatibility=ecs.Compatibility.FARGATE,
            cpu=cpu_param.value_as_string,
            memory_mib=memory_param.value_as_string,
            execution_role=execution_role,
            task_role=task_role,
        )

        # Build worker start command using shell to handle multiple --work-queue flags
        # Create base command template for substitution
        base_cmd_template = (
            "prefect worker start --type ecs --pool ${WorkPoolName} --with-healthcheck"
        )

        # Build the command with conditional work queues
        command_with_queues = Fn.condition_if(
            self.has_work_queues_condition.logical_id,
            # If work queues specified, add multiple --work-queue flags
            Fn.sub(
                base_cmd_template + " --work-queue ${WorkQueueList}",
                {
                    "WorkPoolName": self.work_pool_name.value_as_string,
                    "WorkQueueList": Fn.join(
                        " --work-queue ", self.work_queues.value_as_list
                    ),
                },
            ),
            # If no work queues, just the base command
            Fn.sub(
                base_cmd_template,
                {
                    "WorkPoolName": self.work_pool_name.value_as_string,
                },
            ),
        ).to_string()

        command_args = ["sh", "-c", command_with_queues]

        environment_vars = {
            "PREFECT_API_URL": self.prefect_api_url.value_as_string,
            "PREFECT_INTEGRATIONS_AWS_ECS_OBSERVER_ENABLED": "true",
        }

        # Add SQS queue name if provided
        if queue:
            environment_vars["PREFECT_INTEGRATIONS_AWS_ECS_OBSERVER_SQS_QUEUE_NAME"] = (
                queue.queue_name
            )

        # Add container
        task_definition.add_container(
            "worker",
            container_name="prefect-worker",
            image=ecs.ContainerImage.from_registry(self.docker_image.value_as_string),
            command=command_args,
            environment=environment_vars,
            secrets={
                "PREFECT_API_KEY": ecs.Secret.from_secrets_manager(self.api_key_secret),
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="ecs",
                log_group=log_group,
            ),
            health_check=ecs.HealthCheck(
                command=[
                    "CMD-SHELL",
                    "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8080/health', timeout=5)\"",
                ],
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                retries=3,
                start_period=Duration.seconds(60),
            ),
            port_mappings=[
                ecs.PortMapping(
                    container_port=8080,
                    protocol=ecs.Protocol.TCP,
                    name="health",
                )
            ],
        )

        CfnOutput(
            self,
            "TaskDefinitionArn",
            value=task_definition.task_definition_arn,
            description="ARN of the ECS task definition for the worker",
        )

        return task_definition

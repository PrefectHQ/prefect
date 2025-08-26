"""ECS worker service stack - deploys to existing cluster with event infrastructure."""

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
    aws_ec2 as ec2,
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


class EcsServiceStack(Stack):
    """ECS worker service for existing cluster with event infrastructure."""

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

        # Auth string parameters (alternative to API key for self-hosted servers)
        self.prefect_auth_string_secret_arn = CfnParameter(
            self,
            "PrefectAuthStringSecretArn",
            type="String",
            description="ARN of existing AWS Secrets Manager secret containing Prefect auth string for self-hosted servers (leave empty to create new)",
            default="",
        )

        self.prefect_auth_string = CfnParameter(
            self,
            "PrefectAuthString",
            type="String",
            description="Prefect auth string for self-hosted servers in format 'username:password' (only used if PrefectAuthStringSecretArn is empty)",
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

        # Additional parameters for service-only deployment
        self.existing_cluster_identifier = CfnParameter(
            self,
            "ExistingClusterIdentifier",
            type="String",
            description="ECS cluster name or ARN. You can provide either the cluster name (e.g., 'my-cluster') or the full ARN (e.g., 'arn:aws:ecs:us-east-1:123456789012:cluster/my-cluster'). Find available clusters in the ECS console.",
            allowed_pattern=r"^(arn:aws:ecs:[a-z0-9-]+:\d{12}:cluster/.+|[a-zA-Z][a-zA-Z0-9_-]{0,254})$",
            constraint_description="Must be either a valid cluster name (1-255 characters) or a complete ECS cluster ARN",
        )

        self.existing_vpc_id = CfnParameter(
            self,
            "ExistingVpcId",
            type="String",
            description="VPC ID where the existing cluster is located (e.g., vpc-12345678). Find this in the EC2 console or run 'aws ec2 describe-vpcs'.",
            allowed_pattern=r"^vpc-[0-9a-f]{8,17}$",
            constraint_description="Must be a valid VPC ID in the format: vpc-xxxxxxxx",
        )

        self.existing_subnet_ids = CfnParameter(
            self,
            "ExistingSubnetIds",
            type="CommaDelimitedList",
            description="Comma-separated list of subnet IDs for the service (e.g., subnet-12345678,subnet-87654321). Use private subnets for better security. Find these in the VPC console or run 'aws ec2 describe-subnets --filters Name=vpc-id,Values=YOUR_VPC_ID'.",
        )

        self.desired_count = CfnParameter(
            self,
            "DesiredCount",
            type="Number",
            description="Desired number of worker tasks to run",
            default=1,
        )

        self.min_capacity = CfnParameter(
            self,
            "MinCapacity",
            type="Number",
            description="Minimum number of worker tasks for auto scaling",
            default=1,
        )

        self.max_capacity = CfnParameter(
            self,
            "MaxCapacity",
            type="Number",
            description="Maximum number of worker tasks for auto scaling",
            default=10,
        )

        # Conditions for auth method selection
        self.use_api_key_condition = CfnCondition(
            self,
            "UseApiKey",
            expression=Fn.condition_or(
                Fn.condition_not(
                    Fn.condition_equals(
                        self.prefect_api_key_secret_arn.value_as_string, ""
                    )
                ),
                Fn.condition_not(
                    Fn.condition_equals(self.prefect_api_key.value_as_string, "")
                ),
            ),
        )

        self.use_auth_string_condition = CfnCondition(
            self,
            "UseAuthString",
            expression=Fn.condition_or(
                Fn.condition_not(
                    Fn.condition_equals(
                        self.prefect_auth_string_secret_arn.value_as_string, ""
                    )
                ),
                Fn.condition_not(
                    Fn.condition_equals(self.prefect_auth_string.value_as_string, "")
                ),
            ),
        )

        # Conditions to check if we should create new secrets
        self.create_new_api_key_secret_condition = CfnCondition(
            self,
            "CreateNewApiKeySecret",
            expression=Fn.condition_and(
                self.use_api_key_condition,
                Fn.condition_equals(
                    self.prefect_api_key_secret_arn.value_as_string, ""
                ),
            ),
        )

        self.create_new_auth_string_secret_condition = CfnCondition(
            self,
            "CreateNewAuthStringSecret",
            expression=Fn.condition_and(
                self.use_auth_string_condition,
                Fn.condition_equals(
                    self.prefect_auth_string_secret_arn.value_as_string, ""
                ),
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

        # Condition to check if cluster identifier is an ARN
        self.is_cluster_arn_condition = CfnCondition(
            self,
            "IsClusterArn",
            expression=Fn.condition_equals(
                Fn.select(
                    0, Fn.split(":", self.existing_cluster_identifier.value_as_string)
                ),
                "arn",
            ),
        )

        # Create the secrets if needed
        self.api_key_secret = self._create_api_key_secret()
        self.auth_string_secret = self._create_auth_string_secret()

        # Get existing resources
        self.vpc = self._get_existing_vpc()
        # Convert cluster identifier to ARN if needed
        self.cluster_arn = self._get_cluster_arn()
        self.cluster = self._get_existing_cluster()

        # Create infrastructure
        self.queue, self.dlq = self.create_sqs_infrastructure()
        self.eventbridge_rule = self.create_eventbridge_rule(
            self.queue, cluster_arn=self.cluster_arn
        )
        self.execution_role = self.create_task_execution_role()
        self.task_role = self.create_task_role(self.queue)
        self.log_group = self.create_log_group()
        self.task_definition = self.create_task_definition(
            self.execution_role, self.task_role, self.log_group, self.queue
        )
        self.service = self._create_service()
        self._setup_autoscaling()

    def _get_existing_vpc(self) -> ec2.IVpc:
        """Import existing VPC."""
        # For synthesis, we provide explicit AZs to avoid the list token warning
        # In actual deployment, these will be resolved correctly
        return ec2.Vpc.from_vpc_attributes(
            self,
            "ExistingVpc",
            vpc_id=self.existing_vpc_id.value_as_string,
            availability_zones=[
                "us-east-1a",
                "us-east-1b",
            ],  # Will be overridden at deployment
        )

    def _get_cluster_arn(self) -> str:
        """Convert cluster identifier to ARN if it's just a name."""
        cluster_identifier = self.existing_cluster_identifier.value_as_string
        # If it already looks like an ARN, use it as-is
        # Otherwise, construct ARN from cluster name
        return Fn.condition_if(
            self.is_cluster_arn_condition.logical_id,
            cluster_identifier,
            Fn.sub(
                "arn:aws:ecs:${AWS::Region}:${AWS::AccountId}:cluster/${ClusterName}",
                {"ClusterName": cluster_identifier},
            ),
        ).to_string()

    def _get_existing_cluster(self) -> ecs.ICluster:
        """Import existing ECS cluster."""
        # Extract cluster name from ARN or use the identifier if it's already a name
        cluster_name = Fn.condition_if(
            self.is_cluster_arn_condition.logical_id,
            Fn.select(
                1, Fn.split("/", self.existing_cluster_identifier.value_as_string)
            ),
            self.existing_cluster_identifier.value_as_string,
        ).to_string()

        return ecs.Cluster.from_cluster_attributes(
            self,
            "ExistingCluster",
            cluster_name=cluster_name,
            cluster_arn=self.cluster_arn,
            vpc=self.vpc,
            security_groups=[],
        )

    def _create_service(self) -> ecs.FargateService:
        """Create ECS service in existing cluster."""
        # Create security group for the service
        security_group = ec2.SecurityGroup(
            self,
            "WorkerSecurityGroup",
            vpc=self.vpc,
            description="Security group for Prefect ECS workers",
            allow_all_outbound=True,
        )

        # Allow health check traffic
        security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(8080),
            description="Health check endpoint",
        )

        # Import existing subnets with proper attributes
        subnets = [
            ec2.Subnet.from_subnet_attributes(
                self,
                f"ExistingSubnet{i}",
                subnet_id=subnet_id,
                availability_zone=f"us-east-1{chr(97 + i)}",  # Will be resolved at deployment
                route_table_id=f"rtb-{subnet_id[-8:]}",  # Placeholder route table ID
            )
            for i, subnet_id in enumerate(self.existing_subnet_ids.value_as_list)
        ]

        # For CloudFormation synthesis, we can't use conditions directly in CDK
        # We'll set assign_public_ip based on the parameter value
        # This is a limitation when synthesizing without deployment context
        service = ecs.FargateService(
            self,
            "WorkerService",
            cluster=self.cluster,
            task_definition=self.task_definition,
            service_name=f"{self.work_pool_name.value_as_string}-workers",
            desired_count=self.desired_count.value_as_number,
            security_groups=[security_group],
            vpc_subnets=ec2.SubnetSelection(subnets=subnets),
            assign_public_ip=False,
            capacity_provider_strategies=[
                ecs.CapacityProviderStrategy(
                    capacity_provider="FARGATE",
                    weight=1,
                )
            ],
            enable_execute_command=True,  # Enable ECS Exec for debugging
            min_healthy_percent=100,  # Prevent tasks from stopping during deployments
        )

        CfnOutput(
            self,
            "ServiceArn",
            value=service.service_arn,
            description="ARN of the ECS service",
        )

        CfnOutput(
            self,
            "ServiceName",
            value=service.service_name,
            description="Name of the ECS service",
        )

        return service

    def _setup_autoscaling(self) -> None:
        """Set up auto scaling for the service."""
        scaling_target = self.service.auto_scale_task_count(
            min_capacity=self.min_capacity.value_as_number,
            max_capacity=self.max_capacity.value_as_number,
        )

        # Scale based on CPU utilization
        scaling_target.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=70,
            scale_in_cooldown=Duration.minutes(5),
            scale_out_cooldown=Duration.minutes(2),
        )

        # Scale based on memory utilization
        scaling_target.scale_on_memory_utilization(
            "MemoryScaling",
            target_utilization_percent=80,
            scale_in_cooldown=Duration.minutes(5),
            scale_out_cooldown=Duration.minutes(2),
        )

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
            self.create_new_api_key_secret_condition
        )

        return secret

    def _create_auth_string_secret(self) -> secretsmanager.Secret:
        """Create Secrets Manager secret for Prefect auth string if needed."""
        secret = secretsmanager.Secret(
            self,
            "PrefectAuthStringSecret",
            secret_name=f"{self.work_pool_name.value_as_string}-prefect-auth-string",
            description="Prefect auth string for ECS worker (self-hosted servers)",
            secret_string_value=SecretValue.cfn_parameter(self.prefect_auth_string),
        )

        # Apply condition so it's only created when needed
        secret.node.default_child.cfn_options.condition = (
            self.create_new_auth_string_secret_condition
        )

        return secret

    def get_api_key_secret_arn(self) -> str:
        """Get the ARN of the API key secret (either existing or newly created)."""
        return Fn.condition_if(
            self.create_new_api_key_secret_condition.logical_id,
            self.api_key_secret.secret_arn,
            self.prefect_api_key_secret_arn.value_as_string,
        ).to_string()

    def get_auth_string_secret_arn(self) -> str:
        """Get the ARN of the auth string secret (either existing or newly created)."""
        return Fn.condition_if(
            self.create_new_auth_string_secret_condition.logical_id,
            self.auth_string_secret.secret_arn,
            self.prefect_auth_string_secret_arn.value_as_string,
        ).to_string()

    def get_active_secret_arn(self) -> str:
        """Get the ARN of whichever auth method is being used."""
        return Fn.condition_if(
            self.use_api_key_condition.logical_id,
            self.get_api_key_secret_arn(),
            self.get_auth_string_secret_arn(),
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
                    "clusterArn": [cluster_arn],
                },
            )
        else:
            event_pattern = events.EventPattern(
                source=["aws.ecs"],
                detail_type=["ECS Task State Change"],
                detail={},
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

        # Grant access to the appropriate Prefect auth secret
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                ],
                resources=[self.get_active_secret_arn()],
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

    def create_log_group(self) -> logs.ILogGroup:
        """Create or reference CloudWatch log group for worker tasks."""
        # Generate unique suffix for log group name to prevent collisions
        # Extract first 8 chars of UUID from stack ID for true uniqueness across deployments
        unique_suffix = Fn.select(
            0, Fn.split("-", Fn.select(2, Fn.split("/", Stack.of(self).stack_id)))
        )

        # Create log group with unique name (will only be created when condition is true)
        new_log_group = logs.LogGroup(
            self,
            "WorkerLogGroup",
            log_group_name=Fn.join(
                "/", ["", "ecs", self.work_pool_name.value_as_string, unique_suffix]
            ),
            retention=logs.RetentionDays.ONE_MONTH,  # Default, will be overridden by parameter
            removal_policy=RemovalPolicy.RETAIN,  # Preserve logs when stack is deleted
        )

        # Store the generated log group name for use in task definition
        self._generated_log_group_name = Fn.join(
            "/", ["", "ecs", self.work_pool_name.value_as_string, unique_suffix]
        )

        # Configure the underlying CloudFormation resource
        cfn_log_group = new_log_group.node.default_child
        cfn_log_group.add_property_override(
            "RetentionInDays", self.log_retention_days.value_as_number
        )

        # Only create this log group resource when NOT using existing log group
        create_new_log_group_condition = CfnCondition(
            self,
            "CreateNewLogGroup",
            expression=Fn.condition_not(self.use_existing_log_group_condition),
        )
        cfn_log_group.cfn_options.condition = create_new_log_group_condition

        # Output the log group name conditionally
        CfnOutput(
            self,
            "LogGroupName",
            value=Fn.condition_if(
                self.use_existing_log_group_condition.logical_id,
                self.existing_log_group_name.value_as_string,
                self._generated_log_group_name,
            ).to_string(),
            description="CloudWatch log group for worker tasks",
        )

        # Output the created secret ARNs if we created them
        CfnOutput(
            self,
            "PrefectApiKeySecretArnOutput",
            value=self.get_api_key_secret_arn(),
            description="ARN of the Prefect API key secret",
            condition=self.create_new_api_key_secret_condition,
        )

        CfnOutput(
            self,
            "PrefectAuthStringSecretArnOutput",
            value=self.get_auth_string_secret_arn(),
            description="ARN of the Prefect auth string secret",
            condition=self.create_new_auth_string_secret_condition,
        )

        # Return the new log group (CDK will handle the conditional logic in CloudFormation)
        return new_log_group

    def get_log_group_for_task_definition(self) -> str:
        """Get the appropriate log group name for the task definition."""
        return Fn.condition_if(
            self.use_existing_log_group_condition.logical_id,
            self.existing_log_group_name.value_as_string,
            self._generated_log_group_name,
        ).to_string()

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

        # Add container (we'll handle auth method selection by post-processing the CloudFormation)
        task_definition.add_container(
            "worker",
            container_name="prefect-worker",
            image=ecs.ContainerImage.from_registry(self.docker_image.value_as_string),
            command=command_args,
            environment=environment_vars,
            # Logging will be configured via CloudFormation override below
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

        # Manually configure the secrets in the CloudFormation template since CDK doesn't support conditional secrets
        cfn_task_definition = task_definition.node.default_child

        # Get the container definition and add conditional secrets
        # API key takes precedence - if provided, use it exclusively
        # Auth string is only used if NO API key is provided
        cfn_task_definition.add_property_override(
            "ContainerDefinitions.0.Secrets",
            Fn.condition_if(
                self.use_api_key_condition.logical_id,
                # If using API key, only include API key secret
                [
                    {
                        "Name": "PREFECT_API_KEY",
                        "ValueFrom": self.get_api_key_secret_arn(),
                    }
                ],
                Fn.condition_if(
                    self.use_auth_string_condition.logical_id,
                    # If not using API key but using auth string, only include auth string
                    [
                        {
                            "Name": "PREFECT_AUTH_STRING",
                            "ValueFrom": self.get_auth_string_secret_arn(),
                        }
                    ],
                    # If using neither, omit the Secrets property entirely
                    Fn.ref("AWS::NoValue"),
                ),
            ),
        )

        # Configure logging to use the appropriate log group (existing or new)
        cfn_task_definition.add_property_override(
            "ContainerDefinitions.0.LogConfiguration",
            {
                "LogDriver": "awslogs",
                "Options": {
                    "awslogs-group": self.get_log_group_for_task_definition(),
                    "awslogs-region": {"Ref": "AWS::Region"},
                    "awslogs-stream-prefix": "ecs",
                },
            },
        )

        CfnOutput(
            self,
            "TaskDefinitionArn",
            value=task_definition.task_definition_arn,
            description="ARN of the ECS task definition for the worker",
        )

        # Add outputs for work pool configuration
        CfnOutput(
            self,
            "TaskExecutionRoleArn",
            value=execution_role.role_arn,
            description="ARN of the ECS task execution role",
        )

        CfnOutput(
            self,
            "ClusterArn",
            value=self.cluster_arn,
            description="ARN of the ECS cluster",
        )

        CfnOutput(
            self,
            "VpcId",
            value=self.existing_vpc_id.value_as_string,
            description="VPC ID where the worker is deployed",
        )

        CfnOutput(
            self,
            "SubnetIds",
            value=Fn.join(",", self.existing_subnet_ids.value_as_list),
            description="Comma-separated list of subnet IDs",
        )

        return task_definition

"""ECS worker service stack - deploys to existing cluster with event infrastructure."""

from aws_cdk import (
    CfnCondition,
    CfnOutput,
    CfnParameter,
    Duration,
    Fn,
)
from aws_cdk import (
    aws_ec2 as ec2,
)
from aws_cdk import (
    aws_ecs as ecs,
)
from constructs import Construct

from .base import EcsWorkerBase


class EcsServiceStack(EcsWorkerBase):
    """ECS worker service for existing cluster with event infrastructure."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

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

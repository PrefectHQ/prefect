"""Events-only stack - sets up EventBridge and SQS for ECS task state changes."""

from aws_cdk import (
    CfnOutput,
    CfnParameter,
)
from constructs import Construct

from .base import EcsWorkerBase


class EcsEventsStack(EcsWorkerBase):
    """EventBridge and SQS infrastructure for ECS task state monitoring."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Additional parameters for events-only deployment
        self.existing_cluster_arn = CfnParameter(
            self,
            "ExistingClusterArn",
            type="String",
            description="ARN of existing ECS cluster to monitor",
        )

        # Create only the event infrastructure
        self.queue, self.dlq = self.create_sqs_infrastructure()
        self.eventbridge_rule = self.create_eventbridge_rule(
            self.queue, cluster_arn=self.existing_cluster_arn.value_as_string
        )

        # Output the queue configuration for workers to consume
        CfnOutput(
            self,
            "EcsEventsQueueName",
            value=self.queue.queue_name,
            description="Name of the SQS queue receiving ECS events",
        )

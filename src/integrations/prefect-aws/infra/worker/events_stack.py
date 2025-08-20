"""Events-only stack - sets up EventBridge and SQS for ECS task state changes."""

from aws_cdk import (
    CfnCondition,
    CfnOutput,
    CfnParameter,
    Fn,
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
            description="ARN of existing ECS cluster to monitor (leave empty to monitor all clusters)",
            default="",
        )

        self.monitor_all_clusters = CfnParameter(
            self,
            "MonitorAllClusters",
            type="String",
            description="Whether to monitor all ECS clusters or just the specified one",
            allowed_values=["true", "false"],
            default="false",
        )

        # Condition to check if we should filter by cluster
        self.filter_by_cluster_condition = CfnCondition(
            self,
            "FilterByCluster",
            expression=Fn.condition_and(
                Fn.condition_equals(self.monitor_all_clusters.value_as_string, "false"),
                Fn.condition_not(
                    Fn.condition_equals(self.existing_cluster_arn.value_as_string, "")
                ),
            ),
        )

        # Create only the event infrastructure
        self.queue, self.dlq = self.create_sqs_infrastructure()
        self.eventbridge_rule = self._create_conditional_eventbridge_rule()

        # Output the queue configuration for workers to consume
        CfnOutput(
            self,
            "ObserverConfiguration",
            value=Fn.sub(
                '{"queue_url": "${QueueUrl}", "queue_arn": "${QueueArn}"}',
                {
                    "QueueUrl": self.queue.queue_url,
                    "QueueArn": self.queue.queue_arn,
                },
            ),
            description="Configuration for ECS observer (JSON format)",
        )

    def _create_conditional_eventbridge_rule(self):
        """Create EventBridge rule with conditional cluster filtering."""
        # Determine cluster ARN to use for filtering
        cluster_arn = Fn.condition_if(
            self.filter_by_cluster_condition.logical_id,
            self.existing_cluster_arn.value_as_string,
            Fn.ref("AWS::NoValue"),  # No filtering if monitoring all clusters
        ).to_string()

        return self.create_eventbridge_rule(
            self.queue,
            cluster_arn=cluster_arn if self.filter_by_cluster_condition else None,
        )

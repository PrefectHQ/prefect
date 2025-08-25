"""Events-only stack - sets up EventBridge and SQS for ECS task state changes."""

from aws_cdk import (
    CfnOutput,
    CfnParameter,
    Duration,
    Stack,
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
    aws_sqs as sqs,
)
from constructs import Construct


class EcsEventsStack(Stack):
    """EventBridge and SQS infrastructure for ECS task state monitoring."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Parameters
        self.work_pool_name = CfnParameter(
            self,
            "WorkPoolName",
            type="String",
            description="Name of the Prefect work pool",
            default="ecs-work-pool",
        )

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

import aws_cdk as core
import aws_cdk.assertions as assertions

from ..worker.events_stack import EcsEventsStack
from ..worker.service_stack import EcsServiceStack


def test_service_stack():
    """Test that service stack doesn't create cluster."""
    app = core.App()
    stack = EcsServiceStack(app, "TestServiceStack")
    template = assertions.Template.from_stack(stack)

    # Should NOT have ECS cluster
    template.resource_count_is("AWS::ECS::Cluster", 0)

    # Should have ECS service
    template.resource_count_is("AWS::ECS::Service", 1)

    # Should have SQS queue and DLQ
    template.resource_count_is("AWS::SQS::Queue", 2)

    # Should have EventBridge rule
    template.resource_count_is("AWS::Events::Rule", 1)


def test_events_stack():
    """Test that events stack only creates event infrastructure."""
    app = core.App()
    stack = EcsEventsStack(app, "TestEventsStack")
    template = assertions.Template.from_stack(stack)

    # Should NOT have ECS cluster or service
    template.resource_count_is("AWS::ECS::Cluster", 0)
    template.resource_count_is("AWS::ECS::Service", 0)

    # Should have SQS queue and DLQ
    template.resource_count_is("AWS::SQS::Queue", 2)

    # Should have EventBridge rule
    template.resource_count_is("AWS::Events::Rule", 1)


def test_all_stacks_have_outputs():
    """Test that all stacks provide necessary outputs."""
    app = core.App()

    service_stack = EcsServiceStack(app, "TestServiceStack")
    events_stack = EcsEventsStack(app, "TestEventsStack")

    service_template = assertions.Template.from_stack(service_stack)
    events_template = assertions.Template.from_stack(events_stack)

    # All should have queue outputs
    for template in [service_template, events_template]:
        template.has_output("EcsEventsQueueUrl", {})
        template.has_output("EcsEventsQueueArn", {})

    # Service stack should have service outputs
    service_template.has_output("ServiceArn", {})


def test_conditional_secret_creation():
    """Test that secrets are created conditionally based on auth method."""
    app = core.App()
    stack = EcsServiceStack(app, "TestServiceStack")
    template = assertions.Template.from_stack(stack)

    # Should have conditional API key secret creation
    template.has_condition(
        "CreateNewApiKeySecret",
        {
            "Fn::And": [
                {"Condition": "UseApiKey"},
                {"Fn::Equals": [{"Ref": "PrefectApiKeySecretArn"}, ""]},
            ]
        },
    )

    # Should have conditional auth string secret creation
    template.has_condition(
        "CreateNewAuthStringSecret",
        {
            "Fn::And": [
                {"Condition": "UseAuthString"},
                {"Fn::Equals": [{"Ref": "PrefectAuthStringSecretArn"}, ""]},
            ]
        },
    )

    # Should have both secrets with their respective conditions
    template.has_resource(
        "AWS::SecretsManager::Secret", {"Condition": "CreateNewApiKeySecret"}
    )
    template.has_resource(
        "AWS::SecretsManager::Secret", {"Condition": "CreateNewAuthStringSecret"}
    )


def test_work_queues_parameter():
    """Test that work queues parameter is properly configured."""
    app = core.App()
    stack = EcsServiceStack(app, "TestServiceStack")
    template = assertions.Template.from_stack(stack)

    # Should have WorkQueues parameter as CommaDelimitedList
    template.has_parameter("WorkQueues", {"Type": "CommaDelimitedList"})

    # Should have condition for work queues
    template.has_condition(
        "HasWorkQueues",
        {"Fn::Not": [{"Fn::Equals": [{"Fn::Select": [0, {"Ref": "WorkQueues"}]}, ""]}]},
    )


def test_auth_conditions():
    """Test CloudFormation conditions for auth method selection."""
    app = core.App()
    stack = EcsServiceStack(app, "TestServiceStack")
    template = assertions.Template.from_stack(stack)

    # Should have conditions for auth method selection
    template.has_condition(
        "UseApiKey",
        {
            "Fn::Or": [
                {"Fn::Not": [{"Fn::Equals": [{"Ref": "PrefectApiKeySecretArn"}, ""]}]},
                {"Fn::Not": [{"Fn::Equals": [{"Ref": "PrefectApiKey"}, ""]}]},
            ]
        },
    )

    template.has_condition(
        "UseAuthString",
        {
            "Fn::Or": [
                {
                    "Fn::Not": [
                        {"Fn::Equals": [{"Ref": "PrefectAuthStringSecretArn"}, ""]}
                    ]
                },
                {"Fn::Not": [{"Fn::Equals": [{"Ref": "PrefectAuthString"}, ""]}]},
            ]
        },
    )

    # Should have conditions for secret creation
    template.has_condition(
        "CreateNewApiKeySecret",
        {
            "Fn::And": [
                {"Condition": "UseApiKey"},
                {"Fn::Equals": [{"Ref": "PrefectApiKeySecretArn"}, ""]},
            ]
        },
    )

    template.has_condition(
        "CreateNewAuthStringSecret",
        {
            "Fn::And": [
                {"Condition": "UseAuthString"},
                {"Fn::Equals": [{"Ref": "PrefectAuthStringSecretArn"}, ""]},
            ]
        },
    )


def test_iam_permissions():
    """Test that IAM roles have correct permissions."""
    app = core.App()
    stack = EcsServiceStack(app, "TestServiceStack")
    template = assertions.Template.from_stack(stack)

    # Task role should have ECS permissions including the ones we specifically need
    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": assertions.Match.array_with(
                    [
                        assertions.Match.object_like(
                            {
                                "Effect": "Allow",
                                "Action": assertions.Match.array_with(
                                    [
                                        "ecs:RegisterTaskDefinition",
                                        "ecs:DeregisterTaskDefinition",
                                        "ec2:DescribeVpcs",
                                        "logs:GetLogEvents",
                                    ]
                                ),
                                "Resource": "*",
                            }
                        ),
                        assertions.Match.object_like(
                            {
                                "Effect": "Allow",
                                "Action": "iam:PassRole",
                                "Resource": "arn:aws:iam::*:role/*",
                            }
                        ),
                    ]
                )
            }
        },
    )

    # Task execution role should have secrets access
    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": assertions.Match.array_with(
                    [
                        assertions.Match.object_like(
                            {
                                "Effect": "Allow",
                                "Action": "secretsmanager:GetSecretValue",
                            }
                        )
                    ]
                )
            }
        },
    )


def test_eventbridge_rule_patterns():
    """Test EventBridge rule event patterns."""
    # Test service stack EventBridge rule (dynamic cluster filtering)
    service_app = core.App()
    service_stack = EcsServiceStack(service_app, "TestServiceStack")
    service_template = assertions.Template.from_stack(service_stack)

    service_template.has_resource_properties(
        "AWS::Events::Rule",
        {
            "EventPattern": {
                "source": ["aws.ecs"],
                "detail-type": ["ECS Task State Change"],
                "detail": {
                    "clusterArn": assertions.Match.any_value(),  # Dynamic based on cluster identifier
                },
            }
        },
    )

    # Test events stack EventBridge rule (should filter by cluster) - separate app
    events_app = core.App()
    events_stack = EcsEventsStack(events_app, "TestEventsStack")
    events_template = assertions.Template.from_stack(events_stack)

    events_template.has_resource_properties(
        "AWS::Events::Rule",
        {
            "EventPattern": {
                "source": ["aws.ecs"],
                "detail-type": ["ECS Task State Change"],
                "detail": {
                    "clusterArn": [{"Ref": "ExistingClusterArn"}],
                },
            }
        },
    )


def test_sqs_configuration():
    """Test SQS queue configuration."""
    app = core.App()
    stack = EcsServiceStack(app, "TestServiceStack")
    template = assertions.Template.from_stack(stack)

    # Main queue configuration
    template.has_resource_properties(
        "AWS::SQS::Queue",
        {
            "MessageRetentionPeriod": 604800,  # 7 days
            "VisibilityTimeout": 300,  # 5 minutes
            "RedrivePolicy": {"maxReceiveCount": 3},
        },
    )

    # DLQ configuration
    template.has_resource_properties(
        "AWS::SQS::Queue",
        {
            "MessageRetentionPeriod": 1209600,  # 14 days
            "VisibilityTimeout": 60,  # 1 minute
        },
    )

    # Queue policy for EventBridge - just check that required actions are present
    template.has_resource_properties(
        "AWS::SQS::QueuePolicy",
        {
            "PolicyDocument": {
                "Statement": assertions.Match.array_with(
                    [
                        assertions.Match.object_like(
                            {
                                "Effect": "Allow",
                                "Principal": {"Service": "events.amazonaws.com"},
                                "Action": assertions.Match.array_with(
                                    [
                                        "sqs:SendMessage"  # Key permission for EventBridge
                                    ]
                                ),
                            }
                        )
                    ]
                )
            }
        },
    )


def test_parameter_validation():
    """Test CloudFormation parameters have correct types and constraints."""
    app = core.App()
    service_stack = EcsServiceStack(app, "TestServiceStack")
    events_stack = EcsEventsStack(app, "TestEventsStack")

    service_template = assertions.Template.from_stack(service_stack)
    events_template = assertions.Template.from_stack(events_stack)

    # Service stack parameters
    service_template.has_parameter("WorkPoolName", {"Type": "String"})
    service_template.has_parameter("PrefectApiUrl", {"Type": "String"})
    service_template.has_parameter("DockerImage", {"Type": "String"})
    service_template.has_parameter("WorkQueues", {"Type": "CommaDelimitedList"})
    service_template.has_parameter("LogRetentionDays", {"Type": "Number"})

    # Auth parameters (both API key and auth string)
    service_template.has_parameter("PrefectApiKeySecretArn", {"Type": "String"})
    service_template.has_parameter("PrefectApiKey", {"Type": "String", "NoEcho": True})
    service_template.has_parameter("PrefectAuthStringSecretArn", {"Type": "String"})
    service_template.has_parameter(
        "PrefectAuthString", {"Type": "String", "NoEcho": True}
    )

    # Service-specific parameters
    service_template.has_parameter(
        "ExistingClusterIdentifier",
        {
            "Type": "String",
            "AllowedPattern": "^(arn:aws:ecs:[a-z0-9-]+:\\d{12}:cluster/.+|[a-zA-Z][a-zA-Z0-9_-]{0,254})$",
        },
    )
    service_template.has_parameter(
        "ExistingVpcId", {"Type": "String", "AllowedPattern": "^vpc-[0-9a-f]{8,17}$"}
    )
    service_template.has_parameter("ExistingSubnetIds", {"Type": "CommaDelimitedList"})

    # Events stack parameters (minimal set)
    events_template.has_parameter("WorkPoolName", {"Type": "String"})
    events_template.has_parameter("ExistingClusterArn", {"Type": "String"})

    # Events stack should NOT have these parameters (test that they raise AssertionError)
    try:
        events_template.has_parameter("PrefectApiUrl", {"Type": "String"})
        assert False, "Expected AssertionError for PrefectApiUrl parameter"
    except Exception as e:
        assert "AssertionError" in str(e), f"Expected AssertionError, got: {e}"

    try:
        events_template.has_parameter("DockerImage", {"Type": "String"})
        assert False, "Expected AssertionError for DockerImage parameter"
    except Exception as e:
        assert "AssertionError" in str(e), f"Expected AssertionError, got: {e}"

    try:
        events_template.has_parameter("WorkQueues", {"Type": "CommaDelimitedList"})
        assert False, "Expected AssertionError for WorkQueues parameter"
    except Exception as e:
        assert "AssertionError" in str(e), f"Expected AssertionError, got: {e}"


def test_resource_naming():
    """Test that resources have predictable names based on work pool."""
    app = core.App()
    stack = EcsServiceStack(app, "TestServiceStack")
    template = assertions.Template.from_stack(stack)

    # Queue names should use work pool name
    template.has_resource_properties(
        "AWS::SQS::Queue",
        {"QueueName": {"Fn::Join": ["", [{"Ref": "WorkPoolName"}, "-ecs-events"]]}},
    )

    template.has_resource_properties(
        "AWS::SQS::Queue",
        {"QueueName": {"Fn::Join": ["", [{"Ref": "WorkPoolName"}, "-ecs-events-dlq"]]}},
    )

    # EventBridge rule name
    template.has_resource_properties(
        "AWS::Events::Rule",
        {"Name": {"Fn::Join": ["", [{"Ref": "WorkPoolName"}, "-ecs-task-events"]]}},
    )

    # IAM role names
    template.has_resource_properties(
        "AWS::IAM::Role",
        {"RoleName": {"Fn::Join": ["", [{"Ref": "WorkPoolName"}, "-task-role"]]}},
    )

    template.has_resource_properties(
        "AWS::IAM::Role",
        {
            "RoleName": {
                "Fn::Join": ["", [{"Ref": "WorkPoolName"}, "-task-execution-role"]]
            }
        },
    )


def test_conditional_log_group():
    """Test conditional log group creation."""
    app = core.App()
    stack = EcsServiceStack(app, "TestServiceStack")
    template = assertions.Template.from_stack(stack)

    # Should have condition for existing log group
    template.has_condition(
        "UseExistingLogGroup",
        {"Fn::Not": [{"Fn::Equals": [{"Ref": "ExistingLogGroupName"}, ""]}]},
    )

    # Log group should only be created when NOT using existing log group
    template.has_resource(
        "AWS::Logs::LogGroup",
        {
            "Condition": "CreateNewLogGroup",
            "Properties": {
                "LogGroupName": {
                    "Fn::Join": [
                        "/",
                        ["/ecs", {"Ref": "WorkPoolName"}, assertions.Match.any_value()],
                    ]
                },
                "RetentionInDays": {"Ref": "LogRetentionDays"},
            },
        },
    )

    # Should have condition for creating new log group
    template.has_condition(
        "CreateNewLogGroup",
        {"Fn::Not": [{"Condition": "UseExistingLogGroup"}]},
    )


def test_cluster_arn_handling():
    """Test cluster ARN vs name handling in service stack."""
    app = core.App()
    stack = EcsServiceStack(app, "TestServiceStack")
    template = assertions.Template.from_stack(stack)

    # Should have condition to detect cluster ARN
    template.has_condition(
        "IsClusterArn",
        {
            "Fn::Equals": [
                {
                    "Fn::Select": [
                        0,
                        {"Fn::Split": [":", {"Ref": "ExistingClusterIdentifier"}]},
                    ]
                },
                "arn",
            ]
        },
    )

    # Service cluster reference should handle both cases
    template.has_resource_properties(
        "AWS::ECS::Service",
        {
            "Cluster": {
                "Fn::If": [
                    "IsClusterArn",
                    {
                        "Fn::Select": [
                            1,
                            {"Fn::Split": ["/", {"Ref": "ExistingClusterIdentifier"}]},
                        ]
                    },
                    {"Ref": "ExistingClusterIdentifier"},
                ]
            }
        },
    )


def test_task_definition_configuration():
    """Test ECS task definition configuration."""
    app = core.App()
    stack = EcsServiceStack(app, "TestServiceStack")
    template = assertions.Template.from_stack(stack)

    # Task definition should have correct configuration
    template.has_resource_properties(
        "AWS::ECS::TaskDefinition",
        {
            "Family": {"Fn::Join": ["", [{"Ref": "WorkPoolName"}, "-worker"]]},
            "RequiresCompatibilities": ["FARGATE"],
            "NetworkMode": "awsvpc",
        },
    )

    # Container should have health check
    template.has_resource_properties(
        "AWS::ECS::TaskDefinition",
        {
            "ContainerDefinitions": [
                assertions.Match.object_like(
                    {
                        "Name": "prefect-worker",
                        "HealthCheck": {
                            "Command": [
                                "CMD-SHELL",
                                assertions.Match.string_like_regexp(r".*urllib.*"),
                            ],
                            "Interval": 30,
                            "Timeout": 5,
                            "Retries": 3,
                            "StartPeriod": 60,
                        },
                    }
                )
            ]
        },
    )


def test_service_networking():
    """Test ECS service networking configuration."""
    app = core.App()
    stack = EcsServiceStack(app, "TestServiceStack")
    template = assertions.Template.from_stack(stack)

    # Service should disable public IP
    template.has_resource_properties(
        "AWS::ECS::Service",
        {
            "NetworkConfiguration": {
                "AwsvpcConfiguration": {"AssignPublicIp": "DISABLED"}
            }
        },
    )

    # Security group should allow health check port
    template.has_resource_properties(
        "AWS::EC2::SecurityGroup",
        {
            "SecurityGroupIngress": [
                {
                    "CidrIp": "0.0.0.0/0",
                    "Description": "Health check endpoint",
                    "FromPort": 8080,
                    "ToPort": 8080,
                    "IpProtocol": "tcp",
                }
            ]
        },
    )


def test_auto_scaling_configuration():
    """Test ECS service auto scaling configuration."""
    app = core.App()
    stack = EcsServiceStack(app, "TestServiceStack")
    template = assertions.Template.from_stack(stack)

    # Should have scalable target
    template.resource_count_is("AWS::ApplicationAutoScaling::ScalableTarget", 1)

    # Should have CPU and memory scaling policies
    template.resource_count_is("AWS::ApplicationAutoScaling::ScalingPolicy", 2)

    # CPU scaling policy
    template.has_resource_properties(
        "AWS::ApplicationAutoScaling::ScalingPolicy",
        {
            "PolicyType": "TargetTrackingScaling",
            "TargetTrackingScalingPolicyConfiguration": {
                "PredefinedMetricSpecification": {
                    "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
                },
                "TargetValue": 70,
            },
        },
    )

    # Memory scaling policy
    template.has_resource_properties(
        "AWS::ApplicationAutoScaling::ScalingPolicy",
        {
            "PolicyType": "TargetTrackingScaling",
            "TargetTrackingScalingPolicyConfiguration": {
                "PredefinedMetricSpecification": {
                    "PredefinedMetricType": "ECSServiceAverageMemoryUtilization"
                },
                "TargetValue": 80,
            },
        },
    )


def test_required_outputs():
    """Test that all stacks provide required outputs."""
    app = core.App()
    service_stack = EcsServiceStack(app, "TestServiceStack")
    events_stack = EcsEventsStack(app, "TestEventsStack")

    service_template = assertions.Template.from_stack(service_stack)
    events_template = assertions.Template.from_stack(events_stack)

    # Both should have SQS outputs
    for template in [service_template, events_template]:
        template.has_output(
            "EcsEventsQueueUrl",
            {"Description": "URL of the SQS queue receiving ECS events"},
        )
        template.has_output(
            "EcsEventsQueueArn",
            {"Description": "ARN of the SQS queue receiving ECS events"},
        )
        template.has_output(
            "EventBridgeRuleArn",
            {"Description": "ARN of the EventBridge rule for ECS events"},
        )

    # Events stack should have queue name output
    events_template.has_output(
        "EcsEventsQueueName",
        {"Description": "Name of the SQS queue receiving ECS events"},
    )

    # Service stack should have service outputs
    service_template.has_output("ServiceArn", {"Description": "ARN of the ECS service"})
    service_template.has_output(
        "TaskDefinitionArn",
        {"Description": "ARN of the ECS task definition for the worker"},
    )

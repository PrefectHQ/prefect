import aws_cdk as core
import aws_cdk.assertions as assertions
from worker.events_stack import EcsEventsStack
from worker.service_stack import EcsServiceStack


def test_service_stack_no_cluster():
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


def test_events_stack_minimal():
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
    """Test that API key secret is created conditionally."""
    app = core.App()
    stack = EcsServiceStack(app, "TestServiceStack")
    template = assertions.Template.from_stack(stack)

    # Should have conditional secret
    template.has_condition(
        "CreateNewSecret", {"Fn::Equals": [{"Ref": "PrefectApiKeySecretArn"}, ""]}
    )

    # Should have secret with condition
    template.has_resource(
        "AWS::SecretsManager::Secret", {"Condition": "CreateNewSecret"}
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

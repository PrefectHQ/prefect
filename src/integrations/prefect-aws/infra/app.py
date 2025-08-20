#!/usr/bin/env python3
import aws_cdk as cdk
from worker.events_stack import EcsEventsStack
from worker.service_stack import EcsServiceStack

app = cdk.App()

# Create stack variants for different deployment scenarios
EcsServiceStack(app, "PrefectEcsServiceStack")
EcsEventsStack(app, "PrefectEcsEventsStack")

app.synth()

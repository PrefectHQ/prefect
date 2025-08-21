#!/usr/bin/env python3
import aws_cdk as cdk
from worker.events_stack import EcsEventsStack
from worker.service_stack import EcsServiceStack

app = cdk.App()

# Create stack variants for different deployment scenarios without bootstrap requirements
EcsServiceStack(
    app,
    "PrefectEcsServiceStack",
    synthesizer=cdk.DefaultStackSynthesizer(generate_bootstrap_version_rule=False),
)
EcsEventsStack(
    app,
    "PrefectEcsEventsStack",
    synthesizer=cdk.DefaultStackSynthesizer(generate_bootstrap_version_rule=False),
)

app.synth()

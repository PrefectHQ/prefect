"""
[Flow Runners](/concepts/flow-runners/) in Prefect are responsible for creating and
monitoring infrastructure for flow runs associated with deployments.

A flow runner can only be used with a deployment. When you run a flow directly by
calling the flow yourself, you are responsible for the environment in which the flow
executes.

For usage details, see the [Flow Runners](/concepts/flow-runners/) documentation.
"""

from prefect.flow_runners.base import FlowRunner, UniversalFlowRunner
from prefect.flow_runners.docker import DockerFlowRunner, ImagePullPolicy
from prefect.flow_runners.kubernetes import (
    KubernetesFlowRunner,
    KubernetesImagePullPolicy,
    KubernetesRestartPolicy,
)
from prefect.flow_runners.subprocess import SubprocessFlowRunner

# The flow runner should be able to run containers with this version or newer.
# Containers with versions of prefect before this version are not expected to run
# correctly.
MIN_COMPAT_PREFECT_VERSION = "2.0b8"


__all__ = [
    "DockerFlowRunner",
    "FlowRunner",
    "ImagePullPolicy",
    "KubernetesFlowRunner",
    "KubernetesImagePullPolicy",
    "KubernetesRestartPolicy",
    "SubprocessFlowRunner",
    "UniversalFlowRunner",
]

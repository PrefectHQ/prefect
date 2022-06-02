"""
[Flow Runners](/concepts/flow-runners/) in Prefect are responsible for creating and
monitoring infrastructure for flow runs associated with deployments.

A flow runner can only be used with a deployment. When you run a flow directly by
calling the flow yourself, you are responsible for the environment in which the flow
executes.

For usage details, see the [Flow Runners](/concepts/flow-runners/) documentation.
"""

from .base import (  # noqa: F401, these are package re-exports
    FlowRunner,
    FlowRunnerSettings,
    FlowRunnerT,
    UniversalFlowRunner,
    base_flow_run_environment,
    get_prefect_image_name,
    lookup_flow_runner,
    python_version_micro,
    python_version_minor,
    register_flow_runner,
)
from .docker import (  # noqa: F401, these are package re-exports
    DockerFlowRunner,
    ImagePullPolicy,
)
from .kubernetes import (  # noqa: F401, these are package re-exports
    KubernetesFlowRunner,
    KubernetesImagePullPolicy,
    KubernetesRestartPolicy,
)
from .subprocess import SubprocessFlowRunner  # noqa: F401, these are package re-exports

# The flow runner should be able to run containers with this version or newer.
# Containers with versions of prefect before this version are not expected to run
# correctly.
MIN_COMPAT_PREFECT_VERSION = "2.0b7"

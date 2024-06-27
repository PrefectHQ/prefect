from prefect._internal.compatibility.migration import getattr_migration
import prefect.deployments.base
import prefect.deployments.steps
from prefect.deployments.base import (
    initialize_project,
)

from prefect.deployments.runner import (
    RunnerDeployment,
    deploy,
    DockerImage,
    EntrypointType,
)


from prefect.deployments.flow_runs import (
    run_deployment,
)

__getattr__ = getattr_migration(__name__)

"""
Execution environments encapsulate the logic for where your Flow should execute in Prefect Cloud.

Currently, we recommend all users deploy their Flow using the `RemoteEnvironment` configured with the
appropriate choice of executor.
"""
from prefect.environments.execution.base import Environment
from prefect.environments.execution.dask import DaskKubernetesEnvironment
from prefect.environments.execution.fargate import FargateTaskEnvironment
from prefect.environments.execution.k8s import KubernetesJobEnvironment
from prefect.environments.execution.local import LocalEnvironment
from prefect.environments.execution.remote import RemoteEnvironment

try:
    from prefect.environments.execution.fargate import FargateTaskEnvironment
except ImportError:
    raise ImportError(
        'Using `prefect.environments.FargateTaskEnvironment` requires Prefect to be installed with the "aws" extra.'
    )

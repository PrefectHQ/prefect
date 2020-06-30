"""
Execution environments encapsulate the logic for where your Flow should execute in Prefect Cloud.

Currently, we recommend all users deploy their Flow using the `LocalEnvironment` configured with the
appropriate choice of executor.
"""
from prefect.environments.execution.base import Environment, load_and_run_flow
from prefect.environments.execution.dask import DaskKubernetesEnvironment
from prefect.environments.execution.dask import DaskCloudProviderEnvironment
from prefect.environments.execution.fargate import FargateTaskEnvironment
from prefect.environments.execution.k8s import KubernetesJobEnvironment
from prefect.environments.execution.local import LocalEnvironment
from prefect.environments.execution.remote import RemoteEnvironment
from prefect.environments.execution.dask import RemoteDaskEnvironment

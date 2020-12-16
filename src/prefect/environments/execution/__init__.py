"""
Execution environments encapsulate the logic for where your Flow should execute in Prefect Cloud.

DEPRECATED: Environment based configuration is deprecated, please transition to
configuring `flow.run_config` instead of `flow.environment`. See
https://docs.prefect.io/orchestration/flow_config/overview.html for more info.
"""
from prefect.environments.execution.base import Environment, load_and_run_flow
from prefect.environments.execution.dask import DaskKubernetesEnvironment
from prefect.environments.execution.dask import DaskCloudProviderEnvironment
from prefect.environments.execution.fargate import FargateTaskEnvironment
from prefect.environments.execution.k8s import KubernetesJobEnvironment
from prefect.environments.execution.local import LocalEnvironment

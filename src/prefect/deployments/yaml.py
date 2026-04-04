from pathlib import Path
from typing import List

from prefect.flows import load_flow_from_entrypoint
from prefect.deployments.runner import RunnerDeployment

# Temporary import from CLI (we may refactor later)
from prefect.cli.deploy._config import _load_deploy_configs_and_actions


class DummyConsole:
    def print(self, *args, **kwargs):
        pass


def deploy_from_yaml(path: str) -> List[RunnerDeployment]:
    path = Path(path)

    # Load YAML configs
    deploy_configs, actions = _load_deploy_configs_and_actions(
        path,
        console=DummyConsole()
    )

    deployments = []  # ✅ create list

    for config in deploy_configs:  # ✅ loop added
        entrypoint = config.get("entrypoint")

        # Load flow FIRST
        flow = load_flow_from_entrypoint(entrypoint)

        # THEN define flow_name
        flow_name = flow.name

        # THEN use it
        deployment = RunnerDeployment(
            name=config.get("name"),
            flow_name=flow_name,
            entrypoint=entrypoint,
            work_pool_name=(config.get("work_pool") or {}).get("name"),
            parameters=config.get("parameters") or {},
            description=config.get("description"),
            tags=config.get("tags") or [],
        )

        # Apply deployment
        deployment.apply()

        deployments.append(deployment)

    return deployments
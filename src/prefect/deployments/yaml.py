from pathlib import Path
from uuid import UUID


def _non_interactive() -> bool:
    return False


class _SilentConsole:
    """Suppresses Rich console output when deploying via SDK."""

    def print(self, *args, **kwargs) -> None:
        pass

    def print_json(self, *args, **kwargs) -> None:
        pass


async def deploy_from_yaml(path: str) -> list[UUID]:
    """
    Deploy flows defined in a prefect.yaml file via the SDK.

    Args:
        path: Path to the prefect.yaml file.

    Returns:
        List of UUIDs for the created/updated deployments.

    Example:
        import asyncio
        from prefect.deployments import deploy_from_yaml

        asyncio.run(deploy_from_yaml("prefect.yaml"))
    """
    from prefect.cli.deploy._config import (
        _load_deploy_configs_and_actions,
        _pick_deploy_configs,
    )
    from prefect.cli.deploy._core import _run_multi_deploy, _run_single_deploy

    yaml_path = Path(path)
    if not yaml_path.exists():
        raise FileNotFoundError(f"No prefect.yaml found at: {path}")

    console = _SilentConsole()

    all_deploy_configs, actions = _load_deploy_configs_and_actions(
        prefect_file=yaml_path,
        console=console,
    )

    deploy_configs = _pick_deploy_configs(
        all_deploy_configs,
        names=[],
        deploy_all=True,
        console=console,
        is_interactive=_non_interactive,
    )

    if not deploy_configs:
        raise ValueError("No deployments found in prefect.yaml")

    if len(deploy_configs) > 1:
        return await _run_multi_deploy(
            deploy_configs=deploy_configs,
            actions=actions,
            deploy_all=True,
            prefect_file=yaml_path,
            console=console,
            is_interactive=_non_interactive,
        )

    deployment_id = await _run_single_deploy(
        deploy_config=deploy_configs[0],
        actions=actions,
        options={},
        prefect_file=yaml_path,
        console=console,
        is_interactive=_non_interactive,
    )
    return [deployment_id]

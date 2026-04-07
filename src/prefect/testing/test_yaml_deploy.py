import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def prefect_yaml(tmp_path):
    content = """
deployments:
  - name: test-deployment
    entrypoint: myflow.py:my_flow
    work_pool:
      name: my-pool
"""
    f = tmp_path / "prefect.yaml"
    f.write_text(content)
    return str(f)


@pytest.mark.asyncio
async def test_deploy_from_yaml_file_not_found():
    from prefect.deployments.yaml import deploy_from_yaml
    with pytest.raises(FileNotFoundError, match="No prefect.yaml found"):
        await deploy_from_yaml("nonexistent.yaml")


@pytest.mark.asyncio
async def test_deploy_from_yaml_no_deployments(tmp_path):
    f = tmp_path / "prefect.yaml"
    f.write_text("deployments: []")
    with patch(
        "prefect.cli.deploy._config._load_deploy_configs_and_actions",
        return_value=([], []),
    ), patch(
        "prefect.cli.deploy._config._pick_deploy_configs",
        return_value=[],
    ):
        from prefect.deployments.yaml import deploy_from_yaml
        with pytest.raises(ValueError, match="No deployments found"):
            await deploy_from_yaml(str(f))


@pytest.mark.asyncio
async def test_deploy_from_yaml_single(prefect_yaml):
    mock_config = {"name": "test-deployment", "entrypoint": "myflow.py:my_flow"}
    with patch(
        "prefect.cli.deploy._config._load_deploy_configs_and_actions",
        return_value=([mock_config], []),
    ), patch(
        "prefect.cli.deploy._config._pick_deploy_configs",
        return_value=[mock_config],
    ), patch(
        "prefect.cli.deploy._core._run_single_deploy",
        new_callable=AsyncMock,
    ) as mock_single:
        from prefect.deployments.yaml import deploy_from_yaml
        await deploy_from_yaml(prefect_yaml)
        mock_single.assert_called_once()


@pytest.mark.asyncio
async def test_deploy_from_yaml_multi(prefect_yaml):
    mock_configs = [
        {"name": "deployment-1", "entrypoint": "myflow.py:flow_one"},
        {"name": "deployment-2", "entrypoint": "myflow.py:flow_two"},
    ]
    with patch(
        "prefect.cli.deploy._config._load_deploy_configs_and_actions",
        return_value=(mock_configs, []),
    ), patch(
        "prefect.cli.deploy._config._pick_deploy_configs",
        return_value=mock_configs,
    ), patch(
        "prefect.cli.deploy._core._run_multi_deploy",
        new_callable=AsyncMock,
    ) as mock_multi:
        from prefect.deployments.yaml import deploy_from_yaml
        await deploy_from_yaml(prefect_yaml)
        mock_multi.assert_called_once()
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest


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
    with (
        patch(
            "prefect.cli.deploy._config._load_deploy_configs_and_actions",
            return_value=([], []),
        ),
        patch(
            "prefect.cli.deploy._config._pick_deploy_configs",
            return_value=[],
        ),
    ):
        from prefect.deployments.yaml import deploy_from_yaml

        with pytest.raises(ValueError, match="No deployments found"):
            await deploy_from_yaml(str(f))


@pytest.mark.asyncio
async def test_deploy_from_yaml_single(prefect_yaml):
    mock_config = {"name": "test-deployment", "entrypoint": "myflow.py:my_flow"}
    deployment_id = uuid4()
    with (
        patch(
            "prefect.cli.deploy._config._load_deploy_configs_and_actions",
            return_value=([mock_config], []),
        ),
        patch(
            "prefect.cli.deploy._config._pick_deploy_configs",
            return_value=[mock_config],
        ) as mock_pick_configs,
        patch(
            "prefect.cli.deploy._core._run_single_deploy",
            new_callable=AsyncMock,
            return_value=deployment_id,
        ) as mock_single,
    ):
        from prefect.deployments.yaml import deploy_from_yaml

        result = await deploy_from_yaml(prefect_yaml)

        assert result == [deployment_id]
        mock_single.assert_called_once()
        assert callable(mock_pick_configs.call_args.kwargs["is_interactive"])
        assert mock_pick_configs.call_args.kwargs["is_interactive"]() is False
        assert callable(mock_single.call_args.kwargs["is_interactive"])
        assert mock_single.call_args.kwargs["is_interactive"]() is False


@pytest.mark.asyncio
async def test_deploy_from_yaml_multi(prefect_yaml):
    mock_configs = [
        {"name": "deployment-1", "entrypoint": "myflow.py:flow_one"},
        {"name": "deployment-2", "entrypoint": "myflow.py:flow_two"},
    ]
    deployment_ids = [uuid4(), uuid4()]
    with (
        patch(
            "prefect.cli.deploy._config._load_deploy_configs_and_actions",
            return_value=(mock_configs, []),
        ),
        patch(
            "prefect.cli.deploy._config._pick_deploy_configs",
            return_value=mock_configs,
        ) as mock_pick_configs,
        patch(
            "prefect.cli.deploy._core._run_multi_deploy",
            new_callable=AsyncMock,
            return_value=deployment_ids,
        ) as mock_multi,
    ):
        from prefect.deployments.yaml import deploy_from_yaml

        result = await deploy_from_yaml(prefect_yaml)

        assert result == deployment_ids
        mock_multi.assert_called_once()
        assert callable(mock_pick_configs.call_args.kwargs["is_interactive"])
        assert mock_pick_configs.call_args.kwargs["is_interactive"]() is False
        assert callable(mock_multi.call_args.kwargs["is_interactive"])
        assert mock_multi.call_args.kwargs["is_interactive"]() is False


@pytest.mark.asyncio
async def test_run_multi_deploy_returns_deployment_ids():
    deployment_ids = [uuid4(), uuid4()]
    deploy_configs = [{"name": "one"}, {"name": "two"}]
    silent_console = type(
        "SilentConsole",
        (),
        {
            "print": lambda self, *args, **kwargs: None,
            "print_json": lambda self, *args, **kwargs: None,
        },
    )()

    with (
        patch(
            "prefect.cli.deploy._core._run_single_deploy",
            new_callable=AsyncMock,
            side_effect=deployment_ids,
        ),
        patch(
            "prefect.cli.deploy._core.escape",
            side_effect=lambda value: value,
        ),
    ):
        from prefect.cli.deploy._core import _run_multi_deploy

        result = await _run_multi_deploy(
            deploy_configs=deploy_configs,
            actions={},
            deploy_all=True,
            console=silent_console,
            is_interactive=lambda: False,
        )

    assert result == deployment_ids

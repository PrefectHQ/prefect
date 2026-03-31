"""Tests for deploy action helpers in prefect.cli.deploy._actions."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prefect.cli.deploy._actions import _generate_default_pull_action


@pytest.fixture
def console():
    return MagicMock()


def _make_deploy_config(
    *,
    entrypoint: str = "flows/my_flow.py:my_flow",
    image: str | None = None,
    build: list | None = None,
):
    config: dict = {"entrypoint": entrypoint}
    if build is not None:
        config["build"] = build
    if image is not None:
        config.setdefault("work_pool", {}).setdefault("job_variables", {})["image"] = (
            image
        )
    return config


class TestGenerateDefaultPullActionCustomImage:
    """When build is null and job_variables.image is set, the pull step
    should point to a container path instead of the local cwd."""

    @pytest.mark.asyncio
    async def test_non_interactive_uses_opt_prefect(self, console):
        deploy_config = _make_deploy_config(image="my-registry/my-image:latest")
        actions = {"build": []}

        result = await _generate_default_pull_action(
            console,
            deploy_config=deploy_config,
            actions=actions,
            is_interactive=lambda: False,
        )

        assert result == [
            {
                "prefect.deployments.steps.set_working_directory": {
                    "directory": "/opt/prefect"
                }
            }
        ]

    @pytest.mark.asyncio
    async def test_non_interactive_prints_warning(self, console):
        deploy_config = _make_deploy_config(image="my-registry/my-image:latest")
        actions = {"build": []}

        await _generate_default_pull_action(
            console,
            deploy_config=deploy_config,
            actions=actions,
            is_interactive=lambda: False,
        )

        console.print.assert_called_once()
        printed = console.print.call_args[0][0]
        assert "Warning" in printed
        assert "/opt/prefect" in printed

    @pytest.mark.asyncio
    async def test_interactive_prompts_for_directory(self, console):
        deploy_config = _make_deploy_config(image="my-registry/my-image:latest")
        actions = {"build": []}

        with patch(
            "prefect.cli.deploy._actions.prompt",
            return_value="/app/code",
        ) as mock_prompt:
            result = await _generate_default_pull_action(
                console,
                deploy_config=deploy_config,
                actions=actions,
                is_interactive=lambda: True,
            )

        mock_prompt.assert_called_once()
        assert "working directory" in mock_prompt.call_args[0][0].lower()
        assert result == [
            {
                "prefect.deployments.steps.set_working_directory": {
                    "directory": "/app/code"
                }
            }
        ]

    @pytest.mark.asyncio
    async def test_interactive_default_includes_dir_name(self, console):
        deploy_config = _make_deploy_config(image="my-registry/my-image:latest")
        actions = {"build": []}
        dir_name = os.path.basename(os.getcwd())

        with patch(
            "prefect.cli.deploy._actions.prompt",
            return_value=f"/opt/prefect/{dir_name}",
        ) as mock_prompt:
            await _generate_default_pull_action(
                console,
                deploy_config=deploy_config,
                actions=actions,
                is_interactive=lambda: True,
            )

        _, kwargs = mock_prompt.call_args
        assert kwargs["default"] == f"/opt/prefect/{dir_name}"


class TestGenerateDefaultPullActionNoImage:
    """When build is null and no job_variables.image, the existing behavior
    (local cwd) should be preserved."""

    @pytest.mark.asyncio
    async def test_uses_local_cwd(self, console):
        deploy_config = _make_deploy_config()
        actions = {"build": []}

        result = await _generate_default_pull_action(
            console,
            deploy_config=deploy_config,
            actions=actions,
            is_interactive=lambda: False,
        )

        expected_dir = str(Path.cwd().absolute().resolve())
        assert result == [
            {
                "prefect.deployments.steps.set_working_directory": {
                    "directory": expected_dir
                }
            }
        ]


class TestGenerateDefaultPullActionBuildDockerStep:
    """When a build_docker_image step exists, the existing behavior should
    be preserved."""

    @pytest.mark.asyncio
    async def test_auto_dockerfile_generates_pull_step(self, console):
        deploy_config = _make_deploy_config(
            build=[
                {
                    "prefect_docker.deployments.steps.build_docker_image": {
                        "dockerfile": "auto"
                    }
                }
            ]
        )
        actions = {"build": []}

        result = await _generate_default_pull_action(
            console,
            deploy_config=deploy_config,
            actions=actions,
            is_interactive=lambda: False,
        )

        dir_name = os.path.basename(os.getcwd())
        assert result == [
            {
                "prefect.deployments.steps.set_working_directory": {
                    "directory": f"/opt/prefect/{dir_name}"
                }
            }
        ]

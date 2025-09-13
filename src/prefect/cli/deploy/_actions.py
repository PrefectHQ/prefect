from __future__ import annotations

import os
from getpass import GetPassWarning
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import prefect.cli.root as root
from prefect.blocks.system import Secret
from prefect.cli._prompts import (
    confirm,
    prompt,
    prompt_select_blob_storage_credentials,
    prompt_select_remote_flow_storage,
)
from prefect.utilities._git import get_git_branch, get_git_remote_origin_url
from prefect.utilities.slugify import slugify

if TYPE_CHECKING:
    from rich.console import Console


async def _generate_git_clone_pull_step(
    console: "Console",
    deploy_config: dict[str, Any],
    remote_url: str,
) -> list[dict[str, Any]]:
    # confirm/prompt imported from concrete module

    branch = get_git_branch() or "main"

    if not remote_url:
        remote_url = prompt(
            "Please enter the URL to pull your flow code from", console=console
        )

    elif not confirm(
        f"Is [green]{remote_url}[/] the correct URL to pull your flow code from?",
        default=True,
        console=console,
    ):
        remote_url = prompt(
            "Please enter the URL to pull your flow code from", console=console
        )
    if not confirm(
        f"Is [green]{branch}[/] the correct branch to pull your flow code from?",
        default=True,
        console=console,
    ):
        branch = prompt(
            "Please enter the branch to pull your flow code from",
            default="main",
            console=console,
        )
    token_secret_block_name = None
    if confirm("Is this a private repository?", console=console):
        token_secret_block_name = f"deployment-{slugify(deploy_config['name'])}-{slugify(deploy_config['flow_name'])}-repo-token"
        create_new_block = False
        prompt_message = (
            "Please enter a token that can be used to access your private"
            " repository. This token will be saved as a secret via the Prefect API"
        )

        try:
            await Secret.aload(token_secret_block_name)
            if not confirm(
                (
                    "We found an existing token saved for this deployment. Would"
                    " you like use the existing token?"
                ),
                default=True,
                console=console,
            ):
                prompt_message = (
                    "Please enter a token that can be used to access your private"
                    " repository (this will overwrite the existing token saved via"
                    " the Prefect API)."
                )

                create_new_block = True
        except ValueError:
            create_new_block = True

        if create_new_block:
            try:
                repo_token = prompt(
                    prompt_message,
                    console=console,
                    password=True,
                )
            except GetPassWarning:
                # Handling for when password masking is not supported
                repo_token = prompt(
                    prompt_message,
                    console=console,
                )
            await Secret(
                value=repo_token,
            ).save(name=token_secret_block_name, overwrite=True)

    git_clone_step = {
        "prefect.deployments.steps.git_clone": {
            "repository": remote_url,
            "branch": branch,
        }
    }

    if token_secret_block_name:
        git_clone_step["prefect.deployments.steps.git_clone"]["access_token"] = (
            "{{ prefect.blocks.secret." + token_secret_block_name + " }}"
        )

    return [git_clone_step]


async def _generate_pull_step_for_build_docker_image(
    console: "Console", deploy_config: Dict[str, Any], auto: bool = True
) -> list[dict[str, Any]]:
    pull_step: dict[str, Any] = {}
    # prompt imported from concrete module

    dir_name = os.path.basename(os.getcwd())
    if auto:
        pull_step["directory"] = f"/opt/prefect/{dir_name}"
    else:
        pull_step["directory"] = prompt(
            "What is the path to your flow code in your Dockerfile?",
            default=f"/opt/prefect/{dir_name}",
            console=console,
        )

    return [{"prefect.deployments.steps.set_working_directory": pull_step}]


async def _check_for_build_docker_image_step(
    build_action: List[Dict],
) -> Optional[Dict[str, Any]]:
    if not build_action:
        return None

    build_docker_image_steps = [
        "prefect_docker.deployments.steps.build_docker_image",
    ]
    for build_docker_image_step in build_docker_image_steps:
        for action in build_action:
            if action.get(build_docker_image_step):
                return action.get(build_docker_image_step)

    return None


async def _generate_actions_for_remote_flow_storage(
    console: "Console", deploy_config: dict[str, Any], actions: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    # prompt + selection helpers imported from concrete module

    storage_provider_to_collection: dict[str, str] = {
        "s3": "prefect_aws",
        "gcs": "prefect_gcp",
        "azure_blob_storage": "prefect_azure",
    }
    selected_storage_provider = await prompt_select_remote_flow_storage(console=console)

    if selected_storage_provider == "git":
        actions["pull"] = await _generate_git_clone_pull_step(
            console=console,
            deploy_config=deploy_config,
            remote_url=get_git_remote_origin_url(),
        )

    elif selected_storage_provider in storage_provider_to_collection.keys():
        collection = storage_provider_to_collection[selected_storage_provider]

        bucket, folder = prompt("Bucket name"), prompt("Folder name")

        # Prompt user to select or create credentials for the chosen provider
        credentials_block = await prompt_select_blob_storage_credentials(
            console=console, storage_provider=selected_storage_provider
        )
        # This prompt returns a Jinja template string referencing a credentials block
        credentials = credentials_block if credentials_block else None

        step_fields = {
            (
                "container"
                if selected_storage_provider == "azure_blob_storage"
                else "bucket"
            ): bucket,
            "folder": folder,
            "credentials": credentials,
        }

        actions["push"] = [
            {
                f"{collection}.deployments.steps.push_to_{selected_storage_provider}": (
                    step_fields
                )
            }
        ]

        actions["pull"] = [
            {
                f"{collection}.deployments.steps.pull_from_{selected_storage_provider}": (
                    step_fields
                )
            }
        ]

    return actions


async def _generate_default_pull_action(
    console: "Console",
    deploy_config: dict[str, Any],
    actions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    from prefect.cli._utilities import exit_with_error

    build_docker_image_step = await _check_for_build_docker_image_step(
        deploy_config.get("build") or actions["build"]
    )
    if build_docker_image_step:
        dockerfile = build_docker_image_step.get("dockerfile")
        if dockerfile == "auto":
            return await _generate_pull_step_for_build_docker_image(
                console, deploy_config
            )
        if root.is_interactive():
            if not confirm(
                "Does your Dockerfile have a line that copies the current working"
                " directory into your image?"
            ):
                exit_with_error(
                    "Your flow code must be copied into your Docker image to run"
                    " your deployment.\nTo do so, you can copy this line into your"
                    " Dockerfile: [yellow]COPY . /opt/prefect/[/yellow]"
                )
            return await _generate_pull_step_for_build_docker_image(
                console, deploy_config, auto=False
            )
    else:
        entrypoint_path, _ = deploy_config["entrypoint"].split(":")
        console.print(
            "Your Prefect workers will attempt to load your flow from:"
            f" [green]{(Path.cwd() / Path(entrypoint_path)).absolute().resolve()}[/]. To"
            " see more options for managing your flow's code, run:\n\n\t[blue]$"
            " prefect init[/]\n"
        )
        return [
            {
                "prefect.deployments.steps.set_working_directory": {
                    "directory": str(Path.cwd().absolute().resolve())
                }
            }
        ]

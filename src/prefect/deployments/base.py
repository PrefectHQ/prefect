"""
Core primitives for managing Prefect deployments via `prefect deploy`, providing a minimally opinionated
build system for managing flows and deployments.

To get started, follow along with [the deloyments tutorial](/tutorials/deployments/).
"""

from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from ruamel.yaml import YAML

from prefect.client.schemas.objects import ConcurrencyLimitStrategy
from prefect.client.schemas.schedules import IntervalSchedule
from prefect.utilities._git import get_git_branch, get_git_remote_origin_url
from prefect.utilities.annotations import NotSet
from prefect.utilities.filesystem import create_default_ignore_file
from prefect.utilities.templating import apply_values


def create_default_prefect_yaml(
    path: str, name: Optional[str] = None, contents: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Creates default `prefect.yaml` file in the provided path if one does not already exist;
    returns boolean specifying whether a file was created.

    Args:
        name (str, optional): the name of the project; if not provided, the current directory name
            will be used
        contents (dict, optional): a dictionary of contents to write to the file; if not provided,
            defaults will be used
    """
    path = Path(path)
    prefect_file = path / "prefect.yaml"
    if prefect_file.exists():
        return False
    default_file = Path(__file__).parent / "templates" / "prefect.yaml"

    with default_file.open(mode="r") as df:
        default_contents = yaml.safe_load(df)

    import prefect

    contents["prefect-version"] = prefect.__version__
    contents["name"] = name

    with prefect_file.open(mode="w") as f:
        # write header
        f.write(
            "# Welcome to your prefect.yaml file! You can use this file for storing and"
            " managing\n# configuration for deploying your flows. We recommend"
            " committing this file to source\n# control along with your flow code.\n\n"
        )

        f.write("# Generic metadata about this project\n")
        yaml.dump({"name": contents["name"]}, f, sort_keys=False)
        yaml.dump({"prefect-version": contents["prefect-version"]}, f, sort_keys=False)
        f.write("\n")

        # build
        f.write("# build section allows you to manage and build docker images\n")
        yaml.dump(
            {"build": contents.get("build", default_contents.get("build"))},
            f,
            sort_keys=False,
        )
        f.write("\n")

        # push
        f.write(
            "# push section allows you to manage if and how this project is uploaded to"
            " remote locations\n"
        )
        yaml.dump(
            {"push": contents.get("push", default_contents.get("push"))},
            f,
            sort_keys=False,
        )
        f.write("\n")

        # pull
        f.write(
            "# pull section allows you to provide instructions for cloning this project"
            " in remote locations\n"
        )
        yaml.dump(
            {"pull": contents.get("pull", default_contents.get("pull"))},
            f,
            sort_keys=False,
        )
        f.write("\n")

        # deployments
        f.write(
            "# the deployments section allows you to provide configuration for"
            " deploying flows\n"
        )
        yaml.dump(
            {
                "deployments": contents.get(
                    "deployments", default_contents.get("deployments")
                )
            },
            f,
            sort_keys=False,
        )

    return True


def configure_project_by_recipe(
    recipe: str, **formatting_kwargs: Any
) -> dict[str, Any] | type[NotSet]:
    """
    Given a recipe name, returns a dictionary representing base configuration options.

    Args:
        recipe (str): the name of the recipe to use
        formatting_kwargs (dict, optional): additional keyword arguments to format the recipe

    Raises:
        ValueError: if provided recipe name does not exist.
    """
    # load the recipe
    recipe_path = Path(__file__).parent / "recipes" / recipe / "prefect.yaml"

    if not recipe_path.exists():
        raise ValueError(f"Unknown recipe {recipe!r} provided.")

    with recipe_path.open(mode="r") as f:
        config: dict[str, Any] = yaml.safe_load(f)

    templated_config = apply_values(
        template=config, values=formatting_kwargs, remove_notset=False
    )

    return templated_config


def initialize_project(
    name: Optional[str] = None,
    recipe: Optional[str] = None,
    inputs: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """
    Initializes a basic project structure with base files.  If no name is provided, the name
    of the current directory is used.  If no recipe is provided, one is inferred.

    Args:
        name (str, optional): the name of the project; if not provided, the current directory name
        recipe (str, optional): the name of the recipe to use; if not provided, one is inferred
        inputs (dict, optional): a dictionary of inputs to use when formatting the recipe

    Returns:
        List[str]: a list of files / directories that were created
    """
    # determine if in git repo or use directory name as a default
    is_git_based = False
    formatting_kwargs = {"directory": str(Path(".").absolute().resolve())}
    dir_name = os.path.basename(os.getcwd())

    remote_url = get_git_remote_origin_url()
    if remote_url:
        formatting_kwargs["repository"] = remote_url
        is_git_based = True
        branch = get_git_branch()
        formatting_kwargs["branch"] = branch or "main"

    formatting_kwargs["name"] = dir_name

    has_dockerfile = Path("Dockerfile").exists()

    if has_dockerfile:
        formatting_kwargs["dockerfile"] = "Dockerfile"
    elif recipe is not None and "docker" in recipe:
        formatting_kwargs["dockerfile"] = "auto"

    # hand craft a pull step
    if is_git_based and recipe is None:
        if has_dockerfile:
            recipe = "docker-git"
        else:
            recipe = "git"
    elif recipe is None and has_dockerfile:
        recipe = "docker"
    elif recipe is None:
        recipe = "local"

    formatting_kwargs.update(inputs or {})
    configuration = configure_project_by_recipe(recipe=recipe, **formatting_kwargs)

    project_name = name or dir_name

    files = []
    if create_default_ignore_file("."):
        files.append(".prefectignore")
    if create_default_prefect_yaml(".", name=project_name, contents=configuration):
        files.append("prefect.yaml")

    return files


def _format_deployment_for_saving_to_prefect_file(
    deployment: dict[str, Any],
) -> dict[str, Any]:
    """
    Formats a deployment into a templated deploy config for saving to prefect.yaml.

    Args:
        - deployment (Dict): a dictionary containing an untemplated deployment configuration

    Returns:
        - deployment (Dict): a dictionary containing a templated deployment configuration
    """
    if not deployment:
        raise ValueError("Deployment must be a non-empty dictionary.")
    deployment = deepcopy(deployment)
    # Parameter schema is not stored in prefect.yaml
    deployment.pop("parameter_openapi_schema")
    # Only want entrypoint to avoid errors
    deployment.pop("flow_name", None)

    if deployment.get("schedules"):
        schedules: list[dict[str, Any]] = []
        for deployment_schedule in deployment["schedules"]:
            if isinstance(deployment_schedule.schedule, IntervalSchedule):
                schedule_config = _interval_schedule_to_dict(
                    deployment_schedule.schedule
                )
            else:  # all valid SCHEDULE_TYPES are subclasses of BaseModel
                schedule_config = deployment_schedule.schedule.model_dump()

            schedule_config["active"] = deployment_schedule.active
            schedules.append(schedule_config)

        deployment["schedules"] = schedules

    if deployment.get("concurrency_limit"):
        concurrency_limit = deployment["concurrency_limit"]
        if isinstance(concurrency_limit, dict):
            if isinstance(
                concurrency_limit["collision_strategy"], ConcurrencyLimitStrategy
            ):
                concurrency_limit["collision_strategy"] = str(
                    concurrency_limit["collision_strategy"].value
                )
        deployment["concurrency_limit"] = concurrency_limit

    return deployment


def _interval_schedule_to_dict(schedule: IntervalSchedule) -> dict[str, Any]:
    """
    Converts an IntervalSchedule to a dictionary.

    Args:
        - schedule (IntervalSchedule): the schedule to convert

    Returns:
        - dict[str, Any]: the schedule as a dictionary
    """
    schedule_config = schedule.model_dump()
    schedule_config["interval"] = schedule_config["interval"].total_seconds()
    schedule_config["anchor_date"] = schedule_config["anchor_date"].isoformat()

    return schedule_config


def _save_deployment_to_prefect_file(
    deployment: dict[str, Any],
    build_steps: list[dict[str, Any]] | None = None,
    push_steps: list[dict[str, Any]] | None = None,
    pull_steps: list[dict[str, Any]] | None = None,
    triggers: list[dict[str, Any]] | None = None,
    sla: list[dict[str, Any]] | None = None,
    prefect_file: Path = Path("prefect.yaml"),
):
    """
    Save a deployment configuration to the `prefect.yaml` file in the
    current directory.

    Will create a prefect.yaml file if one does not already exist.

    Args:
        - deployment: a dictionary containing a deployment configuration
    """
    deployment = _format_deployment_for_saving_to_prefect_file(deployment)

    current_directory_name = os.path.basename(os.getcwd())
    if not prefect_file.exists():
        if triggers:
            deployment["triggers"] = triggers
        if sla:
            deployment["sla"] = sla
        create_default_prefect_yaml(
            ".",
            current_directory_name,
            contents={
                "deployments": [deployment],
                "build": build_steps,
                "push": push_steps,
                "pull": pull_steps,
            },
        )
        create_default_ignore_file(".")
    else:
        # use ruamel.yaml to preserve comments
        ryaml = YAML()
        with prefect_file.open(mode="r") as f:
            parsed_prefect_file_contents = ryaml.load(f)

        if build_steps != parsed_prefect_file_contents.get("build"):
            deployment["build"] = build_steps

        if push_steps != parsed_prefect_file_contents.get("push"):
            deployment["push"] = push_steps

        if pull_steps != parsed_prefect_file_contents.get("pull"):
            deployment["pull"] = pull_steps

        if triggers and triggers != parsed_prefect_file_contents.get("triggers"):
            deployment["triggers"] = triggers

        if sla and sla != parsed_prefect_file_contents.get("sla"):
            deployment["sla"] = sla

        deployments = parsed_prefect_file_contents.get("deployments")
        if deployments is None:
            parsed_prefect_file_contents["deployments"] = [deployment]
        else:
            for i, existing_deployment in enumerate(deployments):
                if existing_deployment.get("name") == deployment.get("name") and (
                    existing_deployment.get("entrypoint")
                    == deployment.get("entrypoint")
                ):
                    deployments[i] = deployment
                    break
            else:
                deployments.append(deployment)

        with prefect_file.open(mode="w") as f:
            ryaml.dump(parsed_prefect_file_contents, f)

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import ValidationError
from yaml.error import YAMLError

import prefect.cli.root as root
from prefect.cli.root import app
from prefect.utilities.annotations import NotSet

from ._models import PrefectYamlModel


def _format_validation_error(exc: ValidationError, raw_data: dict[str, Any]) -> str:
    """Format Pydantic validation errors into user-friendly messages."""
    deployment_errors: dict[str, set[str]] = {}
    top_level_errors: list[tuple[str, str]] = []

    for error in exc.errors():
        loc = error.get("loc", ())
        msg = error.get("msg", "Invalid value")

        # Handle deployment-level errors
        if len(loc) >= 2 and loc[0] == "deployments" and isinstance(loc[1], int):
            idx = loc[1]
            deployments = raw_data.get("deployments", [])
            name = (
                deployments[idx].get("name", f"#{idx}")
                if idx < len(deployments)
                else f"#{idx}"
            )

            # Get field path (only include string field names, not indices or type names)
            field_parts = []
            for part in loc[2:]:
                if isinstance(part, str) and not part.startswith("function-"):
                    # Assume lowercase names are field names, not type names
                    if part[0].islower():
                        field_parts.append(part)

            if field_parts:
                field = field_parts[0]  # Just use the top-level field
                if name not in deployment_errors:
                    deployment_errors[name] = set()
                deployment_errors[name].add(field)
        # Handle top-level field errors (prefect-version, name, build, push, pull, etc.)
        elif len(loc) >= 1 and isinstance(loc[0], str):
            field_name = loc[0]
            top_level_errors.append((field_name, msg))

    if not deployment_errors and not top_level_errors:
        return "Validation error in config file"

    lines = []

    # Format top-level errors
    if top_level_errors:
        lines.append("Invalid top-level fields in config file:\n")
        for field_name, msg in top_level_errors:
            lines.append(f"  • {field_name}: {msg}")
        lines.append(
            "\nFor valid prefect.yaml fields, see: https://docs.prefect.io/v3/how-to-guides/deployments/prefect-yaml"
        )

    # Format deployment-level errors
    if deployment_errors:
        if top_level_errors:
            lines.append("")  # blank line separator
        lines.append("Invalid fields in deployments:\n")
        for name, fields in sorted(deployment_errors.items()):
            lines.append(f"  • {name}: {', '.join(sorted(fields))}")
        lines.append(
            "\nFor valid deployment fields and examples, go to: https://docs.prefect.io/v3/concepts/deployments#deployment-schema"
        )

    return "\n".join(lines)


def _merge_with_default_deploy_config(deploy_config: dict[str, Any]) -> dict[str, Any]:
    deploy_config = deepcopy(deploy_config)
    DEFAULT_DEPLOY_CONFIG: dict[str, Any] = {
        "name": None,
        "version": None,
        "tags": [],
        "concurrency_limit": None,
        "description": None,
        "flow_name": None,
        "entrypoint": None,
        "parameters": {},
        "work_pool": {
            "name": None,
            "work_queue_name": None,
            "job_variables": {},
        },
    }

    for key, value in DEFAULT_DEPLOY_CONFIG.items():
        if key not in deploy_config:
            deploy_config[key] = value
        if isinstance(value, dict):
            for k, v in value.items():
                if k not in deploy_config[key]:
                    deploy_config[key][k] = v

    return deploy_config


def _load_deploy_configs_and_actions(
    prefect_file: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Load and validate a prefect.yaml using Pydantic models.

    Returns a tuple of (deployment_configs, actions_dict) where deployments are
    dictionaries compatible with existing CLI code and actions contains
    top-level build/push/pull lists from the file.
    """
    raw: dict[str, Any] = {}
    try:
        with prefect_file.open("r") as f:
            loaded = yaml.safe_load(f)
    except (FileNotFoundError, IsADirectoryError, YAMLError) as exc:
        app.console.print(
            f"Unable to read the specified config file. Reason: {exc}. Skipping.",
            style="yellow",
        )
        loaded = {}

    if isinstance(loaded, dict):
        raw = loaded
    else:
        app.console.print(
            "Unable to parse the specified config file. Skipping.",
            style="yellow",
        )

    try:
        model = PrefectYamlModel.model_validate(raw)
    except ValidationError as exc:
        # Format and display validation errors
        error_message = _format_validation_error(exc, raw)
        app.console.print(error_message, style="yellow")
        app.console.print(
            "\nSkipping deployment configuration due to validation errors.",
            style="yellow",
        )
        model = PrefectYamlModel()

    actions: dict[str, Any] = {
        "build": model.build or [],
        "push": model.push or [],
        "pull": model.pull or [],
    }
    # Convert Pydantic models to plain dicts for downstream consumption,
    # excluding keys that were not provided by users to preserve legacy semantics
    deploy_configs: list[dict[str, Any]] = [
        d.model_dump(exclude_unset=True, mode="json") for d in model.deployments
    ]
    return deploy_configs, actions


def _extract_variable(variable: str) -> dict[str, Any]:
    """
    Extracts a variable from a string. Variables can be in the format
    key=value or a JSON object.
    """
    try:
        key, value = variable.split("=", 1)
    except ValueError:
        pass
    else:
        return {key: value}

    try:
        # Only key=value strings and JSON objexcts are valid inputs for
        # variables, not arrays or strings, so we attempt to convert the parsed
        # object to a dict.
        return dict(json.loads(variable))
    except (ValueError, TypeError) as e:
        raise ValueError(
            f'Could not parse variable: "{variable}". Please ensure variables are'
            " either in the format `key=value` or are strings containing a valid JSON"
            " object."
        ) from e


def _apply_cli_options_to_deploy_config(
    deploy_config: dict[str, Any], cli_options: dict[str, Any]
) -> dict[str, Any]:
    """
    Applies CLI options to a deploy config. CLI options take
    precedence over values in the deploy config.

    Args:
        deploy_config: A deploy config
        cli_options: A dictionary of CLI options

    Returns:
        Dict: a deploy config with CLI options applied
    """
    deploy_config = deepcopy(deploy_config)

    # verification
    if cli_options.get("param") and (cli_options.get("params") is not None):
        raise ValueError("Can only pass one of `param` or `params` options")

    # If there's more than one name, we can't set the name of the deploy config.
    # The user will be prompted if running in interactive mode.
    if len(cli_options.get("names", [])) == 1:
        deploy_config["name"] = cli_options["names"][0]

    variable_overrides: dict[str, Any] = {}
    for cli_option, cli_value in cli_options.items():
        if (
            cli_option
            in [
                "description",
                "entrypoint",
                "version",
                "tags",
                "concurrency_limit",
                "flow_name",
                "enforce_parameter_schema",
            ]
            and cli_value is not None
        ):
            deploy_config[cli_option] = cli_value

        elif (
            cli_option in ["work_pool_name", "work_queue_name", "variables"]
            and cli_value
        ):
            if not isinstance(deploy_config.get("work_pool"), dict):
                deploy_config["work_pool"] = {}
            if cli_option == "work_pool_name":
                deploy_config["work_pool"]["name"] = cli_value
            elif cli_option == "variables":
                for variable in cli_value or []:
                    variable_overrides.update(**_extract_variable(variable))
                if not isinstance(deploy_config["work_pool"].get("variables"), dict):
                    deploy_config["work_pool"]["job_variables"] = {}
                deploy_config["work_pool"]["job_variables"].update(variable_overrides)
            else:
                deploy_config["work_pool"][cli_option] = cli_value

        elif cli_option in ["cron", "interval", "rrule"] and cli_value:
            if not isinstance(deploy_config.get("schedules"), list):
                deploy_config["schedules"] = []

            for value in cli_value:
                deploy_config["schedules"].append({cli_option: value})

        elif cli_option in ["param", "params"] and cli_value:
            parameters: dict[str, Any] = {}
            if cli_option == "param":
                for p in cli_value or []:
                    k, unparsed_value = p.split("=", 1)
                    try:
                        v = json.loads(unparsed_value)
                        app.console.print(
                            f"The parameter value {unparsed_value} is parsed as a JSON"
                            " string"
                        )
                    except json.JSONDecodeError:
                        v = unparsed_value
                    parameters[k] = v

            if cli_option == "params" and cli_value is not None:
                parameters = json.loads(cli_value)

            if not isinstance(deploy_config.get("parameters"), dict):
                deploy_config["parameters"] = {}
            deploy_config["parameters"].update(parameters)

    anchor_date = cli_options.get("anchor_date")
    timezone = cli_options.get("timezone")

    # Apply anchor_date and timezone to new and existing schedules
    for schedule_config in deploy_config.get("schedules") or []:
        if anchor_date and schedule_config.get("interval"):
            schedule_config["anchor_date"] = anchor_date
        if timezone:
            schedule_config["timezone"] = timezone

    return deploy_config, variable_overrides


def _handle_pick_deploy_without_name(
    deploy_configs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    from prefect.cli._prompts import prompt_select_from_table

    selectable_deploy_configs = [
        deploy_config for deploy_config in deploy_configs if deploy_config.get("name")
    ]
    if not selectable_deploy_configs:
        return []
    selected_deploy_config = prompt_select_from_table(
        app.console,
        "Would you like to use an existing deployment configuration?",
        [
            {"header": "Name", "key": "name"},
            {"header": "Entrypoint", "key": "entrypoint"},
            {"header": "Description", "key": "description"},
        ],
        selectable_deploy_configs,
        opt_out_message="No, configure a new deployment",
        opt_out_response=None,
    )
    return [selected_deploy_config] if selected_deploy_config else []


def _log_missing_deployment_names(missing_names, matched_deploy_configs, names):
    if missing_names:
        app.console.print(
            (
                "The following deployment(s) could not be found and will not be"
                f" deployed: {', '.join(list(sorted(missing_names)))}"
            ),
            style="yellow",
        )
    if not matched_deploy_configs:
        app.console.print(
            (
                "Could not find any deployment configurations with the given"
                f" name(s): {', '.join(names)}. Your flow will be deployed with a"
                " new deployment configuration."
            ),
            style="yellow",
        )


def _filter_matching_deploy_config(
    name: str, deploy_configs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    matching_deployments: list[dict[str, Any]] = []
    if "/" in name:
        flow_name, deployment_name = name.split("/")
        flow_name = flow_name.replace("-", "_")
        matching_deployments = [
            deploy_config
            for deploy_config in deploy_configs
            if deploy_config.get("name") == deployment_name
            and deploy_config.get("entrypoint", "").split(":")[-1] == flow_name
        ]
    else:
        matching_deployments = [
            deploy_config
            for deploy_config in deploy_configs
            if deploy_config.get("name") == name
        ]
    return matching_deployments


def _parse_name_from_pattern(
    deploy_configs: list[dict[str, Any]], name_pattern: str
) -> list[str]:
    parsed_names: list[str] = []
    name_pattern = re.escape(name_pattern).replace(r"\*", ".*")

    if "/" in name_pattern:
        flow_name, deploy_name = name_pattern.split("/", 1)
        flow_name = (
            re.compile(flow_name.replace("*", ".*"))
            if "*" in flow_name
            else re.compile(flow_name)
        )
        deploy_name = (
            re.compile(deploy_name.replace("*", ".*"))
            if "*" in deploy_name
            else re.compile(deploy_name)
        )
    else:
        flow_name = None
        deploy_name = re.compile(name_pattern.replace("*", ".*"))

    for deploy_config in deploy_configs:
        if not deploy_config.get("entrypoint"):
            continue
        entrypoint = deploy_config.get("entrypoint").split(":")[-1].replace("_", "-")
        deployment_name = deploy_config.get("name")
        flow_match = flow_name.fullmatch(entrypoint) if flow_name else True
        deploy_match = deploy_name.fullmatch(deployment_name)
        if flow_match and deploy_match:
            parsed_names.append(deployment_name)

    return parsed_names


def _handle_pick_deploy_with_name(
    deploy_configs: list[dict[str, Any]],
    names: list[str],
) -> list[dict[str, Any]]:
    from prefect.cli._prompts import prompt_select_from_table

    matched_deploy_configs: list[dict[str, Any]] = []
    deployment_names: list[str] = []
    for name in names:
        matching_deployments = _filter_matching_deploy_config(name, deploy_configs)

        if len(matching_deployments) > 1 and root.is_interactive():
            user_selected_matching_deployment = prompt_select_from_table(
                app.console,
                (
                    "Found multiple deployment configurations with the name"
                    f" [yellow]{name}[/yellow]. Please select the one you would"
                    " like to deploy:"
                ),
                [
                    {"header": "Name", "key": "name"},
                    {"header": "Entrypoint", "key": "entrypoint"},
                    {"header": "Description", "key": "description"},
                ],
                matching_deployments,
            )
            matched_deploy_configs.append(user_selected_matching_deployment)
        elif matching_deployments:
            matched_deploy_configs.extend(matching_deployments)

        deployment_names.append(name.split("/")[-1])

    unfound_names = set(deployment_names) - {
        deploy_config.get("name") for deploy_config in matched_deploy_configs
    }
    _log_missing_deployment_names(unfound_names, matched_deploy_configs, names)

    return matched_deploy_configs


def _pick_deploy_configs(
    deploy_configs: list[dict[str, Any]],
    names: Optional[list[str]] = None,
    deploy_all: bool = False,
) -> list[dict[str, Any]]:
    names = names or []

    if deploy_all and names:
        raise ValueError(
            "Cannot use both `--all` and `--name` at the same time. Use only one."
        )

    if not deploy_configs:
        if not root.is_interactive():
            return [
                _merge_with_default_deploy_config({}),
            ]
        selected_deploy_config = _handle_pick_deploy_without_name(deploy_configs)
        if not selected_deploy_config:
            return [
                _merge_with_default_deploy_config({}),
            ]
        return selected_deploy_config

    # Original behavior (pre-refactor): in non-interactive mode, if there is
    # exactly one deploy config and at most one name provided, proceed with the
    # single deploy config even if the provided name does not match. This allows
    # users/tests to override the name via CLI while still inheriting templated
    # fields (e.g., version, tags, description) from the config.
    if (not root.is_interactive()) and len(deploy_configs) == 1 and len(names) <= 1:
        return [
            _merge_with_default_deploy_config(deploy_configs[0]),
        ]

    if not names and not deploy_all:
        if not root.is_interactive():
            if len(deploy_configs) == 1:
                return [
                    _merge_with_default_deploy_config(deploy_configs[0]),
                ]
            # Mirror original behavior: error when multiple configs present and no
            # explicit name provided in non-interactive mode.
            raise ValueError(
                "Discovered one or more deployment configurations, but no name was"
                " given. Please specify the name of at least one deployment to"
                " create or update."
            )
        selected_deploy_config = _handle_pick_deploy_without_name(deploy_configs)
        if not selected_deploy_config:
            return [
                _merge_with_default_deploy_config({}),
            ]
        return selected_deploy_config

    if names:
        matched_deploy_configs = _handle_pick_deploy_with_name(deploy_configs, names)
        return matched_deploy_configs

    if deploy_all:
        return [
            _merge_with_default_deploy_config(deploy_config)
            for deploy_config in deploy_configs
        ]

    raise ValueError("Invalid selection. Please try again.")


def _handle_deprecated_schedule_fields(deploy_config: dict[str, Any]):
    deploy_config = deepcopy(deploy_config)

    legacy_schedule = deploy_config.get("schedule", NotSet)
    schedule_configs = deploy_config.get("schedules", NotSet)

    if (
        legacy_schedule
        and legacy_schedule is not NotSet
        and schedule_configs is not NotSet
    ):
        raise ValueError(
            "Both 'schedule' and 'schedules' keys are present in the deployment"
            " configuration. Please use only use `schedules`."
        )

    if legacy_schedule and isinstance(legacy_schedule, dict):
        deploy_config["schedules"] = [deploy_config["schedule"]]

    return deploy_config

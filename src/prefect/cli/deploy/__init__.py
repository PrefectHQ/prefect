"""Deploy CLI package (strict refactor).

This package preserves the original `prefect.cli.deploy` API while organizing
the implementation into a package. We explicitly import and re-expose symbols
so external imports and monkeypatch paths remain unchanged.
"""

# Re-export interactive flags and prompt so tests can monkeypatch
from prefect.cli.root import is_interactive  # noqa: F401
from prefect.cli._prompts import (  # noqa: F401
    prompt,
    confirm,
    prompt_build_custom_docker_image,
    prompt_entrypoint,
    prompt_push_custom_docker_image,
    prompt_schedules,
    prompt_select_blob_storage_credentials,
    prompt_select_from_table,
    prompt_select_remote_flow_storage,
    prompt_select_work_pool,
)

# Public commands
from .commands import deploy, init  # noqa: F401

# Internal helpers and adapters (re-exported to keep tests/monkeypatching stable)
from .storage import _PullStepStorage  # noqa: F401
from .schedules import (  # noqa: F401
    _construct_schedules,
    _schedule_config_to_deployment_schedule,
)
from .config import (  # noqa: F401
    _merge_with_default_deploy_config,
    _load_deploy_configs_and_actions,
    _apply_cli_options_to_deploy_config,
    _handle_pick_deploy_without_name,
    _log_missing_deployment_names,
    _filter_matching_deploy_config,
    _parse_name_from_pattern,
    _handle_pick_deploy_with_name,
    _pick_deploy_configs,
    _extract_variable,
)
from .triggers import (  # noqa: F401
    DeploymentTriggerAdapter,
    _initialize_deployment_triggers,
    _gather_deployment_trigger_definitions,
    _create_deployment_triggers,
)
from .sla import (  # noqa: F401
    SlaAdapter,
    _gather_deployment_sla_definitions,
    _initialize_deployment_slas,
    _create_slas,
)
from .actions import (  # noqa: F401
    _generate_default_pull_action,
    _generate_actions_for_remote_flow_storage,
    _check_for_build_docker_image_step,
    _generate_pull_step_for_build_docker_image,
    _generate_git_clone_pull_step,
)
from .core import (  # noqa: F401
    _run_single_deploy,
    _run_multi_deploy,
)

__all__ = [
    "deploy",
    "init",
    "DeploymentTriggerAdapter",
    "SlaAdapter",
]

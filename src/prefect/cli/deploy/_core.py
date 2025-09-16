from __future__ import annotations

import inspect
import os
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from rich.panel import Panel

import prefect.cli.root as root
from prefect.cli._prompts import (
    confirm,
    prompt,
    prompt_build_custom_docker_image,
    prompt_entrypoint,
    prompt_push_custom_docker_image,
    prompt_select_work_pool,
)
from prefect.cli.root import app
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import WorkerFilter
from prefect.deployments.base import _save_deployment_to_prefect_file
from prefect.deployments.runner import RunnerDeployment
from prefect.deployments.steps.core import run_steps
from prefect.exceptions import ObjectNotFound
from prefect.flows import load_flow_from_entrypoint
from prefect.settings import PREFECT_UI_URL
from prefect.utilities.callables import parameter_schema
from prefect.utilities.collections import get_from_dict
from prefect.utilities.templating import (
    apply_values,
    resolve_block_document_references,
    resolve_variables,
)

from ._actions import (
    _generate_actions_for_remote_flow_storage,
    _generate_default_pull_action,
)
from ._config import (
    _apply_cli_options_to_deploy_config,
    _handle_deprecated_schedule_fields,
    _merge_with_default_deploy_config,
)
from ._models import DeploymentConfig
from ._schedules import _construct_schedules
from ._sla import (
    _create_slas,
    _gather_deployment_sla_definitions,
    _initialize_deployment_slas,
)
from ._storage import _PullStepStorage
from ._triggers import (
    _create_deployment_triggers,
    _gather_deployment_trigger_definitions,
    _initialize_deployment_triggers,
)

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient


async def _run_single_deploy(
    deploy_config: dict[str, Any],
    actions: dict[str, Any],
    options: dict[str, Any] | None = None,
    client: Optional["PrefectClient"] = None,
    prefect_file: Path = Path("prefect.yaml"),
):
    client = client or get_client()
    deploy_config = deepcopy(deploy_config) if deploy_config else {}
    actions = deepcopy(actions) if actions else {}
    options = deepcopy(options) if options else {}

    # Convert dict to model and apply CLI options using strongly-typed helpers
    model = DeploymentConfig.model_validate(deploy_config or {})
    model = _handle_deprecated_schedule_fields(model)
    model, variable_overrides = _apply_cli_options_to_deploy_config(model, options)

    # Resolve blocks/variables and apply env vars on a dict view, then re-validate
    dd = model.model_dump(exclude_unset=True, mode="json")
    dd = await resolve_block_document_references(dd)
    dd = await resolve_variables(dd)
    dd = apply_values(dd, os.environ, remove_notset=False)
    model = DeploymentConfig.model_validate(dd)

    build_steps = (model.build or actions.get("build")) or []
    push_steps = (model.push or actions.get("push")) or []
    pull_steps = (model.pull or actions.get("pull")) or []

    if not model.entrypoint:
        if not root.is_interactive():
            raise ValueError(
                "An entrypoint must be provided:\n\n"
                " \t[yellow]prefect deploy path/to/file.py:flow_function\n\n"
                "You can also provide an entrypoint in a prefect.yaml file."
            )
        model.entrypoint = await prompt_entrypoint(app.console)

    flow = load_flow_from_entrypoint(model.entrypoint)

    model.flow_name = flow.name

    deployment_name = model.name
    if not deployment_name:
        if not root.is_interactive():
            raise ValueError("A deployment name must be provided.")
        model.name = prompt("Deployment name", default="default")

    parameter_openapi_schema = parameter_schema(flow)

    work_pool_name = model.work_pool.name if model.work_pool else None

    # determine work pool
    if work_pool_name:
        try:
            work_pool = await client.read_work_pool(work_pool_name)

            # dont allow submitting to prefect-agent typed work pools
            if work_pool.type == "prefect-agent":
                if not root.is_interactive():
                    raise ValueError(
                        "Cannot create a project-style deployment with work pool of"
                        " type 'prefect-agent'. If you wish to use an agent with"
                        " your deployment, please use the `prefect deployment"
                        " build` command."
                    )
                app.console.print(
                    "You've chosen a work pool with type 'prefect-agent' which"
                    " cannot be used for project-style deployments. Let's pick"
                    " another work pool to deploy to."
                )
                if model.work_pool is None:
                    from ._models import WorkPoolConfig

                    model.work_pool = WorkPoolConfig()
                model.work_pool.name = await prompt_select_work_pool(app.console)
        except ObjectNotFound:
            raise ValueError(
                "This deployment configuration references work pool"
                f" {work_pool_name!r} which does not exist. This"
                " means no worker will be able to pick up its runs. You can create a"
                " work pool in the Prefect UI."
            )
    else:
        if not root.is_interactive():
            raise ValueError(
                "A work pool is required to deploy this flow. Please specify a work"
                " pool name via the '--pool' flag or in your prefect.yaml file."
            )
        if model.work_pool is None:
            from ._models import WorkPoolConfig

            model.work_pool = WorkPoolConfig()
        model.work_pool.name = await prompt_select_work_pool(console=app.console)

    docker_build_steps = [
        "prefect_docker.deployments.steps.build_docker_image",
    ]

    docker_push_steps = [
        "prefect_docker.deployments.steps.push_docker_image",
    ]

    docker_build_step_exists = any(
        any(step in action for step in docker_build_steps)
        for action in ((model.build or actions.get("build")) or [])
    )

    update_work_pool_image = False

    build_step_set_to_null = model.build in (None, {}, [])

    work_pool = await client.read_work_pool(model.work_pool.name)

    image_properties = (
        work_pool.base_job_template.get("variables", {})
        .get("properties", {})
        .get("image", {})
    )
    image_is_configurable = (
        "image"
        in work_pool.base_job_template.get("variables", {}).get("properties", {})
        and image_properties.get("type") == "string"
        and not image_properties.get("enum")
    )

    if (
        root.is_interactive()
        and not docker_build_step_exists
        and not build_step_set_to_null
        and image_is_configurable
    ):
        build_docker_image_step = await prompt_build_custom_docker_image(
            app.console, model.model_dump(exclude_unset=True, mode="json")
        )
        if build_docker_image_step is not None:
            if not ((model.work_pool.job_variables or {}).get("image")):
                update_work_pool_image = True

            (
                push_docker_image_step,
                updated_build_docker_image_step,
            ) = await prompt_push_custom_docker_image(
                app.console,
                model.model_dump(exclude_unset=True, mode="json"),
                build_docker_image_step,
            )

            if actions.get("build"):
                actions["build"].append(updated_build_docker_image_step)
            else:
                actions["build"] = [updated_build_docker_image_step]

            if push_docker_image_step is not None:
                if actions.get("push"):
                    actions["push"].append(push_docker_image_step)
                else:
                    actions["push"] = [push_docker_image_step]

        build_steps = (model.build or actions.get("build")) or []
        push_steps = (model.push or actions.get("push")) or []

    docker_push_step_exists = any(
        any(step in action for step in docker_push_steps)
        for action in ((model.push or actions.get("push")) or [])
    )

    ## CONFIGURE PUSH and/or PULL STEPS FOR REMOTE FLOW STORAGE
    if (
        root.is_interactive()
        and not (model.pull or actions.get("pull"))
        and not docker_push_step_exists
        and confirm(
            (
                "Your Prefect workers will need access to this flow's code in order to"
                " run it. Would you like your workers to pull your flow code from a"
                " remote storage location when running this flow?"
            ),
            default=True,
            console=app.console,
        )
    ):
        actions = await _generate_actions_for_remote_flow_storage(
            console=app.console,
            deploy_config=model.model_dump(exclude_unset=True, mode="json"),
            actions=actions,
        )

    if trigger_specs := _gather_deployment_trigger_definitions(
        options.get("triggers"), (model.triggers or [])
    ):
        triggers = _initialize_deployment_triggers(deployment_name, trigger_specs)
    else:
        triggers = []

    # Prefer the originally captured pull_steps (taken before resolution) to
    # preserve unresolved block placeholders in the deployment spec. Only fall
    # back to the config/actions/default if no pull steps were provided.
    pull_steps = (
        pull_steps
        or model.pull
        or actions.get("pull")
        or await _generate_default_pull_action(
            app.console,
            deploy_config=model.model_dump(exclude_unset=True, mode="json"),
            actions=actions,
        )
    )

    ## RUN BUILD AND PUSH STEPS
    step_outputs: dict[str, Any] = {}
    if build_steps:
        app.console.print("Running deployment build steps...")
        step_outputs.update(
            await run_steps(build_steps, step_outputs, print_function=app.console.print)
        )

    if push_steps := push_steps or actions.get("push"):
        app.console.print("Running deployment push steps...")
        step_outputs.update(
            await run_steps(push_steps, step_outputs, print_function=app.console.print)
        )

    step_outputs.update(variable_overrides)

    if update_work_pool_image:
        if "build-image" not in step_outputs:
            app.console.print(
                "Warning: no build-image step found in the deployment build steps."
                " The work pool image will not be updated."
            )
        job_vars = model.work_pool.job_variables or {}
        job_vars["image"] = "{{ build-image.image }}"
        model.work_pool.job_variables = job_vars

    if not model.description:
        model.description = flow.description

    schedules = _construct_schedules(
        model.model_dump(exclude_unset=True, mode="json"), step_outputs
    )

    # save deploy_config before templating
    deploy_config_before_templating = model.model_dump(exclude_unset=True, mode="json")
    ## apply templating from build and push steps to the final deployment spec
    # Apply templating from build/push outputs to the final spec
    dd = model.model_dump(exclude_unset=True, mode="json")
    dd = apply_values(dd, step_outputs, warn_on_notset=True)
    dd["parameter_openapi_schema"] = parameter_openapi_schema
    dd["schedules"] = schedules

    if isinstance(dd.get("concurrency_limit"), dict):
        dd["concurrency_options"] = {
            "collision_strategy": get_from_dict(
                dd, "concurrency_limit.collision_strategy"
            )
        }
        dd["concurrency_limit"] = get_from_dict(dd, "concurrency_limit.limit")

    # Ensure legacy defaults are present for downstream objects (e.g., parameters {})
    dd = _merge_with_default_deploy_config(dd)

    pull_steps = apply_values(pull_steps, step_outputs, remove_notset=False)

    deployment = RunnerDeployment(
        name=dd["name"],
        flow_name=dd.get("flow_name"),
        entrypoint=dd.get("entrypoint"),
        work_pool_name=get_from_dict(dd, "work_pool.name"),
        work_queue_name=get_from_dict(dd, "work_pool.work_queue_name"),
        parameters=dd.get("parameters"),
        description=dd.get("description"),
        version=dd.get("version") or options.get("version"),
        version_type=dd.get("version_type") or options.get("version_type"),
        tags=dd.get("tags"),
        concurrency_limit=dd.get("concurrency_limit"),
        concurrency_options=dd.get("concurrency_options"),
        paused=dd.get("paused"),
        storage=_PullStepStorage(pull_steps),
        job_variables=get_from_dict(dd, "work_pool.job_variables"),
    )

    deployment._set_defaults_from_flow(flow)

    deployment._parameter_openapi_schema = dd["parameter_openapi_schema"]

    if dd.get("enforce_parameter_schema") is not None:
        deployment.enforce_parameter_schema = dd.get("enforce_parameter_schema")

    apply_coro = deployment.apply(schedules=dd.get("schedules"))
    if TYPE_CHECKING:
        assert inspect.isawaitable(apply_coro)

    deployment_id = await apply_coro

    await _create_deployment_triggers(client, deployment_id, triggers)

    # # We want to ensure that if a user passes an empty list of SLAs, we call the
    # # apply endpoint to remove existing SLAs for the deployment.
    # # If the argument is not provided, we will not call the endpoint.
    # Import SLA helpers from the package namespace to honor test monkeypatches
    sla_specs = _gather_deployment_sla_definitions(options.get("sla"), dd.get("sla"))
    if sla_specs is not None:
        slas = _initialize_deployment_slas(deployment_id, sla_specs)
        await _create_slas(client, deployment_id, slas)

    app.console.print(
        Panel(
            f"Deployment '{dd['flow_name']}/{dd['name']}'"
            f" successfully created with id '{deployment_id}'."
        ),
        style="green",
    )

    if PREFECT_UI_URL:
        message = (
            "\nView Deployment in UI:"
            f" {PREFECT_UI_URL.value()}/deployments/deployment/{deployment_id}\n"
        )
        app.console.print(message, soft_wrap=True)

    if root.is_interactive() and not prefect_file.exists():
        if confirm(
            (
                "Would you like to save configuration for this deployment for faster"
                " deployments in the future?"
            ),
            console=app.console,
        ):
            deploy_config_before_templating.update({"schedules": schedules})
            _save_deployment_to_prefect_file(
                deploy_config_before_templating,
                build_steps=build_steps or None,
                push_steps=push_steps or None,
                pull_steps=pull_steps or None,
                triggers=trigger_specs or None,
                sla=sla_specs or None,
                prefect_file=prefect_file,
            )
            app.console.print(
                (
                    f"\n[green]Deployment configuration saved to {prefect_file}![/]"
                    " You can now deploy using this deployment configuration"
                    " with:\n\n\t[blue]$ prefect deploy -n"
                    f" {dd['name']}[/]\n\nYou can also make changes to"
                    " this deployment configuration by making changes to the"
                    " YAML file."
                ),
            )
    active_workers = []
    if work_pool_name:
        active_workers = await client.read_workers_for_work_pool(
            work_pool_name, worker_filter=WorkerFilter(status={"any_": ["ONLINE"]})
        )

    if (
        not work_pool.is_push_pool
        and not work_pool.is_managed_pool
        and not active_workers
    ):
        app.console.print(
            "\nTo execute flow runs from these deployments, start a worker in a"
            " separate terminal that pulls work from the"
            f" {work_pool_name!r} work pool:"
        )
        app.console.print(
            f"\n\t$ prefect worker start --pool {work_pool_name!r}",
            style="blue",
        )
    app.console.print(
        "\nTo schedule a run for this deployment, use the following command:"
    )
    app.console.print(
        (f"\n\t$ prefect deployment run '{dd['flow_name']}/{dd['name']}'\n"),
        style="blue",
    )


async def _run_multi_deploy(
    deploy_configs: list[dict[str, Any]],
    actions: dict[str, Any],
    names: Optional[list[str]] = None,
    deploy_all: bool = False,
    prefect_file: Path = Path("prefect.yaml"),
):
    deploy_configs = deepcopy(deploy_configs) if deploy_configs else []
    actions = deepcopy(actions) if actions else {}
    names = names or []

    if deploy_all:
        app.console.print(
            "Deploying all flows with an existing deployment configuration..."
        )
    else:
        app.console.print("Deploying flows with selected deployment configurations...")
    for deploy_config in deploy_configs:
        if deploy_config.get("name") is None:
            if not root.is_interactive():
                app.console.print(
                    "Discovered unnamed deployment. Skipping...", style="yellow"
                )
                continue
            app.console.print("Discovered unnamed deployment.", style="yellow")
            app.console.print_json(data=deploy_config)
            if confirm(
                "Would you like to give this deployment a name and deploy it?",
                default=True,
                console=app.console,
            ):
                deploy_config["name"] = prompt("Deployment name", default="default")
            else:
                app.console.print("Skipping unnamed deployment.", style="yellow")
                continue
        app.console.print(Panel(f"Deploying {deploy_config['name']}", style="blue"))
        await _run_single_deploy(deploy_config, actions, prefect_file=prefect_file)

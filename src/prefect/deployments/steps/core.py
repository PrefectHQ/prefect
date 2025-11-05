"""
Core primitives for running Prefect deployment steps.

Deployment steps are YAML representations of Python functions along with their inputs.

Whenever a step is run, the following actions are taken:

- The step's inputs and block / variable references are resolved (see [the `prefect deploy` documentation](https://docs.prefect.io/v3/how-to-guides/deployments/prefect-yaml#templating-options) for more details)
- The step's function is imported; if it cannot be found, the `requires` keyword is used to install the necessary packages
- The step's function is called with the resolved inputs
- The step's output is returned and used to resolve inputs for subsequent steps
"""

from __future__ import annotations

import os
import re
import subprocess
import warnings
from copy import deepcopy
from importlib import import_module
from typing import Any
from uuid import UUID

from prefect._internal.compatibility.deprecated import PrefectDeprecationWarning
from prefect._internal.concurrency.api import Call, from_async
from prefect._internal.installation import install_packages
from prefect._internal.integrations import KNOWN_EXTRAS_FOR_PACKAGES
from prefect.events.clients import get_events_client
from prefect.events.schemas.events import Event, RelatedResource, Resource
from prefect.logging.loggers import get_logger
from prefect.settings import PREFECT_DEBUG_MODE
from prefect.utilities.importtools import import_object
from prefect.utilities.templating import (
    apply_values,
    resolve_block_document_references,
    resolve_variables,
)

RESERVED_KEYWORDS = {"id", "requires"}


class StepExecutionError(Exception):
    """
    Raised when a step fails to execute.
    """


def _strip_version(requirement: str) -> str:
    """
    Strips the version from a requirement string.

    Args:
        requirement: A requirement string, e.g. "requests>=2.0.0"

    Returns:
        The package name, e.g. "requests"

    Examples:
        ```python
        _strip_version("s3fs>=2.0.0<3.0.0")
        # "s3fs"
        ```
    """
    # split on any of the characters in the set [<>=!~]
    # and return the first element which will be the package name
    return re.split(r"[<>=!~]", requirement)[0].strip()


def _get_function_for_step(
    fully_qualified_name: str, requires: str | list[str] | None = None
):
    if not isinstance(requires, list):
        packages = [requires] if requires else []
    else:
        packages = requires

    try:
        for package in packages:
            import_module(_strip_version(package).replace("-", "_"))
        step_func = import_object(fully_qualified_name)
        return step_func
    except ImportError:
        if requires:
            print(
                f"Unable to load step function: {fully_qualified_name}. Attempting"
                f" install of {requires}."
            )
        else:
            raise

    try:
        packages = [
            KNOWN_EXTRAS_FOR_PACKAGES.get(package, package)
            for package in packages
            if package
        ]
        install_packages(packages, stream_output=True)

    except subprocess.CalledProcessError:
        get_logger("deployments.steps.core").warning(
            "Unable to install required packages for %s", fully_qualified_name
        )
    step_func = import_object(fully_qualified_name)
    return step_func


async def run_step(
    step: dict[str, Any], upstream_outputs: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Runs a step, returns the step's output.

    Steps are assumed to be in the format `{"importable.func.name": {"kwarg1": "value1", ...}}`.

    The 'id and 'requires' keywords are reserved for specific purposes and will be removed from the
    inputs before passing to the step function:

    This keyword is used to specify packages that should be installed before running the step.
    """
    fqn, inputs = _get_step_fully_qualified_name_and_inputs(step)
    upstream_outputs = upstream_outputs or {}

    if len(step.keys()) > 1:
        raise ValueError(
            f"Step has unexpected additional keys: {', '.join(list(step.keys())[1:])}"
        )

    keywords = {
        keyword: inputs.pop(keyword)
        for keyword in RESERVED_KEYWORDS
        if keyword in inputs
    }

    inputs = apply_values(inputs, upstream_outputs)
    inputs = await resolve_block_document_references(inputs)
    inputs = await resolve_variables(inputs)
    inputs = apply_values(inputs, os.environ)
    step_func = _get_function_for_step(fqn, requires=keywords.get("requires"))
    result = await from_async.call_soon_in_new_thread(
        Call.new(step_func, **inputs)
    ).aresult()
    return result


async def run_steps(
    steps: list[dict[str, Any]],
    upstream_outputs: dict[str, Any] | None = None,
    print_function: Any = print,
    deployment: Any | None = None,
    flow_run: Any | None = None,
    logger: Any | None = None,
) -> dict[str, Any]:
    upstream_outputs = deepcopy(upstream_outputs) if upstream_outputs else {}
    for step_index, step in enumerate(steps):
        if not step:
            continue
        fqn, inputs = _get_step_fully_qualified_name_and_inputs(step)
        step_name = fqn.split(".")[-1]
        print_function(f" > Running {step_name} step...")

        # SECURITY: Serialize inputs BEFORE running the step (and thus before templating).
        # This ensures that the event payload contains template strings like
        # "{{ prefect.blocks.secret.api-key }}" rather than resolved secret values.
        # Templating (which resolves blocks, variables, and env vars) happens inside
        # run_step(), so by serializing here we prevent secrets from leaking in events.
        serialized_step = {
            "index": step_index,
            "qualified_name": fqn,
            "step_name": step_name,
            "id": inputs.get("id"),
            "inputs": inputs,  # Keep all inputs including reserved keywords like 'requires'
        }

        try:
            # catch warnings to ensure deprecation warnings are printed
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter(
                    "always",
                    category=PrefectDeprecationWarning,
                )
                warnings.simplefilter(
                    "always",
                    category=DeprecationWarning,
                )
                step_output = await run_step(step, upstream_outputs)
            if w:
                printed_messages = []
                for warning in w:
                    message = str(warning.message)
                    # prevent duplicate warnings from being printed
                    if message not in printed_messages:
                        try:
                            # try using rich styling
                            print_function(message, style="yellow")
                        except Exception:
                            # default to printing without styling
                            print_function(message)
                        printed_messages.append(message)

            if not isinstance(step_output, dict):
                if PREFECT_DEBUG_MODE:
                    get_logger().warning(
                        "Step function %s returned unexpected type: %s",
                        fqn,
                        type(step_output),
                    )
                continue
            # store step output under step id to prevent clobbering
            if inputs.get("id"):
                upstream_outputs[inputs.get("id")] = step_output
            upstream_outputs.update(step_output)

            # Emit success event for this step
            await _emit_pull_step_event(
                serialized_step,
                event_type="prefect.flow-run.pull-step.executed",
                deployment=deployment,
                flow_run=flow_run,
                logger=logger,
            )
        except Exception as exc:
            # Emit failure event for this step
            await _emit_pull_step_event(
                serialized_step,
                event_type="prefect.flow-run.pull-step.failed",
                deployment=deployment,
                flow_run=flow_run,
                logger=logger,
            )
            raise StepExecutionError(f"Encountered error while running {fqn}") from exc

    return upstream_outputs


def _get_step_fully_qualified_name_and_inputs(step: dict) -> tuple[str, dict]:
    step = deepcopy(step)
    return step.popitem()


async def _emit_pull_step_event(
    serialized_step: dict[str, Any],
    *,
    event_type: str,
    deployment: Any | None = None,
    flow_run: Any | None = None,
    logger: Any | None = None,
) -> None:
    # Get flow_run_id from flow_run param or environment
    flow_run_id = None
    if flow_run:
        flow_run_id = flow_run.id
    else:
        # Read directly from environment variable
        flow_run_id_str = os.getenv("PREFECT__FLOW_RUN_ID")
        if flow_run_id_str:
            flow_run_id = UUID(flow_run_id_str)

    if not flow_run_id:
        return

    # Build related resources
    related: list[RelatedResource] = []
    if deployment:
        related.append(
            RelatedResource(
                {
                    "prefect.resource.id": f"prefect.deployment.{deployment.id}",
                    "prefect.resource.role": "deployment",
                }
            )
        )

    try:
        # Use events client directly with checkpoint_every=1 to avoid buffering issues
        async with get_events_client(checkpoint_every=1) as events_client:
            await events_client.emit(
                Event(
                    event=event_type,
                    resource=Resource(
                        {
                            "prefect.resource.id": f"prefect.flow-run.{flow_run_id}",
                        }
                    ),
                    related=related,
                    payload=serialized_step,
                )
            )
    except Exception:
        if logger:
            logger.warning(
                "Failed to emit pull-step event for flow run %s", flow_run_id
            )
        else:
            get_logger(__name__).warning(
                "Failed to emit pull-step event for flow run %s", flow_run_id
            )

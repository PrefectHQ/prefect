"""
Core primitives for running Prefect project steps.

Project steps are YAML representations of Python functions along with their inputs.

Whenever a step is run, the following actions are taken:

- The step's inputs and block / variable references are resolved (see [the projects concepts documentation](/concepts/projects/#templating-options) for more details)
- The step's function is imported; if it cannot be found, the `requires` keyword is used to install the necessary packages
- The step's function is called with the resolved inputs
- The step's output is returned and used to resolve inputs for subsequent steps
"""
from copy import deepcopy
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple
import warnings

from prefect._internal.concurrency.api import Call, from_async
from prefect.utilities.importtools import import_object
from prefect.utilities.templating import (
    apply_values,
    resolve_block_document_references,
    resolve_variables,
)
from prefect._internal.compatibility.deprecated import PrefectDeprecationWarning

from prefect.settings import PREFECT_DEBUG_MODE

from prefect.logging.loggers import get_logger

RESERVED_KEYWORDS = {"id", "requires"}


class StepExecutionError(Exception):
    """
    Raised when a step fails to execute.
    """


def _get_function_for_step(fully_qualified_name: str, requires: Optional[str] = None):
    try:
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

    if not isinstance(requires, list):
        packages = [requires]
    else:
        packages = requires

    subprocess.check_call([sys.executable, "-m", "pip", "install", ",".join(packages)])
    step_func = import_object(fully_qualified_name)
    return step_func


async def run_step(step: Dict, upstream_outputs: Optional[Dict] = None) -> Dict:
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
    steps: List[Dict[str, Any]],
    upstream_outputs: Optional[Dict[str, Any]] = None,
    print_function: Any = print,
):
    upstream_outputs = deepcopy(upstream_outputs) if upstream_outputs else {}
    for step in steps:
        if not step:
            continue
        fqn, inputs = _get_step_fully_qualified_name_and_inputs(step)
        step_name = fqn.split(".")[-1]
        print_function(f" > Running {step_name} step...")
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
        except Exception as exc:
            raise StepExecutionError(f"Encountered error while running {fqn}") from exc
    return upstream_outputs


def _get_step_fully_qualified_name_and_inputs(step: Dict) -> Tuple[str, Dict]:
    step = deepcopy(step)
    return step.popitem()

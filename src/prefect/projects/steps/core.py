"""
Core primitives for managing Prefect projects.
"""
import subprocess
import sys
from typing import Optional

from prefect.utilities.importtools import import_object
from prefect.utilities.templating import (
    resolve_block_document_references,
    resolve_variables,
)

RESERVED_KEYWORDS = {"requires"}


def _get_function_for_step(fully_qualified_name: str, requires: Optional[str] = None):
    try:
        step_func = import_object(fully_qualified_name)
        return step_func
    except ImportError:
        if requires:
            print(
                "Unable to load step function: {fully_qualified_name}. Attempting"
                " install of {requires}."
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


async def run_step(step: dict) -> dict:
    """
    Runs a step, returns the step's output.

    Steps are assumed to be in the format {"importable.func.name": {"kwarg1": "value1", ...}}

    The following keywords are reserved for specific purposes and will be removed from the
    inputs before passing to the step function:
        requires: A package or list of packages needed to run the step function. If the step
            function cannot be imported, the packages will be installed and the step function
            will be re-imported.
    """
    fqn, inputs = step.popitem()

    if step:
        raise ValueError(
            f"Step has unexpected additional keys: {', '.join(step.keys())}"
        )

    keywords = {
        keyword: inputs.pop(keyword)
        for keyword in RESERVED_KEYWORDS
        if keyword in inputs
    }

    inputs = await resolve_block_document_references(inputs)
    inputs = await resolve_variables(inputs)

    step_func = _get_function_for_step(fqn, requires=keywords.get("requires"))
    return step_func(**inputs)

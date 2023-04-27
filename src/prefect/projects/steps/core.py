"""
Core primitives for running Prefect project steps.

Project steps are YAML representations of Python functions along with their inputs.

Whenever a step is run, the following actions are taken:

- The step's inputs and block / variable references are resolved (see [the projects concepts documentation](/concepts/projects/#templating-options) for more details)
- The step's function is imported; if it cannot be found, the `requires` keyword is used to install the necessary packages
- The step's function is called with the resolved inputs
- The step's output is returned and used to resolve inputs for subsequent steps
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


async def run_step(step: dict) -> dict:
    """
    Runs a step, returns the step's output.

    Steps are assumed to be in the format `{"importable.func.name": {"kwarg1": "value1", ...}}`.

    The 'requires' keyword is reserved for specific purposes and will be removed from the
    inputs before passing to the step function:

    This keyword is used to specify packages that should be installed before running the step.
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

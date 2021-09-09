import os
from contextlib import nullcontext
from typing import Any, Dict

from prefect.utilities.filesystem import tmpchdir


def exec_script(
    file_path: str,
) -> Dict[str, Any]:
    """
    Execute a python script with __file__ populated if feasible and return the global
    variables
    """
    with open(file_path, "r") as f:
        file_contents = f.read()

    # If a file_path has been provided, provide __file__ as a global variable
    # so it resolves correctly during extraction
    exec_vals: Dict[str, Any] = {
        "__file__": file_path,
        "__name__": os.path.dirname(file_path),
    }

    # Execute the script as if we are in its directory
    with tmpchdir(file_path) if file_path else nullcontext():

        # Compile the code so the file is attached to any traceback frames that arise
        # This allows tracebacks to reference failing lines
        code = compile(
            file_contents,
            filename=os.path.abspath(file_path),
            mode="exec",
        )

        exec(code, exec_vals)

    # Globals from the script will be populated in this dict now
    return exec_vals

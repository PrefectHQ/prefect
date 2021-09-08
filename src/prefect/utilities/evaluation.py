from typing import Any, Dict


def exec_script(
    file_path: str = None,
    file_contents: str = None,
) -> Dict[str, Any]:
    """
    Execute a python script with __file__ populated if feasible and return the global
    variables
    """
    if file_contents is None:
        if file_path is None:
            raise ValueError("Either `file_path` of `file_contents` must be provided")
        with open(file_path, "r") as f:
            file_contents = f.read()

    # If a file_path has been provided, provide __file__ as a global variable
    # so it resolves correctly during extraction
    exec_vals: Dict[str, Any] = {"__file__": file_path} if file_path else {}

    # Load objects from file into the dict
    exec(file_contents, exec_vals)

    return exec_vals

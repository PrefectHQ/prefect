from typing import TYPE_CHECKING

import prefect

if TYPE_CHECKING:
    from prefect.core.flow import Flow  # pylint: disable=W0611


def get_flow_image(flow: "Flow") -> str:
    """
    Retrieve the image to use for this flow deployment. Will start by looking for
    an `image` value in the flow's `environment.metadata`. If not found then it will fall
    back to using the `flow.storage`.

    Args:
        - flow (Flow): A flow object

    Returns:
        - str: a full image name to use for this flow run

    Raises:
        - ValueError: if deployment attempted on unsupported Storage type and `image` not
            present in environment metadata
    """
    environment = flow.environment
    if hasattr(environment, "metadata") and environment.metadata.get("image"):
        return environment.metadata.get("image", "")
    else:
        storage = flow.storage
        if not isinstance(storage, prefect.environments.storage.Docker,):
            raise ValueError(
                f"Storage for flow run {flow.name} is not of type Docker and "
                f"environment has no `image` attribute in the metadata field."
            )

        return storage.name


def extract_flow_from_file(
    file_path: str = None, file_contents: str = None, flow_name: str = None
) -> "Flow":
    """
    Extract a flow object from a file.

    Args:
        - file_path (str, optional): A file path pointing to a .py file containing a flow
        - file_contents (str, optional): The string contents of a .py file containing a flow
        - flow_name (str, optional): A specific name of a flow to extract from a file.
            If not set then the first flow object retrieved from file will be returned.

    Returns:
        - Flow: A flow object extracted from a file

    Raises:
        - ValueError: if both `file_path` and `file_contents` are provided or neither are.
    """
    if file_path and file_contents:
        raise ValueError("Provide either `file_path` or `file_contents` but not both.")

    if not file_path and not file_contents:
        raise ValueError("Provide either `file_path` or `file_contents`.")

    # Read file contents
    if file_path:
        with open(file_path, "r") as f:
            contents = f.read()

    # Use contents directly
    if file_contents:
        contents = file_contents

    # Load objects from file into dict
    exec_vals = {}  # type: ignore
    exec(contents, exec_vals)

    # Grab flow name from values loaded via exec
    for var in exec_vals:
        if isinstance(exec_vals[var], prefect.Flow):
            if flow_name and exec_vals[var].name == flow_name:
                return exec_vals[var]
            elif not flow_name:
                return exec_vals[var]

    raise ValueError("No flow found in file.")

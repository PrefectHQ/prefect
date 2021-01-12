import binascii
import importlib
import json
import sys
import warnings
from operator import attrgetter
from typing import TYPE_CHECKING
from distutils.version import LooseVersion

import cloudpickle

import prefect
from prefect.utilities.exceptions import StorageError

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
    if (
        environment is not None
        and hasattr(environment, "metadata")
        and environment.metadata.get("image")
    ):
        return environment.metadata.get("image", "")
    else:
        storage = flow.storage
        if not isinstance(storage, prefect.storage.Docker):
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


def extract_flow_from_module(module_str: str, flow_name: str = None) -> "Flow":
    """
    Extract a flow object from a python module.

    Args:
        - module_str (str): A module path pointing to a .py file containing a flow.
            For example, 'myrepo.mymodule.myflow' where myflow.py contains the flow.
            Additionally, `:` can be used to access module's attribute, for example,
            'myrepo.mymodule.myflow:flow' or 'myrepo.mymodule.myflow:MyObj.newflow'.
        - flow_name (str, optional): A specific name of a flow to extract from a file.
            If not set then the first flow object retrieved from file will be returned.
            The "first" flow object will be based on the dir(module) ordering, which
            is alphabetical and capitalized letters come first.

    Returns:
        - Flow: A flow object extracted from a file
    """

    # load the module
    module_parts = module_str.split(":", 2)

    if len(module_parts) == 2 and flow_name is not None:
        raise ValueError(
            "Provide either `module_str` without an attribute specifier or remove `flow_name`."
        )
    elif len(module_parts) == 2:
        module_name, flow_name = module_parts
    else:
        module_name = module_str

    module = importlib.import_module(module_name)

    # if flow_name is specified, grab it from the module
    if flow_name:
        attr = attrgetter(flow_name)(module)

        if callable(attr):
            attr = attr()

        if isinstance(attr, prefect.Flow):
            return attr
        else:
            raise ValueError(
                f"{module_name}:{flow_name} must return `prefect.Flow`, not {type(attr)}."
            )
    # otherwise loop until we get a Flow object
    else:
        for var in dir(module):
            attr = getattr(module, var)
            if isinstance(attr, prefect.Flow):
                return attr

    raise ValueError("No flow found in module.")


def flow_to_bytes_pickle(flow: "Flow") -> bytes:
    """Serialize a flow to bytes.

    The flow is serialized using `cloudpickle`, with some extra metadata on
    included via JSON. The flow can be reloaded using `flow_from_bytes_pickle`.

    Args:
        - flow (Flow): the flow to be serialized.

    Returns:
        - bytes: a serialized representation of the flow.
    """
    flow_data = binascii.b2a_base64(
        cloudpickle.dumps(flow, protocol=4), newline=False
    ).decode("utf-8")
    out = json.dumps({"flow": flow_data, "versions": _get_versions()})
    return out.encode("utf-8")


def _get_versions() -> dict:
    """Get version info on libraries where a version-mismatch between
    registration and execution environment may cause a flow to fail to load
    properly"""
    return {
        "cloudpickle": cloudpickle.__version__,
        "prefect": prefect.__version__,
        "python": "%d.%d.%d" % sys.version_info[:3],
    }


def flow_from_bytes_pickle(data: bytes) -> "Flow":
    """Load a flow from bytes."""
    try:
        info = json.loads(data.decode("utf-8"))
    except Exception:
        # Serialized using older version of prefect, use cloudpickle directly
        flow_bytes = data
        reg_versions = {}
    else:
        flow_bytes = binascii.a2b_base64(info["flow"])
        reg_versions = info["versions"]

    run_versions = _get_versions()

    try:
        flow = cloudpickle.loads(flow_bytes)
    except Exception as exc:
        parts = ["An error occurred while unpickling the flow:", f"  {exc!r}"]
        # Check for mismatched versions to provide a better error if possible
        mismatches = []
        for name, v1 in sorted(reg_versions.items()):
            if name in run_versions:
                v2 = run_versions[name]
                if LooseVersion(v1) != v2:
                    mismatches.append(
                        f"  - {name}: (flow built with {v1!r}, currently running with {v2!r})"
                    )
        if mismatches:
            parts.append(
                "This may be due to one of the following version mismatches between "
                "the flow build and execution environments:"
            )
            parts.extend(mismatches)
        if isinstance(exc, ImportError):
            # If it's an import error, also note that the user may need to package
            # their dependencies
            prefix = "This also may" if mismatches else "This may"
            parts.append(
                f"{prefix} be due to a missing Python module in your current "
                "environment. Please ensure you have all required flow "
                "dependencies installed."
            )
        raise StorageError("\n".join(parts)) from exc

    run_prefect = run_versions["prefect"]
    reg_prefect = reg_versions.get("prefect")
    if reg_prefect and LooseVersion(reg_prefect) != run_prefect:
        # If we didn't error above, still check that the prefect versions match
        # and warn if they don't. Prefect version mismatches *may* work, but
        # they may also error later leading to confusing behavior.
        warnings.warn(
            f"This flow was built using Prefect {reg_prefect!r}, but you currently "
            f"have Prefect {run_prefect!r} installed. We recommend loading flows "
            "with the same Prefect version they were built with, failure to do so "
            "may result in errors."
        )
    return flow

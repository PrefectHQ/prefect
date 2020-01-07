"""
A health check script which is intended to be executed inside a user's Docker container
containing their Flow(s).  This class runs through a series of checks to catch possible
deployment issues early on.
"""

import ast
import importlib
import sys
import warnings

import cloudpickle


def system_check(python_version: str):
    python_version = ast.literal_eval(python_version)  # convert string to tuple of ints

    if (
        sys.version_info.minor < python_version[1]
        or sys.version_info.minor > python_version[1]
    ):
        msg = "Your Docker container is using python version {sys_ver}, but your Flow was serialized using {user_ver}; this could lead to unexpected errors in deployment.".format(
            sys_ver=(sys.version_info.major, sys.version_info.minor),
            user_ver=python_version,
        )
        warnings.warn(msg)
    else:
        print("System Version check: OK")


def cloudpickle_deserialization_check(flow_file_paths: str):
    flow_file_paths = ast.literal_eval(
        flow_file_paths
    )  # convert string to list of strings

    flows = []
    for flow_file in flow_file_paths:
        with open(flow_file, "rb") as f:
            flows.append(cloudpickle.load(f))

    print("Cloudpickle serialization check: OK")
    return flows


def environment_dependency_check(flows: list):
    # Test for imports that are required by certain environments
    for flow in flows:
        # Load all required dependencies for an environment
        if not hasattr(flow.environment, "dependencies"):
            continue

        required_imports = flow.environment.dependencies
        for dependency in required_imports:
            try:
                importlib.import_module(dependency)
            except ModuleNotFoundError:
                raise ModuleNotFoundError(
                    "Using {} requires the `{}` dependency".format(
                        flow.environment.__class__.__name__, dependency
                    )
                )

    print("Environment dependency check: OK")


if __name__ == "__main__":
    flow_file_path, python_version = sys.argv[1:3]

    print("Beginning health checks...")
    system_check(python_version)
    flows = cloudpickle_deserialization_check(flow_file_path)
    result_handler_check(flows)
    environment_dependency_check(flows)
    print("All health checks passed.")

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
        msg = (
            "Your Docker container is using python version {sys_ver}, but your Flow was "
            "serialized using {user_ver}; this could lead to unexpected errors in "
            "deployment."
        ).format(
            sys_ver=(sys.version_info.major, sys.version_info.minor),
            user_ver=python_version,
        )
        warnings.warn(msg, stacklevel=2)
    else:
        print("System Version check: OK")


def cloudpickle_deserialization_check(flow_file_paths: list):
    flows = []
    for flow_file in flow_file_paths:
        with open(flow_file, "rb") as f:
            try:
                flows.append(cloudpickle.load(f))
            except ModuleNotFoundError:
                warnings.warn(
                    "Flow uses module which is not importable. Refer to documentation "
                    "on how to import custom modules "
                    "https://docs.prefect.io/api/latest/environments/storage.html#docker",
                    stacklevel=2,
                )
                raise

    print("Cloudpickle serialization check: OK")
    return flows


def import_flow_from_script_check(flow_file_paths: list):
    from prefect.utilities.storage import extract_flow_from_file

    flows = []
    for flow_file_path in flow_file_paths:
        flows.append(extract_flow_from_file(file_path=flow_file_path))

    print("Flow import from script check: OK")
    return flows


def result_check(flows: list):
    for flow in flows:
        if flow.result is not None:
            continue

        # test for tasks which might retry without upstream result handlers
        retry_tasks = [t for t in flow.tasks if t.max_retries > 0]
        upstream_edges = flow.all_upstream_edges()
        for task in retry_tasks:
            if any(
                [
                    e.upstream_task.result is None
                    for e in upstream_edges[task]
                    if e.key is not None
                ]
            ):
                warnings.warn(
                    f"Task {task} has retry settings but some upstream dependencies do not "
                    f"have result types. See https://docs.prefect.io/core/concepts/results.html "
                    f"for more details.",
                    stacklevel=2,
                )

        # test for tasks which request caching with no result handler or no upstream result handlers
        cached_tasks = [t for t in flow.tasks if t.cache_for is not None]
        for task in cached_tasks:
            if task.result is None:
                warnings.warn(
                    f"Task {task} has cache settings but does not have a result type. "
                    f"See https://docs.prefect.io/core/concepts/results.html for more "
                    f"details.",
                    stacklevel=2,
                )
            if any(
                [
                    e.upstream_task.result is None
                    for e in upstream_edges[task]
                    if e.key is not None
                ]
            ):
                warnings.warn(
                    f"Task {task} has cache settings but some upstream dependencies do not have "
                    f"result types. See https://docs.prefect.io/core/concepts/results.html for "
                    f"more details.",
                    stacklevel=2,
                )
    print("Result check: OK")


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
            except ModuleNotFoundError as exc:
                raise ModuleNotFoundError(
                    "Using {} requires the `{}` dependency".format(
                        flow.environment.__class__.__name__, dependency
                    )
                ) from exc

    print("Environment dependency check: OK")


if __name__ == "__main__":
    flow_file_paths, python_version = sys.argv[1:3]

    print("Beginning health checks...")

    flow_file_paths = ast.literal_eval(flow_file_paths)

    system_check(python_version)

    if any(".py" in file_path for file_path in flow_file_paths):
        flows = import_flow_from_script_check(flow_file_paths)
    else:
        flows = cloudpickle_deserialization_check(flow_file_paths)

    result_check(flows)
    environment_dependency_check(flows)
    print("All health checks passed.")

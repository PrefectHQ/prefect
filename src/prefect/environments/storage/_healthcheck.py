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
import prefect


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


def _check_mapped_result_templates(flow: "prefect.Flow"):
    if not any(edge.key and edge.mapped for edge in flow.edges):
        return

    for edge in flow.edges:
        if edge.mapped and edge.key:
            result = edge.downstream_task.result or flow.result
            location = getattr(result, "location", None)
            if location is None:
                continue
            if "{filename}" not in location:
                raise ValueError(
                    "Mapped tasks with custom result locations must include {filename} as a template in their location - see https://docs.prefect.io/core/advanced_tutorials/using-results.html#specifying-a-location-for-mapped-or-looped-tasks"
                )


def result_check(flows: list):
    for flow in flows:
        _check_mapped_result_templates(flow)
        if flow.result is not None:
            continue

        ## test for tasks which might retry without upstream result handlers
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
                raise ValueError(
                    "Task {} has retry settings but some upstream dependencies do not have result types. See https://docs.prefect.io/core/concepts/results.html for more details.".format(
                        task
                    )
                )

        ## test for tasks which request caching with no result handler or no upstream result handlers
        cached_tasks = [t for t in flow.tasks if t.cache_for is not None]
        for task in cached_tasks:
            if task.result is None:
                raise ValueError(
                    "Task {} has cache settings but does not have a result type. See https://docs.prefect.io/core/concepts/results.html for more details.".format(
                        task
                    )
                )
            if any(
                [
                    e.upstream_task.result is None
                    for e in upstream_edges[task]
                    if e.key is not None
                ]
            ):
                raise ValueError(
                    "Task {} has cache settings but some upstream dependencies do not have result types. See https://docs.prefect.io/core/concepts/results.html for more details.".format(
                        task
                    )
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
    result_check(flows)
    environment_dependency_check(flows)
    print("All health checks passed.")

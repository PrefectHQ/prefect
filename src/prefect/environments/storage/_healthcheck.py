"""
A health check script which is intended to be executed inside a user's Docker container
containing their Flow(s).  This class runs through a series of checks to catch possible
deployment issues early on.
"""

import ast
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


def result_handler_check(flows: list):
    for flow in flows:
        if flow.result_handler is not None:
            continue

        ## test for tasks which are checkpointed with no result handler
        if any([(t.checkpoint and t.result_handler is None) for t in flow.tasks]):
            raise ValueError(
                "Some tasks request to be checkpointed but do not have a result handler. See https://docs.prefect.io/core/concepts/results.html for more details."
            )

        ## test for tasks which might retry without upstream result handlers
        retry_tasks = [t for t in flow.tasks if t.max_retries > 0]
        upstream_edges = flow.all_upstream_edges()
        for task in retry_tasks:
            if any(
                [
                    e.upstream_task.result_handler is None
                    for e in upstream_edges[task]
                    if e.key is not None
                ]
            ):
                raise ValueError(
                    "Task {} has retry settings but some upstream dependencies do not have result handlers. See https://docs.prefect.io/core/concepts/results.html for more details.".format(
                        task
                    )
                )

        ## test for tasks which request caching with no result handler or no upstream result handlers
        cached_tasks = [t for t in flow.tasks if t.cache_for is not None]
        for task in cached_tasks:
            if task.result_handler is None:
                raise ValueError(
                    "Task {} has cache settings but does not have a result handler. See https://docs.prefect.io/core/concepts/results.html for more details.".format(
                        task
                    )
                )
            if any(
                [
                    e.upstream_task.result_handler is None
                    for e in upstream_edges[task]
                    if e.key is not None
                ]
            ):
                raise ValueError(
                    "Task {} has cache settings but some upstream dependencies do not have result handlers. See https://docs.prefect.io/core/concepts/results.html for more details.".format(
                        task
                    )
                )
    print("Result Handler check: OK")


if __name__ == "__main__":
    flow_file_path, python_version = sys.argv[1:3]

    print("Beginning health checks...")
    system_check(python_version)
    flows = cloudpickle_deserialization_check(flow_file_path)
    result_handler_check(flows)
    print("All health checks passed.")

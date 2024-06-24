"""A module to define flows interacting with Kubernetes resources."""

import inspect
from typing import Any, Callable, Dict, Optional

from prefect import flow, task
from prefect_kubernetes.jobs import KubernetesJob


@flow
def run_namespaced_job(
    kubernetes_job: KubernetesJob, print_func: Optional[Callable] = None
) -> Dict[str, Any]:
    """Flow for running a namespaced Kubernetes job.

    Args:
        kubernetes_job: The `KubernetesJob` block that specifies the job to run.
        print_func: A function to print the logs from the job pods.

    Returns:
        A dict of logs from each pod in the job, e.g. {'pod_name': 'pod_log_str'}.

    Raises:
        RuntimeError: If the created Kubernetes job attains a failed status.

    Example:

        ```python
        from prefect_kubernetes import KubernetesJob, run_namespaced_job
        from prefect_kubernetes.credentials import KubernetesCredentials

        run_namespaced_job(
            kubernetes_job=KubernetesJob.from_yaml_file(
                credentials=KubernetesCredentials.load("k8s-creds"),
                manifest_path="path/to/job.yaml",
            )
        )
        ```
    """
    kubernetes_job_run = task(kubernetes_job.trigger)()

    task(kubernetes_job_run.wait_for_completion)(print_func)

    return task(kubernetes_job_run.fetch_result)()


@flow
async def run_namespaced_job_async(
    kubernetes_job: KubernetesJob, print_func: Optional[Callable] = None
) -> Dict[str, Any]:
    """Flow for running a namespaced Kubernetes job.

    Args:
        kubernetes_job: The `KubernetesJob` block that specifies the job to run.
        print_func: A function to print the logs from the job pods.

    Returns:
        A dict of logs from each pod in the job, e.g. {'pod_name': 'pod_log_str'}.

    Raises:
        RuntimeError: If the created Kubernetes job attains a failed status.

    Example:

        ```python
        from prefect_kubernetes import KubernetesJob, run_namespaced_job
        from prefect_kubernetes.credentials import KubernetesCredentials

        run_namespaced_job(
            kubernetes_job=KubernetesJob.from_yaml_file(
                credentials=KubernetesCredentials.load("k8s-creds"),
                manifest_path="path/to/job.yaml",
            )
        )
        ```
    """
    kubernetes_job_run = (
        await maybe_coro
        if inspect.iscoroutine((maybe_coro := task(kubernetes_job.trigger)()))
        else maybe_coro
    )

    (
        await maybe_coro
        if inspect.iscoroutine(
            maybe_coro := task(kubernetes_job_run.wait_for_completion)(print_func)
        )
        else maybe_coro
    )

    return (
        await maybe_coro
        if inspect.iscoroutine(maybe_coro := task(kubernetes_job_run.fetch_result)())
        else maybe_coro
    )

"""A module to define flows interacting with Kubernetes resources."""

from typing import Any, Dict

from prefect import flow, task
from prefect_kubernetes.jobs import KubernetesJob


@flow
async def run_namespaced_job(
    kubernetes_job: KubernetesJob,
) -> Dict[str, Any]:
    """Flow for running a namespaced Kubernetes job.

    Args:
        kubernetes_job: The `KubernetesJob` block that specifies the job to run.

    Returns:
        The a dict of logs from each pod in the job, e.g. {'pod_name': 'pod_log_str'}.

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
    kubernetes_job_run = await task(kubernetes_job.trigger.aio)(kubernetes_job)

    await task(kubernetes_job_run.wait_for_completion.aio)(kubernetes_job_run)

    return await task(kubernetes_job_run.fetch_result.aio)(kubernetes_job_run)

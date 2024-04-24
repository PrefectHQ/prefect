"""Module to define tasks for interacting with Kubernetes jobs."""

from asyncio import sleep
from pathlib import Path
from typing import Any, Dict, Optional, Type, Union

import yaml
from kubernetes.client.models import V1DeleteOptions, V1Job, V1JobList, V1Status
from pydantic import VERSION as PYDANTIC_VERSION

from prefect import task
from prefect.blocks.abstract import JobBlock, JobRun
from prefect.utilities.asyncutils import run_sync_in_worker_thread, sync_compatible

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import Field
else:
    from pydantic import Field

from typing_extensions import Self

from prefect_kubernetes.credentials import KubernetesCredentials
from prefect_kubernetes.exceptions import KubernetesJobTimeoutError
from prefect_kubernetes.pods import list_namespaced_pod, read_namespaced_pod_log
from prefect_kubernetes.utilities import convert_manifest_to_model

KubernetesManifest = Union[Dict, Path, str]


@task
async def create_namespaced_job(
    kubernetes_credentials: KubernetesCredentials,
    new_job: V1Job,
    namespace: Optional[str] = "default",
    **kube_kwargs: Dict[str, Any],
) -> V1Job:
    """Task for creating a namespaced Kubernetes job.

    Args:
        kubernetes_credentials: `KubernetesCredentials` block
            holding authentication needed to generate the required API client.
        new_job: A Kubernetes `V1Job` specification.
        namespace: The Kubernetes namespace to create this job in.
        **kube_kwargs: Optional extra keyword arguments to pass to the
            Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`).

    Returns:
        A Kubernetes `V1Job` object.

    Example:
        Create a job in the default namespace:
        ```python
        from prefect import flow
        from prefect_kubernetes.credentials import KubernetesCredentials
        from prefect_kubernetes.jobs import create_namespaced_job
        from kubernetes.client.models import V1Job

        @flow
        def kubernetes_orchestrator():
            v1_job_metadata = create_namespaced_job(
                new_job=V1Job(metadata={"labels": {"foo": "bar"}}),
                kubernetes_credentials=KubernetesCredentials.load("k8s-creds"),
            )
        ```
    """
    with kubernetes_credentials.get_client("batch") as batch_v1_client:
        return await run_sync_in_worker_thread(
            batch_v1_client.create_namespaced_job,
            namespace=namespace,
            body=new_job,
            **kube_kwargs,
        )


@task
async def delete_namespaced_job(
    kubernetes_credentials: KubernetesCredentials,
    job_name: str,
    delete_options: Optional[V1DeleteOptions] = None,
    namespace: Optional[str] = "default",
    **kube_kwargs: Dict[str, Any],
) -> V1Status:
    """Task for deleting a namespaced Kubernetes job.

    Args:
        kubernetes_credentials: `KubernetesCredentials` block
            holding authentication needed to generate the required API client.
        job_name: The name of a job to delete.
        delete_options: A Kubernetes `V1DeleteOptions` object.
        namespace: The Kubernetes namespace to delete this job in.
        **kube_kwargs: Optional extra keyword arguments to pass to the
            Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`).


    Returns:
        A Kubernetes `V1Status` object.

    Example:
        Delete "my-job" in the default namespace:
        ```python
        from kubernetes.client.models import V1DeleteOptions
        from prefect import flow
        from prefect_kubernetes.credentials import KubernetesCredentials
        from prefect_kubernetes.jobs import delete_namespaced_job

        @flow
        def kubernetes_orchestrator():
            v1_job_status = delete_namespaced_job(
                job_name="my-job",
                kubernetes_credentials=KubernetesCredentials.load("k8s-creds"),
                delete_options=V1DeleteOptions(propagation_policy="Foreground"),
            )
        ```
    """

    with kubernetes_credentials.get_client("batch") as batch_v1_client:
        return await run_sync_in_worker_thread(
            batch_v1_client.delete_namespaced_job,
            name=job_name,
            body=delete_options,
            namespace=namespace,
            **kube_kwargs,
        )


@task
async def list_namespaced_job(
    kubernetes_credentials: KubernetesCredentials,
    namespace: Optional[str] = "default",
    **kube_kwargs: Dict[str, Any],
) -> V1JobList:
    """Task for listing namespaced Kubernetes jobs.

    Args:
        kubernetes_credentials: `KubernetesCredentials` block
            holding authentication needed to generate the required API client.
        namespace: The Kubernetes namespace to list jobs from.
        **kube_kwargs: Optional extra keyword arguments to pass to the
            Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`).

    Returns:
        A Kubernetes `V1JobList` object.

    Example:
        List jobs in "my-namespace":
        ```python
        from prefect import flow
        from prefect_kubernetes.credentials import KubernetesCredentials
        from prefect_kubernetes.jobs import list_namespaced_job

        @flow
        def kubernetes_orchestrator():
            namespaced_job_list = list_namespaced_job(
                namespace="my-namespace",
                kubernetes_credentials=KubernetesCredentials.load("k8s-creds"),
            )
        ```
    """
    with kubernetes_credentials.get_client("batch") as batch_v1_client:
        return await run_sync_in_worker_thread(
            batch_v1_client.list_namespaced_job,
            namespace=namespace,
            **kube_kwargs,
        )


@task
async def patch_namespaced_job(
    kubernetes_credentials: KubernetesCredentials,
    job_name: str,
    job_updates: V1Job,
    namespace: Optional[str] = "default",
    **kube_kwargs: Dict[str, Any],
) -> V1Job:
    """Task for patching a namespaced Kubernetes job.

    Args:
        kubernetes_credentials: KubernetesCredentials block
            holding authentication needed to generate the required API client.
        job_name: The name of a job to patch.
        job_updates: A Kubernetes `V1Job` specification.
        namespace: The Kubernetes namespace to patch this job in.
        **kube_kwargs: Optional extra keyword arguments to pass to the
            Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`).

    Raises:
        ValueError: if `job_name` is `None`.

    Returns:
        A Kubernetes `V1Job` object.

    Example:
        Patch "my-job" in the default namespace:
        ```python
        from prefect import flow
        from prefect_kubernetes.credentials import KubernetesCredentials
        from prefect_kubernetes.jobs import patch_namespaced_job

        from kubernetes.client.models import V1Job

        @flow
        def kubernetes_orchestrator():
            v1_job_metadata = patch_namespaced_job(
                job_name="my-job",
                job_updates=V1Job(metadata={"labels": {"foo": "bar"}}}),
                kubernetes_credentials=KubernetesCredentials.load("k8s-creds"),
            )
        ```
    """

    with kubernetes_credentials.get_client("batch") as batch_v1_client:
        return await run_sync_in_worker_thread(
            batch_v1_client.patch_namespaced_job,
            name=job_name,
            namespace=namespace,
            body=job_updates,
            **kube_kwargs,
        )


@task
async def read_namespaced_job(
    kubernetes_credentials: KubernetesCredentials,
    job_name: str,
    namespace: Optional[str] = "default",
    **kube_kwargs: Dict[str, Any],
) -> V1Job:
    """Task for reading a namespaced Kubernetes job.

    Args:
        kubernetes_credentials: `KubernetesCredentials` block
            holding authentication needed to generate the required API client.
        job_name: The name of a job to read.
        namespace: The Kubernetes namespace to read this job in.
        **kube_kwargs: Optional extra keyword arguments to pass to the
            Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`).

    Raises:
        ValueError: if `job_name` is `None`.

    Returns:
        A Kubernetes `V1Job` object.

    Example:
        Read "my-job" in the default namespace:
        ```python
        from prefect import flow
        from prefect_kubernetes.credentials import KubernetesCredentials
        from prefect_kubernetes.jobs import read_namespaced_job

        @flow
        def kubernetes_orchestrator():
            v1_job_metadata = read_namespaced_job(
                job_name="my-job",
                kubernetes_credentials=KubernetesCredentials.load("k8s-creds"),
            )
        ```
    """
    with kubernetes_credentials.get_client("batch") as batch_v1_client:
        return await run_sync_in_worker_thread(
            batch_v1_client.read_namespaced_job,
            name=job_name,
            namespace=namespace,
            **kube_kwargs,
        )


@task
async def replace_namespaced_job(
    kubernetes_credentials: KubernetesCredentials,
    job_name: str,
    new_job: V1Job,
    namespace: Optional[str] = "default",
    **kube_kwargs: Dict[str, Any],
) -> V1Job:
    """Task for replacing a namespaced Kubernetes job.

    Args:
        kubernetes_credentials: `KubernetesCredentials` block
            holding authentication needed to generate the required API client.
        job_name: The name of a job to replace.
        new_job: A Kubernetes `V1Job` specification.
        namespace: The Kubernetes namespace to replace this job in.
        **kube_kwargs: Optional extra keyword arguments to pass to the
            Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`).

    Returns:
        A Kubernetes `V1Job` object.

    Example:
        Replace "my-job" in the default namespace:
        ```python
        from prefect import flow
        from prefect_kubernetes.credentials import KubernetesCredentials
        from prefect_kubernetes.jobs import replace_namespaced_job

        @flow
        def kubernetes_orchestrator():
            v1_job_metadata = replace_namespaced_job(
                new_job=V1Job(metadata={"labels": {"foo": "bar"}}),
                job_name="my-job",
                kubernetes_credentials=KubernetesCredentials.load("k8s-creds"),
            )
        ```
    """
    with kubernetes_credentials.get_client("batch") as batch_v1_client:
        return await run_sync_in_worker_thread(
            batch_v1_client.replace_namespaced_job,
            name=job_name,
            body=new_job,
            namespace=namespace,
            **kube_kwargs,
        )


@task
async def read_namespaced_job_status(
    kubernetes_credentials: KubernetesCredentials,
    job_name: str,
    namespace: Optional[str] = "default",
    **kube_kwargs: Dict[str, Any],
) -> V1Job:
    """Task for fetching status of a namespaced Kubernetes job.

    Args:
        kubernetes_credentials: `KubernetesCredentials` block
            holding authentication needed to generate the required API client.
        job_name: The name of a job to fetch status for.
        namespace: The Kubernetes namespace to fetch status of job in.
        **kube_kwargs: Optional extra keyword arguments to pass to the
            Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`).

    Returns:
        A Kubernetes `V1JobStatus` object.

    Example:
        Fetch status of a job in the default namespace:
        ```python
        from prefect import flow
        from prefect_kubernetes.credentials import KubernetesCredentials
        from prefect_kubernetes.jobs import read_namespaced_job_status

        @flow
        def kubernetes_orchestrator():
            v1_job_status = read_namespaced_job_status(
                kubernetes_credentials=KubernetesCredentials.load("k8s-creds"),
                job_name="my-job",
            )
        ```
    """
    with kubernetes_credentials.get_client("batch") as batch_v1_client:
        return await run_sync_in_worker_thread(
            batch_v1_client.read_namespaced_job_status,
            name=job_name,
            namespace=namespace,
            **kube_kwargs,
        )


class KubernetesJobRun(JobRun[Dict[str, Any]]):
    """A container representing a run of a Kubernetes job."""

    def __init__(
        self,
        kubernetes_job: "KubernetesJob",
        v1_job_model: V1Job,
    ):
        self.pod_logs = None

        self._completed = False
        self._kubernetes_job = kubernetes_job
        self._v1_job_model = v1_job_model

    async def _cleanup(self):
        """Deletes the Kubernetes job resource."""

        delete_options = V1DeleteOptions(propagation_policy="Foreground")

        deleted_v1_job = await delete_namespaced_job.fn(
            kubernetes_credentials=self._kubernetes_job.credentials,
            job_name=self._v1_job_model.metadata.name,
            delete_options=delete_options,
            namespace=self._kubernetes_job.namespace,
            **self._kubernetes_job.api_kwargs,
        )
        self.logger.info(
            f"Job {self._v1_job_model.metadata.name} deleted "
            f"with {deleted_v1_job.status!r}."
        )

    @sync_compatible
    async def wait_for_completion(self):
        """Waits for the job to complete.

        If the job has `delete_after_completion` set to `True`,
        the job will be deleted if it is observed by this method
        to enter a completed state.

        Raises:
            RuntimeError: If the Kubernetes job fails.
            KubernetesJobTimeoutError: If the Kubernetes job times out.
            ValueError: If `wait_for_completion` is never called.
        """
        self.pod_logs = {}

        elapsed_time = 0

        while not self._completed:
            job_expired = (
                elapsed_time > self._kubernetes_job.timeout_seconds
                if self._kubernetes_job.timeout_seconds
                else False
            )
            if job_expired:
                raise KubernetesJobTimeoutError(
                    f"Job timed out after {elapsed_time} seconds."
                )

            v1_job_status = await read_namespaced_job_status.fn(
                kubernetes_credentials=self._kubernetes_job.credentials,
                job_name=self._v1_job_model.metadata.name,
                namespace=self._kubernetes_job.namespace,
                **self._kubernetes_job.api_kwargs,
            )
            pod_selector = (
                "controller-uid=" f"{v1_job_status.metadata.labels['controller-uid']}"
            )
            v1_pod_list = await list_namespaced_pod.fn(
                kubernetes_credentials=self._kubernetes_job.credentials,
                namespace=self._kubernetes_job.namespace,
                label_selector=pod_selector,
                **self._kubernetes_job.api_kwargs,
            )

            for pod in v1_pod_list.items:
                pod_name = pod.metadata.name

                if pod.status.phase == "Pending" or pod_name in self.pod_logs.keys():
                    continue

                self.logger.info(f"Capturing logs for pod {pod_name!r}.")

                self.pod_logs[pod_name] = await read_namespaced_pod_log.fn(
                    kubernetes_credentials=self._kubernetes_job.credentials,
                    pod_name=pod_name,
                    container=v1_job_status.spec.template.spec.containers[0].name,
                    namespace=self._kubernetes_job.namespace,
                    **self._kubernetes_job.api_kwargs,
                )

            if v1_job_status.status.active:
                await sleep(self._kubernetes_job.interval_seconds)
                if self._kubernetes_job.timeout_seconds:
                    elapsed_time += self._kubernetes_job.interval_seconds
            elif v1_job_status.status.conditions:
                final_completed_conditions = [
                    condition.type == "Complete"
                    for condition in v1_job_status.status.conditions
                    if condition.status == "True"
                ]
                if final_completed_conditions and any(final_completed_conditions):
                    self._completed = True
                    self.logger.info(
                        f"Job {v1_job_status.metadata.name!r} has "
                        f"completed with {v1_job_status.status.succeeded} pods."
                    )
                elif final_completed_conditions:
                    failed_conditions = [
                        condition.reason
                        for condition in v1_job_status.status.conditions
                        if condition.type == "Failed"
                    ]
                    raise RuntimeError(
                        f"Job {v1_job_status.metadata.name!r} failed due to "
                        f"{failed_conditions}, check the Kubernetes pod logs "
                        f"for more information."
                    )

        if self._kubernetes_job.delete_after_completion:
            await self._cleanup()

    @sync_compatible
    async def fetch_result(self) -> Dict[str, Any]:
        """Fetch the results of the job.

        Returns:
            The logs from each of the pods in the job.

        Raises:
            ValueError: If this method is called when the job has
                a non-terminal state.
        """

        if not self._completed:
            raise ValueError(
                "The Kubernetes Job run is not in a completed state - "
                "be sure to call `wait_for_completion` before attempting "
                "to fetch the result."
            )
        return self.pod_logs


class KubernetesJob(JobBlock):
    """A block representing a Kubernetes job configuration."""

    v1_job: Dict[str, Any] = Field(
        default=...,
        title="Job Manifest",
        description=(
            "The Kubernetes job manifest to run. This dictionary can be produced "
            "using `yaml.safe_load`."
        ),
    )
    api_kwargs: Dict[str, Any] = Field(
        default_factory=dict,
        title="Additional API Arguments",
        description="Additional arguments to include in Kubernetes API calls.",
        example={"pretty": "true"},
    )
    credentials: KubernetesCredentials = Field(
        default=..., description="The credentials to configure a client from."
    )
    delete_after_completion: bool = Field(
        default=True,
        description="Whether to delete the job after it has completed.",
    )
    interval_seconds: int = Field(
        default=5,
        description="The number of seconds to wait between job status checks.",
    )
    namespace: str = Field(
        default="default",
        description="The namespace to create and run the job in.",
    )
    timeout_seconds: Optional[int] = Field(
        default=None,
        description="The number of seconds to wait for the job run before timing out.",
    )

    _block_type_name = "Kubernetes Job"
    _block_type_slug = "k8s-job"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/2d0b896006ad463b49c28aaac14f31e00e32cfab-250x250.png"  # noqa: E501
    _documentation_url = "https://prefecthq.github.io/prefect-kubernetes/jobs/#prefect_kubernetes.jobs.KubernetesJob"  # noqa

    @sync_compatible
    async def trigger(self):
        """Create a Kubernetes job and return a `KubernetesJobRun` object."""

        v1_job_model = convert_manifest_to_model(self.v1_job, "V1Job")

        await create_namespaced_job.fn(
            kubernetes_credentials=self.credentials,
            new_job=v1_job_model,
            namespace=self.namespace,
            **self.api_kwargs,
        )

        return KubernetesJobRun(kubernetes_job=self, v1_job_model=v1_job_model)

    @classmethod
    def from_yaml_file(
        cls: Type[Self], manifest_path: Union[Path, str], **kwargs
    ) -> Self:
        """Create a `KubernetesJob` from a YAML file.

        Args:
            manifest_path: The YAML file to create the `KubernetesJob` from.

        Returns:
            A KubernetesJob object.
        """
        with open(manifest_path, "r") as yaml_stream:
            yaml_dict = yaml.safe_load(yaml_stream)

        return cls(v1_job=yaml_dict, **kwargs)

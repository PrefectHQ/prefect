""" Tasks for working with Kubernetes services. """

from typing import Any, Dict, Optional

from kubernetes.client.models import V1DeleteOptions, V1Service, V1ServiceList

from prefect import task
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect_kubernetes.credentials import KubernetesCredentials


@task
async def create_namespaced_service(
    kubernetes_credentials: KubernetesCredentials,
    new_service: V1Service,
    namespace: Optional[str] = "default",
    **kube_kwargs: Optional[Dict[str, Any]],
) -> V1Service:
    """Create a namespaced Kubernetes service.

    Args:
        kubernetes_credentials: A `KubernetesCredentials` block used to generate a
            `CoreV1Api` client.
        new_service: A `V1Service` object representing the service to create.
        namespace: The namespace to create the service in.
        **kube_kwargs: Additional keyword arguments to pass to the `CoreV1Api`
            method call.

    Returns:
        A `V1Service` representing the created service.

    Example:
        ```python
        from prefect import flow
        from prefect_kubernetes.credentials import KubernetesCredentials
        from prefect_kubernetes.services import create_namespaced_service
        from kubernetes.client.models import V1Service

        @flow
        def create_service_flow():
            v1_service = create_namespaced_service(
                kubernetes_credentials=KubernetesCredentials.load("k8s-creds"),
                new_service=V1Service(metadata={...}, spec={...}),
            )
        ```
    """
    with kubernetes_credentials.get_client("core") as core_v1_client:
        return await run_sync_in_worker_thread(
            core_v1_client.create_namespaced_service,
            body=new_service,
            namespace=namespace,
            **kube_kwargs,
        )


@task
async def delete_namespaced_service(
    kubernetes_credentials: KubernetesCredentials,
    service_name: str,
    delete_options: Optional[V1DeleteOptions] = None,
    namespace: Optional[str] = "default",
    **kube_kwargs: Optional[Dict[str, Any]],
) -> V1Service:
    """Delete a namespaced Kubernetes service.

    Args:
        kubernetes_credentials: `KubernetesCredentials` block for creating
            authenticated Kubernetes API clients.
        service_name: The name of the service to delete.
        delete_options: A `V1DeleteOptions` object representing the options to
            delete the service with.
        namespace: The namespace to delete the service from.
        **kube_kwargs: Optional extra keyword arguments to pass to the Kubernetes API.

    Returns:
        A `V1Service` representing the deleted service.

    Example:
        ```python
        from prefect import flow
        from prefect_kubernetes.credentials import KubernetesCredentials
        from prefect_kubernetes.services import delete_namespaced_service

        @flow
        def kubernetes_orchestrator():
            delete_namespaced_service(
                kubernetes_credentials=KubernetesCredentials.load("k8s-creds"),
                service_name="my-service",
                namespace="my-namespace",
            )
        ```
    """
    with kubernetes_credentials.get_client("core") as core_v1_client:
        return await run_sync_in_worker_thread(
            core_v1_client.delete_namespaced_service,
            name=service_name,
            namespace=namespace,
            body=delete_options,
            **kube_kwargs,
        )


@task
async def list_namespaced_service(
    kubernetes_credentials: KubernetesCredentials,
    namespace: Optional[str] = "default",
    **kube_kwargs: Optional[Dict[str, Any]],
) -> V1ServiceList:
    """List namespaced Kubernetes services.

    Args:
        kubernetes_credentials: `KubernetesCredentials` block for creating
            authenticated Kubernetes API clients.
        namespace: The namespace to list services from.
        **kube_kwargs: Optional extra keyword arguments to pass to the Kubernetes API.

    Returns:
        A `V1ServiceList` representing the list of services in the given namespace.

    Example:
        ```python
        from prefect import flow
        from prefect_kubernetes.credentials import KubernetesCredentials
        from prefect_kubernetes.services import list_namespaced_service

        @flow
        def kubernetes_orchestrator():
            list_namespaced_service(
                kubernetes_credentials=KubernetesCredentials.load("k8s-creds"),
                namespace="my-namespace",
            )
        ```
    """
    with kubernetes_credentials.get_client("core") as core_v1_client:
        return await run_sync_in_worker_thread(
            core_v1_client.list_namespaced_service,
            namespace=namespace,
            **kube_kwargs,
        )


@task
async def patch_namespaced_service(
    kubernetes_credentials: KubernetesCredentials,
    service_name: str,
    service_updates: V1Service,
    namespace: Optional[str] = "default",
    **kube_kwargs: Optional[Dict[str, Any]],
) -> V1Service:
    """Patch a namespaced Kubernetes service.

    Args:
        kubernetes_credentials: `KubernetesCredentials` block for creating
            authenticated Kubernetes API clients.
        service_name: The name of the service to patch.
        service_updates: A `V1Service` object representing patches to `service_name`.
        namespace: The namespace to patch the service in.
        **kube_kwargs: Optional extra keyword arguments to pass to the Kubernetes API.

    Returns:
        A `V1Service` representing the patched service.

    Example:
        ```python
        from prefect import flow
        from prefect_kubernetes.credentials import KubernetesCredentials
        from prefect_kubernetes.services import patch_namespaced_service
        from kubernetes.client.models import V1Service

        @flow
        def kubernetes_orchestrator():
            patch_namespaced_service(
                kubernetes_credentials=KubernetesCredentials.load("k8s-creds"),
                service_name="my-service",
                new_service=V1Service(metadata={...}, spec={...}),
                namespace="my-namespace",
            )
        ```
    """
    with kubernetes_credentials.get_client("core") as core_v1_client:
        return await run_sync_in_worker_thread(
            core_v1_client.patch_namespaced_service,
            name=service_name,
            body=service_updates,
            namespace=namespace,
            **kube_kwargs,
        )


@task
async def read_namespaced_service(
    kubernetes_credentials: KubernetesCredentials,
    service_name: str,
    namespace: Optional[str] = "default",
    **kube_kwargs: Optional[Dict[str, Any]],
) -> V1Service:
    """Read a namespaced Kubernetes service.

    Args:
        kubernetes_credentials: `KubernetesCredentials` block for creating
            authenticated Kubernetes API clients.
        service_name: The name of the service to read.
        namespace: The namespace to read the service from.
        **kube_kwargs: Optional extra keyword arguments to pass to the Kubernetes API.

    Returns:
        A `V1Service` object representing the service.

    Example:
        ```python
        from prefect import flow
        from prefect_kubernetes.credentials import KubernetesCredentials
        from prefect_kubernetes.services import read_namespaced_service

        @flow
        def kubernetes_orchestrator():
            read_namespaced_service(
                kubernetes_credentials=KubernetesCredentials.load("k8s-creds"),
                service_name="my-service",
                namespace="my-namespace",
            )
        ```
    """
    with kubernetes_credentials.get_client("core") as core_v1_client:
        return await run_sync_in_worker_thread(
            core_v1_client.read_namespaced_service,
            name=service_name,
            namespace=namespace,
            **kube_kwargs,
        )


@task
async def replace_namespaced_service(
    kubernetes_credentials: KubernetesCredentials,
    service_name: str,
    new_service: V1Service,
    namespace: Optional[str] = "default",
    **kube_kwargs: Optional[Dict[str, Any]],
) -> V1Service:
    """Replace a namespaced Kubernetes service.

    Args:
        kubernetes_credentials: `KubernetesCredentials` block for creating
            authenticated Kubernetes API clients.
        service_name: The name of the service to replace.
        new_service: A `V1Service` object representing the new service.
        namespace: The namespace to replace the service in.
        **kube_kwargs: Optional extra keyword arguments to pass to the Kubernetes API.

    Returns:
        A `V1Service` representing the new service.

    Example:
        ```python
        from prefect import flow
        from prefect_kubernetes.credentials import KubernetesCredentials
        from prefect_kubernetes.services import replace_namespaced_service
        from kubernetes.client.models import V1Service

        @flow
        def kubernetes_orchestrator():
            replace_namespaced_service(
                kubernetes_credentials=KubernetesCredentials.load("k8s-creds"),
                service_name="my-service",
                new_service=V1Service(metadata={...}, spec={...}),
                namespace="my-namespace",
            )
        ```
    """
    with kubernetes_credentials.get_client("core") as core_v1_client:
        return await run_sync_in_worker_thread(
            core_v1_client.replace_namespaced_service,
            name=service_name,
            body=new_service,
            namespace=namespace,
            **kube_kwargs,
        )

"""Module for interacting with Kubernetes deployments from Prefect flows."""
from typing import Any, Dict, Optional

from kubernetes.client.models import V1DeleteOptions, V1Deployment, V1DeploymentList

from prefect import task
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect_kubernetes.credentials import KubernetesCredentials


@task
async def create_namespaced_deployment(
    kubernetes_credentials: KubernetesCredentials,
    new_deployment: V1Deployment,
    namespace: Optional[str] = "default",
    **kube_kwargs: Dict[str, Any],
) -> V1Deployment:
    """Create a Kubernetes deployment in a given namespace.

    Args:
        kubernetes_credentials: `KubernetesCredentials` block for creating
            authenticated Kubernetes API clients.
        new_deployment: A Kubernetes `V1Deployment` specification.
        namespace: The Kubernetes namespace to create this deployment in.
        **kube_kwargs: Optional extra keyword arguments to pass to the Kubernetes API.

    Returns:
        A Kubernetes `V1Deployment` object.

    Example:
        Create a deployment in the default namespace:
        ```python
        from prefect import flow
        from prefect_kubernetes.credentials import KubernetesCredentials
        from prefect_kubernetes.deployments import create_namespaced_deployment
        from kubernetes.client.models import V1Deployment

        @flow
        def kubernetes_orchestrator():
            v1_deployment_metadata = create_namespaced_deployment(
                kubernetes_credentials=KubernetesCredentials.load("k8s-creds"),
                new_deployment=V1Deployment(metadata={"name": "test-deployment"}),
            )
        ```
    """
    with kubernetes_credentials.get_client("apps") as apps_v1_client:
        return await run_sync_in_worker_thread(
            apps_v1_client.create_namespaced_deployment,
            namespace=namespace,
            body=new_deployment,
            **kube_kwargs,
        )


@task
async def delete_namespaced_deployment(
    kubernetes_credentials: KubernetesCredentials,
    deployment_name: str,
    delete_options: Optional[V1DeleteOptions] = None,
    namespace: Optional[str] = "default",
    **kube_kwargs: Dict[str, Any],
) -> V1Deployment:
    """Delete a Kubernetes deployment in a given namespace.

    Args:
        kubernetes_credentials: `KubernetesCredentials` block for creating
            authenticated Kubernetes API clients.
        deployment_name: The name of the deployment to delete.
        delete_options: A Kubernetes `V1DeleteOptions` object.
        namespace: The Kubernetes namespace to delete this deployment from.
        **kube_kwargs: Optional extra keyword arguments to pass to the Kubernetes API.

    Returns:
        A Kubernetes `V1Deployment` object.

    Example:
        Delete a deployment in the default namespace:
        ```python
        from prefect import flow
        from prefect_kubernetes.credentials import KubernetesCredentials
        from prefect_kubernetes.deployments import delete_namespaced_deployment
        from kubernetes.client.models import V1DeleteOptions

        @flow
        def kubernetes_orchestrator():
            v1_deployment_metadata = delete_namespaced_deployment(
                kubernetes_credentials=KubernetesCredentials.load("k8s-creds"),
                deployment_name="test-deployment",
                delete_options=V1DeleteOptions(grace_period_seconds=0),
            )
        ```
    """
    with kubernetes_credentials.get_client("apps") as apps_v1_client:
        return await run_sync_in_worker_thread(
            apps_v1_client.delete_namespaced_deployment,
            deployment_name,
            body=delete_options,
            namespace=namespace,
            **kube_kwargs,
        )


@task
async def list_namespaced_deployment(
    kubernetes_credentials: KubernetesCredentials,
    namespace: Optional[str] = "default",
    **kube_kwargs: Dict[str, Any],
) -> V1DeploymentList:
    """List all deployments in a given namespace.

    Args:
        kubernetes_credentials: `KubernetesCredentials` block for creating
            authenticated Kubernetes API clients.
        namespace: The Kubernetes namespace to list deployments from.
        **kube_kwargs: Optional extra keyword arguments to pass to the Kubernetes API.

    Returns:
        A Kubernetes `V1DeploymentList` object.

    Example:
        List all deployments in the default namespace:
        ```python
        from prefect import flow
        from prefect_kubernetes.credentials import KubernetesCredentials
        from prefect_kubernetes.deployments import list_namespaced_deployment

        @flow
        def kubernetes_orchestrator():
            v1_deployment_list = list_namespaced_deployment(
                kubernetes_credentials=KubernetesCredentials.load("k8s-creds")
            )
        ```
    """
    with kubernetes_credentials.get_client("apps") as apps_v1_client:
        return await run_sync_in_worker_thread(
            apps_v1_client.list_namespaced_deployment,
            namespace=namespace,
            **kube_kwargs,
        )


@task
async def patch_namespaced_deployment(
    kubernetes_credentials: KubernetesCredentials,
    deployment_name: str,
    deployment_updates: V1Deployment,
    namespace: Optional[str] = "default",
    **kube_kwargs: Dict[str, Any],
) -> V1Deployment:
    """Patch a Kubernetes deployment in a given namespace.

    Args:
        kubernetes_credentials: `KubernetesCredentials` block for creating
            authenticated Kubernetes API clients.
        deployment_name: The name of the deployment to patch.
        deployment_updates: A Kubernetes `V1Deployment` object.
        namespace: The Kubernetes namespace to patch this deployment in.
        **kube_kwargs: Optional extra keyword arguments to pass to the Kubernetes API.

    Returns:
        A Kubernetes `V1Deployment` object.

    Example:
        Patch a deployment in the default namespace:
        ```python
        from prefect import flow
        from prefect_kubernetes.credentials import KubernetesCredentials
        from prefect_kubernetes.deployments import patch_namespaced_deployment
        from kubernetes.client.models import V1Deployment

        @flow
        def kubernetes_orchestrator():
            v1_deployment_metadata = patch_namespaced_deployment(
                kubernetes_credentials=KubernetesCredentials.load("k8s-creds"),
                deployment_name="test-deployment",
                deployment_updates=V1Deployment(metadata={"labels": {"foo": "bar"}}),
            )
        ```
    """
    with kubernetes_credentials.get_client("apps") as apps_v1_client:
        return await run_sync_in_worker_thread(
            apps_v1_client.patch_namespaced_deployment,
            name=deployment_name,
            namespace=namespace,
            body=deployment_updates,
            **kube_kwargs,
        )


@task
async def read_namespaced_deployment(
    kubernetes_credentials: KubernetesCredentials,
    deployment_name: str,
    namespace: Optional[str] = "default",
    **kube_kwargs: Dict[str, Any],
) -> V1Deployment:
    """Read information on a Kubernetes deployment in a given namespace.

    Args:
        kubernetes_credentials: `KubernetesCredentials` block for creating
            authenticated Kubernetes API clients.
        deployment_name: The name of the deployment to read.
        namespace: The Kubernetes namespace to read this deployment from.
        **kube_kwargs: Optional extra keyword arguments to pass to the Kubernetes API.

    Returns:
        A Kubernetes `V1Deployment` object.

    Example:
        Read a deployment in the default namespace:
        ```python
        from prefect import flow
        from prefect_kubernetes.credentials import KubernetesCredentials

        @flow
        def kubernetes_orchestrator():
            v1_deployment_metadata = read_namespaced_deployment(
                kubernetes_credentials=KubernetesCredentials.load("k8s-creds"),
                deployment_name="test-deployment"
            )
        ```
    """
    with kubernetes_credentials.get_client("apps") as apps_v1_client:
        return await run_sync_in_worker_thread(
            apps_v1_client.read_namespaced_deployment,
            name=deployment_name,
            namespace=namespace,
            **kube_kwargs,
        )


@task
async def replace_namespaced_deployment(
    kubernetes_credentials: KubernetesCredentials,
    deployment_name: str,
    new_deployment: V1Deployment,
    namespace: Optional[str] = "default",
    **kube_kwargs: Dict[str, Any],
) -> V1Deployment:
    """Replace a Kubernetes deployment in a given namespace.

    Args:
        kubernetes_credentials: `KubernetesCredentials` block for creating
            authenticated Kubernetes API clients.
        deployment_name: The name of the deployment to replace.
        new_deployment: A Kubernetes `V1Deployment` object.
        namespace: The Kubernetes namespace to replace this deployment in.
        **kube_kwargs: Optional extra keyword arguments to pass to the Kubernetes API.

    Returns:
        A Kubernetes `V1Deployment` object.

    Example:
        Replace a deployment in the default namespace:
        ```python
        from prefect import flow
        from prefect_kubernetes.credentials import KubernetesCredentials
        from prefect_kubernetes.deployments import replace_namespaced_deployment
        from kubernetes.client.models import V1Deployment

        @flow
        def kubernetes_orchestrator():
            v1_deployment_metadata = replace_namespaced_deployment(
                kubernetes_credentials=KubernetesCredentials.load("k8s-creds"),
                deployment_name="test-deployment",
                new_deployment=V1Deployment(metadata={"labels": {"foo": "bar"}})
            )
        ```
    """
    with kubernetes_credentials.get_client("apps") as apps_v1_client:
        return await run_sync_in_worker_thread(
            apps_v1_client.replace_namespaced_deployment,
            body=new_deployment,
            name=deployment_name,
            namespace=namespace,
            **kube_kwargs,
        )

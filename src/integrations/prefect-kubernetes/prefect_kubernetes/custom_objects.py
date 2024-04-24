from typing import Any, Dict, Optional

from prefect import task
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect_kubernetes.credentials import KubernetesCredentials


@task
async def create_namespaced_custom_object(
    kubernetes_credentials: KubernetesCredentials,
    group: str,
    version: str,
    plural: str,
    body: Dict[str, Any],
    namespace: Optional[str] = "default",
    **kube_kwargs: Dict[str, Any],
) -> object:
    """Task for creating a namespaced custom object.

    Args:
        kubernetes_credentials: `KubernetesCredentials` block
            holding authentication needed to generate the required API client.
        group: The custom resource object's group
        version: The custom resource object's version
        plural: The custom resource object's plural
        body: A Dict containing the custom resource object's specification.
        namespace: The Kubernetes namespace to create the custom object in.
        **kube_kwargs: Optional extra keyword arguments to pass to the
            Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`).

    Returns:
        object containing the custom resource created by this task.

    Example:
        Create a custom object in the default namespace:
        ```python
        from prefect import flow
        from prefect_kubernetes.credentials import KubernetesCredentials
        from prefect_kubernetes.custom_objects import create_namespaced_custom_object

        @flow
        def kubernetes_orchestrator():
            custom_object_metadata = create_namespaced_custom_object(
                kubernetes_credentials=KubernetesCredentials.load("k8s-creds"),
                group="crd-group",
                version="crd-version",
                plural="crd-plural",
                body={
                    'api': 'crd-version',
                    'kind': 'crd-kind',
                    'metadata': {
                        'name': 'crd-name',
                    },
                },
            )
        ```
    """
    with kubernetes_credentials.get_client("custom_objects") as custom_objects_client:
        return await run_sync_in_worker_thread(
            custom_objects_client.create_namespaced_custom_object,
            group=group,
            version=version,
            plural=plural,
            body=body,
            namespace=namespace,
            **kube_kwargs,
        )


@task
async def delete_namespaced_custom_object(
    kubernetes_credentials: KubernetesCredentials,
    group: str,
    version: str,
    plural: str,
    name: str,
    namespace: Optional[str] = "default",
    **kube_kwargs: Dict[str, Any],
) -> object:
    """Task for deleting a namespaced custom object.

    Args:
        kubernetes_credentials: `KubernetesCredentials` block
            holding authentication needed to generate the required API client.
        group: The custom resource object's group
        version: The custom resource object's version
        plural: The custom resource object's plural
        name: The name of a custom object to delete.
        namespace: The Kubernetes namespace to create this custom object in.
        **kube_kwargs: Optional extra keyword arguments to pass to the
            Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`).


    Returns:
        object containing the custom resource deleted by this task.

    Example:
        Delete "my-custom-object" in the default namespace:
        ```python
        from prefect import flow
        from prefect_kubernetes.credentials import KubernetesCredentials
        from prefect_kubernetes.custom_objects import delete_namespaced_custom_object

        @flow
        def kubernetes_orchestrator():
            custom_object_metadata = delete_namespaced_custom_object(
                kubernetes_credentials=KubernetesCredentials.load("k8s-creds"),
                group="crd-group",
                version="crd-version",
                plural="crd-plural",
                name="my-custom-object",
            )
        ```
    """

    with kubernetes_credentials.get_client("custom_objects") as custom_objects_client:
        return await run_sync_in_worker_thread(
            custom_objects_client.delete_namespaced_custom_object,
            group=group,
            version=version,
            plural=plural,
            name=name,
            namespace=namespace,
            **kube_kwargs,
        )


@task
async def get_namespaced_custom_object(
    kubernetes_credentials: KubernetesCredentials,
    group: str,
    version: str,
    plural: str,
    name: str,
    namespace: Optional[str] = "default",
    **kube_kwargs: Dict[str, Any],
) -> object:
    """Task for reading a namespaced Kubernetes custom object.

    Args:
        kubernetes_credentials: `KubernetesCredentials` block
            holding authentication needed to generate the required API client.
        group: The custom resource object's group
        version: The custom resource object's version
        plural: The custom resource object's plural
        name: The name of a custom object to read.
        namespace: The Kubernetes namespace the custom resource is in.
        **kube_kwargs: Optional extra keyword arguments to pass to the
            Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`).

    Raises:
        ValueError: if `name` is `None`.

    Returns:
        object containing the custom resource specification.

    Example:
        Read "my-custom-object" in the default namespace:
        ```python
        from prefect import flow
        from prefect_kubernetes.credentials import KubernetesCredentials
        from prefect_kubernetes.custom_objects import get_namespaced_custom_object

        @flow
        def kubernetes_orchestrator():
            custom_object_metadata = get_namespaced_custom_object(
                kubernetes_credentials=KubernetesCredentials.load("k8s-creds"),
                group="crd-group",
                version="crd-version",
                plural="crd-plural",
                name="my-custom-object",
            )
        ```
    """
    with kubernetes_credentials.get_client("custom_objects") as custom_objects_client:
        return await run_sync_in_worker_thread(
            custom_objects_client.get_namespaced_custom_object,
            group=group,
            version=version,
            plural=plural,
            name=name,
            namespace=namespace,
            **kube_kwargs,
        )


@task
async def get_namespaced_custom_object_status(
    kubernetes_credentials: KubernetesCredentials,
    group: str,
    version: str,
    plural: str,
    name: str,
    namespace: str = "default",
    **kube_kwargs: Dict[str, Any],
) -> object:
    """Task for fetching status of a namespaced custom object.

    Args:
        kubernetes_credentials: `KubernetesCredentials` block
            holding authentication needed to generate the required API client.
        group: The custom resource object's group
        version: The custom resource object's version
        plural: The custom resource object's plural
        name: The name of a custom object to read.
        namespace: The Kubernetes namespace the custom resource is in.
        **kube_kwargs: Optional extra keyword arguments to pass to the
            Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`).

    Returns:
        object containing the custom-object specification with status.

    Example:
        Fetch status of "my-custom-object" in the default namespace:
        ```python
        from prefect import flow
        from prefect_kubernetes.credentials import KubernetesCredentials
        from prefect_kubernetes.custom_objects import (
            get_namespaced_custom_object_status,
        )

        @flow
        def kubernetes_orchestrator():
            custom_object_metadata = get_namespaced_custom_object_status(
                kubernetes_credentials=KubernetesCredentials.load("k8s-creds"),
                group="crd-group",
                version="crd-version",
                plural="crd-plural",
                name="my-custom-object",
            )
        ```
    """
    with kubernetes_credentials.get_client("custom_objects") as custom_objects_client:
        return await run_sync_in_worker_thread(
            custom_objects_client.get_namespaced_custom_object_status,
            group=group,
            version=version,
            plural=plural,
            name=name,
            namespace=namespace,
            **kube_kwargs,
        )


@task
async def list_namespaced_custom_object(
    kubernetes_credentials: KubernetesCredentials,
    group: str,
    version: str,
    plural: str,
    namespace: str = "default",
    **kube_kwargs: Dict[str, Any],
) -> object:
    """Task for listing namespaced custom objects.

    Args:
        kubernetes_credentials: `KubernetesCredentials` block
            holding authentication needed to generate the required API client.
        group: The custom resource object's group
        version: The custom resource object's version
        plural: The custom resource object's plural
        namespace: The Kubernetes namespace to list custom resources for.
        **kube_kwargs: Optional extra keyword arguments to pass to the
            Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`).

    Returns:
        object containing a list of custom resources.

    Example:
        List custom resources in "my-namespace":
        ```python
        from prefect import flow
        from prefect_kubernetes.credentials import KubernetesCredentials
        from prefect_kubernetes.custom_objects import list_namespaced_custom_object

        @flow
        def kubernetes_orchestrator():
            namespaced_custom_objects_list = list_namespaced_custom_object(
                kubernetes_credentials=KubernetesCredentials.load("k8s-creds"),
                group="crd-group",
                version="crd-version",
                plural="crd-plural",
                namespace="my-namespace",
            )
        ```
    """
    with kubernetes_credentials.get_client("custom_objects") as custom_objects_client:
        return await run_sync_in_worker_thread(
            custom_objects_client.list_namespaced_custom_object,
            group=group,
            version=version,
            plural=plural,
            namespace=namespace,
            **kube_kwargs,
        )


@task
async def patch_namespaced_custom_object(
    kubernetes_credentials: KubernetesCredentials,
    group: str,
    version: str,
    plural: str,
    name: str,
    body: Dict[str, Any],
    namespace: str = "default",
    **kube_kwargs: Dict[str, Any],
) -> object:
    """Task for patching a namespaced custom resource.

    Args:
        kubernetes_credentials: KubernetesCredentials block
            holding authentication needed to generate the required API client.
        group: The custom resource object's group
        version: The custom resource object's version
        plural: The custom resource object's plural
        name: The name of a custom object to patch.
        body: A Dict containing the custom resource object's patch.
        namespace: The custom resource's Kubernetes namespace.
        **kube_kwargs: Optional extra keyword arguments to pass to the
            Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`).

    Raises:
        ValueError: if `body` is `None`.

    Returns:
        object containing the custom resource specification
        after the patch gets applied.

    Example:
        Patch "my-custom-object" in the default namespace:
        ```python
        from prefect import flow
        from prefect_kubernetes.credentials import KubernetesCredentials
        from prefect_kubernetes.custom_objects import (
            patch_namespaced_custom_object,
        )

        @flow
        def kubernetes_orchestrator():
            custom_object_metadata = patch_namespaced_custom_object(
                kubernetes_credentials=KubernetesCredentials.load("k8s-creds"),
                group="crd-group",
                version="crd-version",
                plural="crd-plural",
                name="my-custom-object",
                body={
                    'api': 'crd-version',
                    'kind': 'crd-kind',
                    'metadata': {
                        'name': 'my-custom-object',
                    },
                },
            )
        ```
    """
    with kubernetes_credentials.get_client("custom_objects") as custom_objects_client:
        return await run_sync_in_worker_thread(
            custom_objects_client.patch_namespaced_custom_object,
            group=group,
            version=version,
            plural=plural,
            name=name,
            body=body,
            namespace=namespace,
            **kube_kwargs,
        )


@task
async def replace_namespaced_custom_object(
    kubernetes_credentials: KubernetesCredentials,
    group: str,
    version: str,
    plural: str,
    name: str,
    body: Dict[str, Any],
    namespace: str = "default",
    **kube_kwargs: Dict[str, Any],
) -> object:
    """Task for replacing a namespaced custom resource.

    Args:
        kubernetes_credentials: KubernetesCredentials block
            holding authentication needed to generate the required API client.
        group: The custom resource object's group
        version: The custom resource object's version
        plural: The custom resource object's plural
        name: The name of a custom object to replace.
        body: A Dict containing the custom resource object's specification.
        namespace: The custom resource's Kubernetes namespace.
        **kube_kwargs: Optional extra keyword arguments to pass to the
            Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`).

    Raises:
        ValueError: if `body` is `None`.

    Returns:
        object containing the custom resource specification after the replacement.

    Example:
        Replace "my-custom-object" in the default namespace:
        ```python
        from prefect import flow
        from prefect_kubernetes.credentials import KubernetesCredentials
        from prefect_kubernetes.custom_objects import replace_namespaced_custom_object

        @flow
        def kubernetes_orchestrator():
            custom_object_metadata = replace_namespaced_custom_object(
                kubernetes_credentials=KubernetesCredentials.load("k8s-creds"),
                group="crd-group",
                version="crd-version",
                plural="crd-plural",
                name="my-custom-object",
                body={
                    'api': 'crd-version',
                    'kind': 'crd-kind',
                    'metadata': {
                        'name': 'my-custom-object',
                    },
                },
            )
        ```
    """
    with kubernetes_credentials.get_client("custom_objects") as custom_objects_client:
        return await run_sync_in_worker_thread(
            custom_objects_client.replace_namespaced_custom_object,
            group=group,
            version=version,
            plural=plural,
            name=name,
            body=body,
            namespace=namespace,
            **kube_kwargs,
        )

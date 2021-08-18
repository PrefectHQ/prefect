from typing import Any, cast, Callable

from kubernetes import client
from kubernetes.stream import stream
from kubernetes.watch import Watch
from kubernetes.client.rest import ApiException

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs
from prefect.utilities.kubernetes import get_kubernetes_client


class CreateNamespacedPod(Task):
    """
    Task for creating a namespaced pod on Kubernetes.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    This task will attempt to connect to a Kubernetes cluster in three steps with
    the first successful connection attempt becoming the mode of communication with a
    cluster.

    1. Attempt to use a Prefect Secret that contains a Kubernetes API Key. If
    `kubernetes_api_key_secret` = `None` then it will attempt the next two connection
    methods. By default the value is `KUBERNETES_API_KEY` so providing `None` acts as
    an override for the remote connection.
    2. Attempt in-cluster connection (will only work when running on a Pod in a cluster)
    3. Attempt out-of-cluster connection using the default location for a kube config file

    The arguments `body` and `kube_kwargs` will perform an in-place update when the task
    is run. This means that it is possible to provide `body = {"info": "here"}` at
    instantiation and then provide `body = {"more": "info"}` at run time which will make
    `body = {"info": "here", "more": "info"}`. *Note*: Keys present in both instantiation
    and runtime will be replaced with the runtime value.

    Args:
        - body (dict, optional): A dictionary representation of a Kubernetes V1Pod
            specification
        - namespace (str, optional): The Kubernetes namespace to create this pod in,
            defaults to the `default` namespace
        - kube_kwargs (dict, optional): Optional extra keyword arguments to pass to the
            Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`)
        - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
            which stored your Kubernetes API Key; this Secret must be a string and in
            BearerToken format
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        body: dict = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
        **kwargs: Any
    ):
        self.body = body or {}
        self.namespace = namespace
        self.kube_kwargs = kube_kwargs or {}
        self.kubernetes_api_key_secret = kubernetes_api_key_secret

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "body", "namespace", "kube_kwargs", "kubernetes_api_key_secret"
    )
    def run(
        self,
        body: dict = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
    ) -> None:
        """
        Task run method.

        Args:
            - body (dict, optional): A dictionary representation of a Kubernetes V1Pod
                specification
            - namespace (str, optional): The Kubernetes namespace to create this pod in,
                defaults to the `default` namespace
            - kube_kwargs (dict, optional): Optional extra keyword arguments to pass to the
                Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`)
            - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
                which stored your Kubernetes API Key; this Secret must be a string and in
                BearerToken format

        Raises:
            - ValueError: if `body` is `None`
        """
        if not body:
            raise ValueError("A dictionary representing a V1Pod must be provided.")

        api_client = cast(
            client.CoreV1Api, get_kubernetes_client("pod", kubernetes_api_key_secret)
        )

        body = {**self.body, **(body or {})}
        kube_kwargs = {**self.kube_kwargs, **(kube_kwargs or {})}

        api_client.create_namespaced_pod(namespace=namespace, body=body, **kube_kwargs)


class DeleteNamespacedPod(Task):
    """
    Task for deleting a namespaced pod on Kubernetes.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    This task will attempt to connect to a Kubernetes cluster in three steps with
    the first successful connection attempt becoming the mode of communication with a
    cluster.

    1. Attempt to use a Prefect Secret that contains a Kubernetes API Key. If
    `kubernetes_api_key_secret` = `None` then it will attempt the next two connection
    methods. By default the value is `KUBERNETES_API_KEY` so providing `None` acts as
    an override for the remote connection.
    2. Attempt in-cluster connection (will only work when running on a Pod in a cluster)
    3. Attempt out-of-cluster connection using the default location for a kube config file

    The argument `kube_kwargs` will perform an in-place update when the task
    is run. This means that it is possible to provide `kube_kwargs = {"info": "here"}` at
    instantiation and then provide `kube_kwargs = {"more": "info"}` at run time which will make
    `kube_kwargs = {"info": "here", "more": "info"}`. *Note*: Keys present in both instantiation
    and runtime will be replaced with the runtime value.

    Args:
        - pod_name (str, optional): The name of a pod to delete
        - namespace (str, optional): The Kubernetes namespace to delete this pod from,
            defaults to the `default` namespace
        - kube_kwargs (dict, optional): Optional extra keyword arguments to pass to the
            Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`)
        - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
            which stored your Kubernetes API Key; this Secret must be a string and in
            BearerToken format
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        pod_name: str = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
        **kwargs: Any
    ):
        self.pod_name = pod_name
        self.namespace = namespace
        self.kube_kwargs = kube_kwargs or {}
        self.kubernetes_api_key_secret = kubernetes_api_key_secret

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "pod_name", "namespace", "kube_kwargs", "kubernetes_api_key_secret"
    )
    def run(
        self,
        pod_name: str = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
        delete_option_kwargs: dict = None,
    ) -> None:
        """
        Task run method.

        Args:
            - pod_name (str, optional): The name of a pod to delete
            - namespace (str, optional): The Kubernetes namespace to delete this pod in,
                defaults to the `default` namespace
            - kube_kwargs (dict, optional): Optional extra keyword arguments to pass to the
                Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`)
            - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
                which stored your Kubernetes API Key; this Secret must be a string and in
                BearerToken format
            - delete_option_kwargs (dict, optional): Optional keyword arguments to pass to
                the V1DeleteOptions object (e.g. {"propagation_policy": "...",
                "grace_period_seconds": "..."}.

        Raises:
            - ValueError: if `pod_name` is `None`
        """
        if not pod_name:
            raise ValueError("The name of a Kubernetes pod must be provided.")

        api_client = cast(
            client.CoreV1Api, get_kubernetes_client("pod", kubernetes_api_key_secret)
        )

        kube_kwargs = {**self.kube_kwargs, **(kube_kwargs or {})}
        delete_option_kwargs = delete_option_kwargs or {}

        api_client.delete_namespaced_pod(
            name=pod_name,
            namespace=namespace,
            body=client.V1DeleteOptions(**delete_option_kwargs),
            **kube_kwargs
        )


class ListNamespacedPod(Task):
    """
    Task for listing namespaced pods on Kubernetes.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    This task will attempt to connect to a Kubernetes cluster in three steps with
    the first successful connection attempt becoming the mode of communication with a
    cluster.

    1. Attempt to use a Prefect Secret that contains a Kubernetes API Key. If
    `kubernetes_api_key_secret` = `None` then it will attempt the next two connection
    methods. By default the value is `KUBERNETES_API_KEY` so providing `None` acts as
    an override for the remote connection.
    2. Attempt in-cluster connection (will only work when running on a Pod in a cluster)
    3. Attempt out-of-cluster connection using the default location for a kube config file

    The argument `kube_kwargs` will perform an in-place update when the task
    is run. This means that it is possible to provide `kube_kwargs = {"info": "here"}` at
    instantiation and then provide `kube_kwargs = {"more": "info"}` at run time which will make
    `kube_kwargs = {"info": "here", "more": "info"}`. *Note*: Keys present in both instantiation
    and runtime will be replaced with the runtime value.

    Args:
        - namespace (str, optional): The Kubernetes namespace to list pods from,
            defaults to the `default` namespace
        - kube_kwargs (dict, optional): Optional extra keyword arguments to pass to the
            Kubernetes API (e.g. `{"field_selector": "...", "label_selector": "..."}`)
        - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
            which stored your Kubernetes API Key; this Secret must be a string and in
            BearerToken format
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
        **kwargs: Any
    ):
        self.namespace = namespace
        self.kube_kwargs = kube_kwargs or {}
        self.kubernetes_api_key_secret = kubernetes_api_key_secret

        super().__init__(**kwargs)

    @defaults_from_attrs("namespace", "kube_kwargs", "kubernetes_api_key_secret")
    def run(
        self,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
    ) -> None:
        """
        Task run method.

        Args:
            - namespace (str, optional): The Kubernetes namespace to list pods from,
                defaults to the `default` namespace
            - kube_kwargs (dict, optional): Optional extra keyword arguments to pass to the
                Kubernetes API (e.g. `{"field_selector": "...", "label_selector": "..."}`)
            - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
                which stored your Kubernetes API Key; this Secret must be a string and in
                BearerToken format

        Returns:
            - V1PodList: a Kubernetes V1PodList of the pods which are found
        """
        api_client = cast(
            client.CoreV1Api, get_kubernetes_client("pod", kubernetes_api_key_secret)
        )

        kube_kwargs = {**self.kube_kwargs, **(kube_kwargs or {})}

        return api_client.list_namespaced_pod(namespace=namespace, **kube_kwargs)


class PatchNamespacedPod(Task):
    """
    Task for patching a namespaced pod on Kubernetes.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    This task will attempt to connect to a Kubernetes cluster in three steps with
    the first successful connection attempt becoming the mode of communication with a
    cluster.

    1. Attempt to use a Prefect Secret that contains a Kubernetes API Key. If
    `kubernetes_api_key_secret` = `None` then it will attempt the next two connection
    methods. By default the value is `KUBERNETES_API_KEY` so providing `None` acts as
    an override for the remote connection.
    2. Attempt in-cluster connection (will only work when running on a Pod in a cluster)
    3. Attempt out-of-cluster connection using the default location for a kube config file

    The arguments `body` and `kube_kwargs` will perform an in-place update when the task
    is run. This means that it is possible to provide `body = {"info": "here"}` at
    instantiation and then provide `body = {"more": "info"}` at run time which will make
    `body = {"info": "here", "more": "info"}`. *Note*: Keys present in both instantiation
    and runtime will be replaced with the runtime value.

    Args:
        - pod_name (str, optional): The name of a pod to patch
        - body (dict, optional): A dictionary representation of a Kubernetes V1Pod
            patch specification
        - namespace (str, optional): The Kubernetes namespace to patch this pod in,
            defaults to the `default` namespace
        - kube_kwargs (dict, optional): Optional extra keyword arguments to pass to the
            Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`)
        - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
            which stored your Kubernetes API Key; this Secret must be a string and in
            BearerToken format
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        pod_name: str = None,
        body: dict = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
        **kwargs: Any
    ):
        self.pod_name = pod_name
        self.body = body or {}
        self.namespace = namespace
        self.kube_kwargs = kube_kwargs or {}
        self.kubernetes_api_key_secret = kubernetes_api_key_secret

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "pod_name", "body", "namespace", "kube_kwargs", "kubernetes_api_key_secret"
    )
    def run(
        self,
        pod_name: str = None,
        body: dict = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
    ) -> None:
        """
        Task run method.

        Args:
            - pod_name (str, optional): The name of a pod to patch
            - body (dict, optional): A dictionary representation of a Kubernetes V1Pod
                patch specification
            - namespace (str, optional): The Kubernetes namespace to patch this pod in,
                defaults to the `default` namespace
            - kube_kwargs (dict, optional): Optional extra keyword arguments to pass to the
                Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`)
            - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
                which stored your Kubernetes API Key; this Secret must be a string and in
                BearerToken format

        Raises:
            - ValueError: if `body` is `None`
            - ValueError: if `pod_name` is `None`
        """
        if not body:
            raise ValueError(
                "A dictionary representing a V1Pod patch must be provided."
            )

        if not pod_name:
            raise ValueError("The name of a Kubernetes pod must be provided.")

        api_client = cast(
            client.CoreV1Api, get_kubernetes_client("pod", kubernetes_api_key_secret)
        )

        body = {**self.body, **(body or {})}
        kube_kwargs = {**self.kube_kwargs, **(kube_kwargs or {})}

        api_client.patch_namespaced_pod(
            name=pod_name, namespace=namespace, body=body, **kube_kwargs
        )


class ReadNamespacedPod(Task):
    """
    Task for reading a namespaced pod on Kubernetes.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    This task will attempt to connect to a Kubernetes cluster in three steps with
    the first successful connection attempt becoming the mode of communication with a
    cluster.

    1. Attempt to use a Prefect Secret that contains a Kubernetes API Key. If
    `kubernetes_api_key_secret` = `None` then it will attempt the next two connection
    methods. By default the value is `KUBERNETES_API_KEY` so providing `None` acts as
    an override for the remote connection.
    2. Attempt in-cluster connection (will only work when running on a Pod in a cluster)
    3. Attempt out-of-cluster connection using the default location for a kube config file

    The argument `kube_kwargs` will perform an in-place update when the task
    is run. This means that it is possible to provide `kube_kwargs = {"info": "here"}` at
    instantiation and then provide `kube_kwargs = {"more": "info"}` at run time which will make
    `kube_kwargs = {"info": "here", "more": "info"}`. *Note*: Keys present in both instantiation
    and runtime will be replaced with the runtime value.

    Args:
        - pod_name (str, optional): The name of a pod to read
        - namespace (str, optional): The Kubernetes namespace to read this pod from,
            defaults to the `default` namespace
        - kube_kwargs (dict, optional): Optional extra keyword arguments to pass to the
            Kubernetes API (e.g. `{"pretty": "...", "exact": "..."}`)
        - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
            which stored your Kubernetes API Key; this Secret must be a string and in
            BearerToken format
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        pod_name: str = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
        **kwargs: Any
    ):
        self.pod_name = pod_name
        self.namespace = namespace
        self.kube_kwargs = kube_kwargs or {}
        self.kubernetes_api_key_secret = kubernetes_api_key_secret

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "pod_name", "namespace", "kube_kwargs", "kubernetes_api_key_secret"
    )
    def run(
        self,
        pod_name: str = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
    ) -> None:
        """
        Task run method.

        Args:
            - pod_name (str, optional): The name of a pod to read
            - namespace (str, optional): The Kubernetes namespace to read this pod in,
                defaults to the `default` namespace
            - kube_kwargs (dict, optional): Optional extra keyword arguments to pass to the
                Kubernetes API (e.g. `{"pretty": "...", "exact": "..."}`)
            - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
                which stored your Kubernetes API Key; this Secret must be a string and in
                BearerToken format

        Returns:
            - V1Pod: a Kubernetes V1Pod matching the pod that was found

        Raises:
            - ValueError: if `pod_name` is `None`
        """
        if not pod_name:
            raise ValueError("The name of a Kubernetes pod must be provided.")

        api_client = cast(
            client.CoreV1Api, get_kubernetes_client("pod", kubernetes_api_key_secret)
        )

        kube_kwargs = {**self.kube_kwargs, **(kube_kwargs or {})}

        return api_client.read_namespaced_pod(
            name=pod_name, namespace=namespace, **kube_kwargs
        )


class ReplaceNamespacedPod(Task):
    """
    Task for replacing a namespaced pod on Kubernetes.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    This task will attempt to connect to a Kubernetes cluster in three steps with
    the first successful connection attempt becoming the mode of communication with a
    cluster.

    1. Attempt to use a Prefect Secret that contains a Kubernetes API Key. If
    `kubernetes_api_key_secret` = `None` then it will attempt the next two connection
    methods. By default the value is `KUBERNETES_API_KEY` so providing `None` acts as
    an override for the remote connection.
    2. Attempt in-cluster connection (will only work when running on a Pod in a cluster)
    3. Attempt out-of-cluster connection using the default location for a kube config file

    The arguments `body` and `kube_kwargs` will perform an in-place update when the task
    is run. This means that it is possible to provide `body = {"info": "here"}` at
    instantiation and then provide `body = {"more": "info"}` at run time which will make
    `body = {"info": "here", "more": "info"}`. *Note*: Keys present in both instantiation
    and runtime will be replaced with the runtime value.

    Args:
        - pod_name (str, optional): The name of a pod to replace
        - body (dict, optional): A dictionary representation of a Kubernetes V1Pod
            specification
        - namespace (str, optional): The Kubernetes namespace to patch this pod in,
            defaults to the `default` namespace
        - kube_kwargs (dict, optional): Optional extra keyword arguments to pass to the
            Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`)
        - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
            which stored your Kubernetes API Key; this Secret must be a string and in
            BearerToken format
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        pod_name: str = None,
        body: dict = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
        **kwargs: Any
    ):
        self.pod_name = pod_name
        self.body = body or {}
        self.namespace = namespace
        self.kube_kwargs = kube_kwargs or {}
        self.kubernetes_api_key_secret = kubernetes_api_key_secret

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "pod_name", "body", "namespace", "kube_kwargs", "kubernetes_api_key_secret"
    )
    def run(
        self,
        pod_name: str = None,
        body: dict = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
    ) -> None:
        """
        Task run method.

        Args:
            - pod_name (str, optional): The name of a pod to replace
            - body (dict, optional): A dictionary representation of a Kubernetes V1Pod
                specification
            - namespace (str, optional): The Kubernetes namespace to patch this pod in,
                defaults to the `default` namespace
            - kube_kwargs (dict, optional): Optional extra keyword arguments to pass to the
                Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`)
            - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
                which stored your Kubernetes API Key; this Secret must be a string and in
                BearerToken format

        Raises:
            - ValueError: if `body` is `None`
            - ValueError: if `pod_name` is `None`
        """
        if not body:
            raise ValueError("A dictionary representing a V1Pod must be provided.")

        if not pod_name:
            raise ValueError("The name of a Kubernetes pod must be provided.")

        api_client = cast(
            client.CoreV1Api, get_kubernetes_client("pod", kubernetes_api_key_secret)
        )

        body = {**self.body, **(body or {})}
        kube_kwargs = {**self.kube_kwargs, **(kube_kwargs or {})}

        api_client.replace_namespaced_pod(
            name=pod_name, namespace=namespace, body=body, **kube_kwargs
        )


class ReadNamespacedPodLogs(Task):
    """
    Task for reading logs from a namespaced pod on Kubernetes. Logs can be streamed by
    providing a `on_log_entry` function which then will be called for each log line. If
    `on_log_entry` = `None`, the task returns all logs for the pod until that point.

    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    This task will attempt to connect to a Kubernetes cluster in three steps with
    the first successful connection attempt becoming the mode of communication with a
    cluster.

    1. Attempt to use a Prefect Secret that contains a Kubernetes API Key. If
    `kubernetes_api_key_secret` = `None` then it will attempt the next two connection
    methods. By default the value is `KUBERNETES_API_KEY` so providing `None` acts as
    an override for the remote connection.
    2. Attempt in-cluster connection (will only work when running on a Pod in a cluster)
    3. Attempt out-of-cluster connection using the default location for a kube config file

    Args:
        - pod_name (str, optional): The name of a pod to replace
        - namespace (str, optional): The Kubernetes namespace to patch this pod in,
            defaults to the `default` namespace
        - on_log_entry (Callable, optional): If provided, will stream the pod logs
            calling the callback for every line (and the task returns `None`). If not
            provided, the current pod logs will be returned immediately from the task.
        - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
            which stored your Kubernetes API Key; this Secret must be a string and in
            BearerToken format
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        pod_name: str = None,
        namespace: str = "default",
        on_log_entry: Callable = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
        **kwargs: Any
    ):
        self.pod_name = pod_name
        self.namespace = namespace
        self.on_log_entry = on_log_entry
        self.kubernetes_api_key_secret = kubernetes_api_key_secret

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "pod_name", "namespace", "on_log_entry", "kubernetes_api_key_secret"
    )
    def run(
        self,
        pod_name: str = None,
        namespace: str = "default",
        on_log_entry: Callable = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
    ) -> None:
        """
        Task run method.

        Args:
            - pod_name (str, optional): The name of a pod to replace
            - namespace (str, optional): The Kubernetes namespace to patch this pod in,
                defaults to the `default` namespace
            - on_log_entry (Callable, optional): If provided, will stream the pod logs
                calling the callback for every line (and the task returns `None`). If not
                provided, the current pod logs will be returned immediately from the task.
            - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
                which stored your Kubernetes API Key; this Secret must be a string and in
                BearerToken format

        Raises:
            - ValueError: if `pod_name` is `None`
        """
        if not pod_name:
            raise ValueError("The name of a Kubernetes pod must be provided.")

        api_client = cast(
            client.CoreV1Api, get_kubernetes_client("pod", kubernetes_api_key_secret)
        )

        if on_log_entry is None:
            return api_client.read_namespaced_pod_log(
                name=pod_name, namespace=namespace
            )

        # From the kubernetes.watch documentation:
        # Note that watching an API resource can expire. The method tries to
        # resume automatically once from the last result, but if that last result
        # is too old as well, an `ApiException` exception will be thrown with
        # ``code`` 410.
        while True:
            try:
                stream = Watch().stream(
                    api_client.read_namespaced_pod_log,
                    name=pod_name,
                    namespace=namespace,
                )

                for log in stream:
                    on_log_entry(log)

                return
            except ApiException as exception:
                if exception.status != 410:
                    raise


class ConnectGetNamespacedPodExec(Task):
    """
    Task for running a command in a namespaced pod on Kubernetes.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.
    This task will attempt to connect to a Kubernetes cluster in three steps with
    the first successful connection attempt becoming the mode of communication with a
    cluster.

    1. Attempt to use a Prefect Secret that contains a Kubernetes API Key. If
    `kubernetes_api_key_secret` = `None` then it will attempt the next two connection
    methods. By default the value is `KUBERNETES_API_KEY` so providing `None` acts as
    an override for the remote connection.
    2. Attempt in-cluster connection (will only work when running on a Pod in a cluster)
    3. Attempt out-of-cluster connection using the default location for a kube config file
    The argument `kube_kwargs` will perform an in-place update when the task
    is run. This means that it is possible to provide `kube_kwargs = {"info": "here"}` at
    instantiation and then provide `kube_kwargs = {"more": "info"}` at run time which will make
    `kube_kwargs = {"info": "here", "more": "info"}`. *Note*: Keys present in both instantiation
    and runtime will be replaced with the runtime value.

    Args:
        - pod_name (str, optional): The name of a pod in which the command is to be run
        - container_name (str, optional): The name of a container to use in the pod
        - exec_command (list, optional): the command to run in pod_name
        - namespace (str, optional): The Kubernetes namespace of the pod,
            defaults to the `default` namespace
        - kube_kwargs (dict, optional): Optional extra keyword arguments to pass to the
            Kubernetes API (e.g. `{"pretty": "...", "exact": "..."}`)
        - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
            which stored your Kubernetes API Key; this Secret must be a string and in
            BearerToken format
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        pod_name: str = None,
        container_name: str = None,
        exec_command: list = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
        **kwargs: Any
    ):
        self.pod_name = pod_name
        self.namespace = namespace
        self.container_name = container_name
        self.exec_command = exec_command
        self.kube_kwargs = kube_kwargs or {}
        self.kubernetes_api_key_secret = kubernetes_api_key_secret

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "pod_name",
        "container_name",
        "namespace",
        "kube_kwargs",
        "kubernetes_api_key_secret",
        "exec_command",
    )
    def run(
        self,
        pod_name: str = None,
        container_name: str = None,
        exec_command: list = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
    ) -> None:
        """
        Task run method.

        Args:
            - pod_name (str, optional): The name of a pod in which the command is to be run
            - container_name (str, optional): The name of a container to use in the pod
            - exec_command (list, optional): the command to run in pod_name
            - namespace (str, optional): The Kubernetes namespace of the pod,
                defaults to the `default` namespace
            - kube_kwargs (dict, optional): Optional extra keyword arguments to pass to the
                Kubernetes API (e.g. `{"pretty": "...", "exact": "..."}`)
            - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
                which stored your Kubernetes API Key; this Secret must be a string and in
                BearerToken format

        Returns:
            - api_response: If the method is called asynchronously, returns the request thread

        Raises:
            - ValueError: if `pod_name` is `None` or `container_name` is `None`
            - TypeError: `exec_command` is not a list
        """
        if not pod_name or not container_name:
            raise ValueError(
                "The name of a Kubernetes pod and container must be provided."
            )
        if type(exec_command) != list:
            raise TypeError("The command to exec must be provided as a list")

        kube_kwargs = {**self.kube_kwargs, **(kube_kwargs or {})}

        api_client = cast(
            client.CoreV1Api, get_kubernetes_client("pod", kubernetes_api_key_secret)
        )

        api_response = stream(
            api_client.connect_get_namespaced_pod_exec,
            name=pod_name,
            namespace=namespace,
            container=container_name,
            command=exec_command,
            stderr=True,
            stdin=True,
            stdout=True,
            tty=False,
            **kube_kwargs
        )
        return api_response

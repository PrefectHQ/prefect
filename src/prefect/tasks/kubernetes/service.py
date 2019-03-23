from typing import Any

from kubernetes import client, config

from prefect import Task
from prefect.client import Secret
from prefect.utilities.tasks import defaults_from_attrs


class CreateNamespacedService(Task):
    """
    Task for creating a namespaced service on Kubernetes.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    This task will attempt to connect to a Kubernetes cluster in three steps with
    the first successful connection attempt becoming the mode of communication with a
    cluster.

    1. Attempt to use a Prefect Secret that contains a Kubernetes API Key
    2. Attempt in-cluster connection (will only work when running on a Service in a cluster)
    3. Attempt out-of-cluster connection using the default location for a kube config file

    The arguments `body` and `kube_kwargs` will perform an in-place update when the task
    is run. This means that it is possible to provide `body = {"info": "here"}` at
    instantiation and then provide `body = {"more": "info"}` at run time which will make
    `body = {"info": "here", "more": "info"}`. *Note*: Keys present in both instantiation
    and runtime will be replaced with the runtime value.

    Args:
        - body (dict, optional): A dictionary representation of a Kubernetes V1Service
            specification
        - namespace (str, optional): The Kubernetes namespace to create this service in,
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
            - body (dict, optional): A dictionary representation of a Kubernetes V1Service
                specification
            - namespace (str, optional): The Kubernetes namespace to create this service in,
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
            raise ValueError("A dictionary representing a V1Service must be provided.")

        kubernetes_api_key = Secret(kubernetes_api_key_secret).get()

        if kubernetes_api_key:
            configuration = client.Configuration()
            configuration.api_key["authorization"] = kubernetes_api_key
            api_client = client.CoreV1Api(client.ApiClient(configuration))
        else:
            try:
                config.load_incluster_config()
            except config.config_exception.ConfigException:
                config.load_kube_config()

            api_client = client.CoreV1Api()

        body = {**self.body, **(body or {})}
        kube_kwargs = {**self.kube_kwargs, **(kube_kwargs or {})}

        api_client.create_namespaced_service(
            namespace=namespace, body=body, **kube_kwargs
        )


class DeleteNamespacedService(Task):
    """
    Task for deleting a namespaced service on Kubernetes.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    This task will attempt to connect to a Kubernetes cluster in three steps with
    the first successful connection attempt becoming the mode of communication with a
    cluster.

    1. Attempt to use a Prefect Secret that contains a Kubernetes API Key
    2. Attempt in-cluster connection (will only work when running on a Service in a cluster)
    3. Attempt out-of-cluster connection using the default location for a kube config file

    The argument `kube_kwargs` will perform an in-place update when the task
    is run. This means that it is possible to provide `kube_kwargs = {"info": "here"}` at
    instantiation and then provide `kube_kwargs = {"more": "info"}` at run time which will make
    `kube_kwargs = {"info": "here", "more": "info"}`. *Note*: Keys present in both instantiation
    and runtime will be replaced with the runtime value.

    Args:
        - service_name (str, optional): The name of a service to delete
        - namespace (str, optional): The Kubernetes namespace to delete this service from,
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
        service_name: str = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
        **kwargs: Any
    ):
        self.service_name = service_name
        self.namespace = namespace
        self.kube_kwargs = kube_kwargs or {}
        self.kubernetes_api_key_secret = kubernetes_api_key_secret

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "service_name", "namespace", "kube_kwargs", "kubernetes_api_key_secret"
    )
    def run(
        self,
        service_name: str = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
    ) -> None:
        """
        Task run method.

        Args:
            - service_name (str, optional): The name of a service to delete
            - namespace (str, optional): The Kubernetes namespace to delete this service in,
                defaults to the `default` namespace
            - kube_kwargs (dict, optional): Optional extra keyword arguments to pass to the
                Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`)
            - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
                which stored your Kubernetes API Key; this Secret must be a string and in
                BearerToken format

        Raises:
            - ValueError: if `service_name` is `None`
        """
        if not service_name:
            raise ValueError("The name of a Kubernetes service must be provided.")

        kubernetes_api_key = Secret(kubernetes_api_key_secret).get()

        if kubernetes_api_key:
            configuration = client.Configuration()
            configuration.api_key["authorization"] = kubernetes_api_key
            api_client = client.CoreV1Api(client.ApiClient(configuration))
        else:
            try:
                config.load_incluster_config()
            except config.config_exception.ConfigException:
                config.load_kube_config()

            api_client = client.CoreV1Api()

        kube_kwargs = {**self.kube_kwargs, **(kube_kwargs or {})}

        api_client.delete_namespaced_service(
            name=service_name,
            namespace=namespace,
            body=api_client.V1DeleteOptions(),
            **kube_kwargs
        )


class ListNamespacedService(Task):
    """
    Task for listing namespaced services on Kubernetes.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    This task will attempt to connect to a Kubernetes cluster in three steps with
    the first successful connection attempt becoming the mode of communication with a
    cluster.

    1. Attempt to use a Prefect Secret that contains a Kubernetes API Key
    2. Attempt in-cluster connection (will only work when running on a Service in a cluster)
    3. Attempt out-of-cluster connection using the default location for a kube config file

    The argument `kube_kwargs` will perform an in-place update when the task
    is run. This means that it is possible to provide `kube_kwargs = {"info": "here"}` at
    instantiation and then provide `kube_kwargs = {"more": "info"}` at run time which will make
    `kube_kwargs = {"info": "here", "more": "info"}`. *Note*: Keys present in both instantiation
    and runtime will be replaced with the runtime value.

    Args:
        - namespace (str, optional): The Kubernetes namespace to list services from,
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
            - namespace (str, optional): The Kubernetes namespace to list services from,
                defaults to the `default` namespace
            - kube_kwargs (dict, optional): Optional extra keyword arguments to pass to the
                Kubernetes API (e.g. `{"field_selector": "...", "label_selector": "..."}`)
            - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
                which stored your Kubernetes API Key; this Secret must be a string and in
                BearerToken format

        Return:
            - V1ServiceList: a Kubernetes V1ServiceList of the services which are found
        """
        kubernetes_api_key = Secret(kubernetes_api_key_secret).get()

        if kubernetes_api_key:
            configuration = client.Configuration()
            configuration.api_key["authorization"] = kubernetes_api_key
            api_client = client.CoreV1Api(client.ApiClient(configuration))
        else:
            try:
                config.load_incluster_config()
            except config.config_exception.ConfigException:
                config.load_kube_config()

            api_client = client.CoreV1Api()

        kube_kwargs = {**self.kube_kwargs, **(kube_kwargs or {})}

        return api_client.list_namespaced_service(namespace=namespace, **kube_kwargs)


class PatchNamespacedService(Task):
    """
    Task for patching a namespaced service on Kubernetes.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    This task will attempt to connect to a Kubernetes cluster in three steps with
    the first successful connection attempt becoming the mode of communication with a
    cluster.

    1. Attempt to use a Prefect Secret that contains a Kubernetes API Key
    2. Attempt in-cluster connection (will only work when running on a Service in a cluster)
    3. Attempt out-of-cluster connection using the default location for a kube config file

    The arguments `body` and `kube_kwargs` will perform an in-place update when the task
    is run. This means that it is possible to provide `body = {"info": "here"}` at
    instantiation and then provide `body = {"more": "info"}` at run time which will make
    `body = {"info": "here", "more": "info"}`. *Note*: Keys present in both instantiation
    and runtime will be replaced with the runtime value.

    Args:
        - service_name (str, optional): The name of a service to patch
        - body (dict, optional): A dictionary representation of a Kubernetes V1Service
            patch specification
        - namespace (str, optional): The Kubernetes namespace to patch this service in,
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
        service_name: str = None,
        body: dict = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
        **kwargs: Any
    ):
        self.service_name = service_name
        self.body = body or {}
        self.namespace = namespace
        self.kube_kwargs = kube_kwargs or {}
        self.kubernetes_api_key_secret = kubernetes_api_key_secret

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "service_name", "body", "namespace", "kube_kwargs", "kubernetes_api_key_secret"
    )
    def run(
        self,
        service_name: str = None,
        body: dict = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
    ) -> None:
        """
        Task run method.

        Args:
            - service_name (str, optional): The name of a service to patch
            - body (dict, optional): A dictionary representation of a Kubernetes V1Service
                patch specification
            - namespace (str, optional): The Kubernetes namespace to patch this service in,
                defaults to the `default` namespace
            - kube_kwargs (dict, optional): Optional extra keyword arguments to pass to the
                Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`)
            - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
                which stored your Kubernetes API Key; this Secret must be a string and in
                BearerToken format

        Raises:
            - ValueError: if `body` is `None`
            - ValueError: if `service_name` is `None`
        """
        if not body:
            raise ValueError(
                "A dictionary representing a V1Service patch must be provided."
            )

        if not service_name:
            raise ValueError("The name of a Kubernetes service must be provided.")

        kubernetes_api_key = Secret(kubernetes_api_key_secret).get()

        if kubernetes_api_key:
            configuration = client.Configuration()
            configuration.api_key["authorization"] = kubernetes_api_key
            api_client = client.CoreV1Api(client.ApiClient(configuration))
        else:
            try:
                config.load_incluster_config()
            except config.config_exception.ConfigException:
                config.load_kube_config()

            api_client = client.CoreV1Api()

        body = {**self.body, **(body or {})}
        kube_kwargs = {**self.kube_kwargs, **(kube_kwargs or {})}

        api_client.patch_namespaced_service(
            name=service_name, namespace=namespace, body=body, **kube_kwargs
        )


class ReadNamespacedService(Task):
    """
    Task for reading a namespaced service on Kubernetes.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    This task will attempt to connect to a Kubernetes cluster in three steps with
    the first successful connection attempt becoming the mode of communication with a
    cluster.

    1. Attempt to use a Prefect Secret that contains a Kubernetes API Key
    2. Attempt in-cluster connection (will only work when running on a Service in a cluster)
    3. Attempt out-of-cluster connection using the default location for a kube config file

    The argument `kube_kwargs` will perform an in-place update when the task
    is run. This means that it is possible to provide `kube_kwargs = {"info": "here"}` at
    instantiation and then provide `kube_kwargs = {"more": "info"}` at run time which will make
    `kube_kwargs = {"info": "here", "more": "info"}`. *Note*: Keys present in both instantiation
    and runtime will be replaced with the runtime value.

    Args:
        - service_name (str, optional): The name of a service to read
        - namespace (str, optional): The Kubernetes namespace to read this service from,
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
        service_name: str = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
        **kwargs: Any
    ):
        self.service_name = service_name
        self.namespace = namespace
        self.kube_kwargs = kube_kwargs or {}
        self.kubernetes_api_key_secret = kubernetes_api_key_secret

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "service_name", "namespace", "kube_kwargs", "kubernetes_api_key_secret"
    )
    def run(
        self,
        service_name: str = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
    ) -> None:
        """
        Task run method.

        Args:
            - service_name (str, optional): The name of a service to read
            - namespace (str, optional): The Kubernetes namespace to read this service in,
                defaults to the `default` namespace
            - kube_kwargs (dict, optional): Optional extra keyword arguments to pass to the
                Kubernetes API (e.g. `{"pretty": "...", "exact": "..."}`)
            - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
                which stored your Kubernetes API Key; this Secret must be a string and in
                BearerToken format

        Returns:
            - V1Service: a Kubernetes V1Service matching the service that was found

        Raises:
            - ValueError: if `service_name` is `None`
        """
        if not service_name:
            raise ValueError("The name of a Kubernetes service must be provided.")

        kubernetes_api_key = Secret(kubernetes_api_key_secret).get()

        if kubernetes_api_key:
            configuration = client.Configuration()
            configuration.api_key["authorization"] = kubernetes_api_key
            api_client = client.CoreV1Api(client.ApiClient(configuration))
        else:
            try:
                config.load_incluster_config()
            except config.config_exception.ConfigException:
                config.load_kube_config()

            api_client = client.CoreV1Api()

        kube_kwargs = {**self.kube_kwargs, **(kube_kwargs or {})}

        return api_client.read_namespaced_service(
            name=service_name, namespace=namespace, **kube_kwargs
        )


class ReplaceNamespacedService(Task):
    """
    Task for replacing a namespaced service on Kubernetes.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    This task will attempt to connect to a Kubernetes cluster in three steps with
    the first successful connection attempt becoming the mode of communication with a
    cluster.

    1. Attempt to use a Prefect Secret that contains a Kubernetes API Key
    2. Attempt in-cluster connection (will only work when running on a Service in a cluster)
    3. Attempt out-of-cluster connection using the default location for a kube config file

    The arguments `body` and `kube_kwargs` will perform an in-place update when the task
    is run. This means that it is possible to provide `body = {"info": "here"}` at
    instantiation and then provide `body = {"more": "info"}` at run time which will make
    `body = {"info": "here", "more": "info"}`. *Note*: Keys present in both instantiation
    and runtime will be replaced with the runtime value.

    Args:
        - service_name (str, optional): The name of a service to replace
        - body (dict, optional): A dictionary representation of a Kubernetes V1Service
            specification
        - namespace (str, optional): The Kubernetes namespace to patch this service in,
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
        service_name: str = None,
        body: dict = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
        **kwargs: Any
    ):
        self.service_name = service_name
        self.body = body or {}
        self.namespace = namespace
        self.kube_kwargs = kube_kwargs or {}
        self.kubernetes_api_key_secret = kubernetes_api_key_secret

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "service_name", "body", "namespace", "kube_kwargs", "kubernetes_api_key_secret"
    )
    def run(
        self,
        service_name: str = None,
        body: dict = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
    ) -> None:
        """
        Task run method.

        Args:
            - service_name (str, optional): The name of a service to replace
            - body (dict, optional): A dictionary representation of a Kubernetes V1Service
                specification
            - namespace (str, optional): The Kubernetes namespace to patch this service in,
                defaults to the `default` namespace
            - kube_kwargs (dict, optional): Optional extra keyword arguments to pass to the
                Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`)
            - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
                which stored your Kubernetes API Key; this Secret must be a string and in
                BearerToken format

        Raises:
            - ValueError: if `body` is `None`
            - ValueError: if `service_name` is `None`
        """
        if not body:
            raise ValueError("A dictionary representing a V1Service must be provided.")

        if not service_name:
            raise ValueError("The name of a Kubernetes service must be provided.")

        kubernetes_api_key = Secret(kubernetes_api_key_secret).get()

        if kubernetes_api_key:
            configuration = client.Configuration()
            configuration.api_key["authorization"] = kubernetes_api_key
            api_client = client.CoreV1Api(client.ApiClient(configuration))
        else:
            try:
                config.load_incluster_config()
            except config.config_exception.ConfigException:
                config.load_kube_config()

            api_client = client.CoreV1Api()

        body = {**self.body, **(body or {})}
        kube_kwargs = {**self.kube_kwargs, **(kube_kwargs or {})}

        api_client.replace_namespaced_service(
            name=service_name, namespace=namespace, body=body, **kube_kwargs
        )

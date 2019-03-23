from typing import Any

from kubernetes import client, config

from prefect import Task
from prefect.client import Secret
from prefect.utilities.tasks import defaults_from_attrs


class CreateNamespacedJob(Task):
    """
    Task for creating a namespaced job on Kubernetes.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    This task will attempt to connect to a Kubernetes cluster in three steps with
    the first successful connection attempt becoming the mode of communication with a
    cluster.

    1. Attempt to use a Prefect Secret that contains a Kubernetes API Key
    2. Attempt in-cluster connection (will only work when running on a Pod in a cluster)
    3. Attempt out-of-cluster connection using the default location for a kube config file

    The arguments `body` and `kube_kwargs` will perform an in-place update when the task
    is run. This means that it is possible to provide `body = {"info": "here"}` at
    instantiation and then provide `body = {"more": "info"}` at run time which will make
    `body = {"info": "here", "more": "info"}`. *Note*: Keys present in both instantiation
    and runtime will be replaced with the runtime value.

    Args:
        - body (dict, optional): A dictionary representation of a Kubernetes V1Job
            specification
        - namespace (str, optional): The Kubernetes namespace to create this job in,
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
            - body (dict, optional): A dictionary representation of a Kubernetes V1Job
                specification
            - namespace (str, optional): The Kubernetes namespace to create this job in,
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
            raise ValueError("A dictionary representing a V1Job must be provided.")

        kubernetes_api_key = Secret(kubernetes_api_key_secret).get()

        if kubernetes_api_key:
            configuration = client.Configuration()
            configuration.api_key["authorization"] = kubernetes_api_key
            api_client = client.BatchV1Api(client.ApiClient(configuration))
        else:
            try:
                config.load_incluster_config()
            except config.config_exception.ConfigException:
                config.load_kube_config()

            api_client = client.BatchV1Api()

        body = {**self.body, **(body or {})}
        kube_kwargs = {**self.kube_kwargs, **(kube_kwargs or {})}

        api_client.create_namespaced_job(namespace=namespace, body=body, **kube_kwargs)


class DeleteNamespacedJob(Task):
    """
    Task for deleting a namespaced job on Kubernetes.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    This task will attempt to connect to a Kubernetes cluster in three steps with
    the first successful connection attempt becoming the mode of communication with a
    cluster.

    1. Attempt to use a Prefect Secret that contains a Kubernetes API Key
    2. Attempt in-cluster connection (will only work when running on a Pod in a cluster)
    3. Attempt out-of-cluster connection using the default location for a kube config file

    The argument `kube_kwargs` will perform an in-place update when the task
    is run. This means that it is possible to provide `kube_kwargs = {"info": "here"}` at
    instantiation and then provide `kube_kwargs = {"more": "info"}` at run time which will make
    `kube_kwargs = {"info": "here", "more": "info"}`. *Note*: Keys present in both instantiation
    and runtime will be replaced with the runtime value.

    Args:
        - job_name (str, optional): The name of a job to delete
        - namespace (str, optional): The Kubernetes namespace to delete this job from,
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
        job_name: str = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
        **kwargs: Any
    ):
        self.job_name = job_name
        self.namespace = namespace
        self.kube_kwargs = kube_kwargs or {}
        self.kubernetes_api_key_secret = kubernetes_api_key_secret

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "job_name", "namespace", "kube_kwargs", "kubernetes_api_key_secret"
    )
    def run(
        self,
        job_name: str = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
    ) -> None:
        """
        Task run method.

        Args:
            - job_name (str, optional): The name of a job to delete
            - namespace (str, optional): The Kubernetes namespace to delete this job in,
                defaults to the `default` namespace
            - kube_kwargs (dict, optional): Optional extra keyword arguments to pass to the
                Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`)
            - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
                which stored your Kubernetes API Key; this Secret must be a string and in
                BearerToken format

        Raises:
            - ValueError: if `job_name` is `None`
        """
        if not job_name:
            raise ValueError("The name of a Kubernetes job must be provided.")

        kubernetes_api_key = Secret(kubernetes_api_key_secret).get()

        if kubernetes_api_key:
            configuration = client.Configuration()
            configuration.api_key["authorization"] = kubernetes_api_key
            api_client = client.BatchV1Api(client.ApiClient(configuration))
        else:
            try:
                config.load_incluster_config()
            except config.config_exception.ConfigException:
                config.load_kube_config()

            api_client = client.BatchV1Api()

        kube_kwargs = {**self.kube_kwargs, **(kube_kwargs or {})}

        api_client.delete_namespaced_job(
            name=job_name,
            namespace=namespace,
            body=api_client.V1DeleteOptions(),
            **kube_kwargs
        )


class ListNamespacedJob(Task):
    """
    Task for listing namespaced jobs on Kubernetes.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    This task will attempt to connect to a Kubernetes cluster in three steps with
    the first successful connection attempt becoming the mode of communication with a
    cluster.

    1. Attempt to use a Prefect Secret that contains a Kubernetes API Key
    2. Attempt in-cluster connection (will only work when running on a Pod in a cluster)
    3. Attempt out-of-cluster connection using the default location for a kube config file

    The argument `kube_kwargs` will perform an in-place update when the task
    is run. This means that it is possible to provide `kube_kwargs = {"info": "here"}` at
    instantiation and then provide `kube_kwargs = {"more": "info"}` at run time which will make
    `kube_kwargs = {"info": "here", "more": "info"}`. *Note*: Keys present in both instantiation
    and runtime will be replaced with the runtime value.

    Args:
        - namespace (str, optional): The Kubernetes namespace to list jobs from,
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
            - namespace (str, optional): The Kubernetes namespace to list jobs from,
                defaults to the `default` namespace
            - kube_kwargs (dict, optional): Optional extra keyword arguments to pass to the
                Kubernetes API (e.g. `{"field_selector": "...", "label_selector": "..."}`)
            - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
                which stored your Kubernetes API Key; this Secret must be a string and in
                BearerToken format

        Return:
            - V1JobList: a Kubernetes V1JobList of the jobs which are found
        """
        kubernetes_api_key = Secret(kubernetes_api_key_secret).get()

        if kubernetes_api_key:
            configuration = client.Configuration()
            configuration.api_key["authorization"] = kubernetes_api_key
            api_client = client.BatchV1Api(client.ApiClient(configuration))
        else:
            try:
                config.load_incluster_config()
            except config.config_exception.ConfigException:
                config.load_kube_config()

            api_client = client.BatchV1Api()

        kube_kwargs = {**self.kube_kwargs, **(kube_kwargs or {})}

        return api_client.list_namespaced_job(namespace=namespace, **kube_kwargs)


class PatchNamespacedJob(Task):
    """
    Task for patching a namespaced job on Kubernetes.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    This task will attempt to connect to a Kubernetes cluster in three steps with
    the first successful connection attempt becoming the mode of communication with a
    cluster.

    1. Attempt to use a Prefect Secret that contains a Kubernetes API Key
    2. Attempt in-cluster connection (will only work when running on a Pod in a cluster)
    3. Attempt out-of-cluster connection using the default location for a kube config file

    The arguments `body` and `kube_kwargs` will perform an in-place update when the task
    is run. This means that it is possible to provide `body = {"info": "here"}` at
    instantiation and then provide `body = {"more": "info"}` at run time which will make
    `body = {"info": "here", "more": "info"}`. *Note*: Keys present in both instantiation
    and runtime will be replaced with the runtime value.

    Args:
        - job_name (str, optional): The name of a job to patch
        - body (dict, optional): A dictionary representation of a Kubernetes V1Job
            patch specification
        - namespace (str, optional): The Kubernetes namespace to patch this job in,
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
        job_name: str = None,
        body: dict = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
        **kwargs: Any
    ):
        self.job_name = job_name
        self.body = body or {}
        self.namespace = namespace
        self.kube_kwargs = kube_kwargs or {}
        self.kubernetes_api_key_secret = kubernetes_api_key_secret

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "job_name", "body", "namespace", "kube_kwargs", "kubernetes_api_key_secret"
    )
    def run(
        self,
        job_name: str = None,
        body: dict = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
    ) -> None:
        """
        Task run method.

        Args:
            - job_name (str, optional): The name of a job to patch
            - body (dict, optional): A dictionary representation of a Kubernetes V1Job
                patch specification
            - namespace (str, optional): The Kubernetes namespace to patch this job in,
                defaults to the `default` namespace
            - kube_kwargs (dict, optional): Optional extra keyword arguments to pass to the
                Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`)
            - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
                which stored your Kubernetes API Key; this Secret must be a string and in
                BearerToken format

        Raises:
            - ValueError: if `body` is `None`
            - ValueError: if `job_name` is `None`
        """
        if not body:
            raise ValueError(
                "A dictionary representing a V1Job patch must be provided."
            )

        if not job_name:
            raise ValueError("The name of a Kubernetes job must be provided.")

        kubernetes_api_key = Secret(kubernetes_api_key_secret).get()

        if kubernetes_api_key:
            configuration = client.Configuration()
            configuration.api_key["authorization"] = kubernetes_api_key
            api_client = client.BatchV1Api(client.ApiClient(configuration))
        else:
            try:
                config.load_incluster_config()
            except config.config_exception.ConfigException:
                config.load_kube_config()

            api_client = client.BatchV1Api()

        body = {**self.body, **(body or {})}
        kube_kwargs = {**self.kube_kwargs, **(kube_kwargs or {})}

        api_client.patch_namespaced_job(
            name=job_name, namespace=namespace, body=body, **kube_kwargs
        )


class ReadNamespacedJob(Task):
    """
    Task for reading a namespaced job on Kubernetes.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    This task will attempt to connect to a Kubernetes cluster in three steps with
    the first successful connection attempt becoming the mode of communication with a
    cluster.

    1. Attempt to use a Prefect Secret that contains a Kubernetes API Key
    2. Attempt in-cluster connection (will only work when running on a Pod in a cluster)
    3. Attempt out-of-cluster connection using the default location for a kube config file

    The argument `kube_kwargs` will perform an in-place update when the task
    is run. This means that it is possible to provide `kube_kwargs = {"info": "here"}` at
    instantiation and then provide `kube_kwargs = {"more": "info"}` at run time which will make
    `kube_kwargs = {"info": "here", "more": "info"}`. *Note*: Keys present in both instantiation
    and runtime will be replaced with the runtime value.

    Args:
        - job_name (str, optional): The name of a job to read
        - namespace (str, optional): The Kubernetes namespace to read this job from,
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
        job_name: str = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
        **kwargs: Any
    ):
        self.job_name = job_name
        self.namespace = namespace
        self.kube_kwargs = kube_kwargs or {}
        self.kubernetes_api_key_secret = kubernetes_api_key_secret

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "job_name", "namespace", "kube_kwargs", "kubernetes_api_key_secret"
    )
    def run(
        self,
        job_name: str = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
    ) -> None:
        """
        Task run method.

        Args:
            - job_name (str, optional): The name of a job to read
            - namespace (str, optional): The Kubernetes namespace to read this job in,
                defaults to the `default` namespace
            - kube_kwargs (dict, optional): Optional extra keyword arguments to pass to the
                Kubernetes API (e.g. `{"pretty": "...", "exact": "..."}`)
            - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
                which stored your Kubernetes API Key; this Secret must be a string and in
                BearerToken format

        Returns:
            - V1Job: a Kubernetes V1Job matching the job that was found

        Raises:
            - ValueError: if `job_name` is `None`
        """
        if not job_name:
            raise ValueError("The name of a Kubernetes job must be provided.")

        kubernetes_api_key = Secret(kubernetes_api_key_secret).get()

        if kubernetes_api_key:
            configuration = client.Configuration()
            configuration.api_key["authorization"] = kubernetes_api_key
            api_client = client.BatchV1Api(client.ApiClient(configuration))
        else:
            try:
                config.load_incluster_config()
            except config.config_exception.ConfigException:
                config.load_kube_config()

            api_client = client.BatchV1Api()

        kube_kwargs = {**self.kube_kwargs, **(kube_kwargs or {})}

        return api_client.read_namespaced_job(
            name=job_name, namespace=namespace, **kube_kwargs
        )


class ReplaceNamespacedJob(Task):
    """
    Task for replacing a namespaced job on Kubernetes.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    This task will attempt to connect to a Kubernetes cluster in three steps with
    the first successful connection attempt becoming the mode of communication with a
    cluster.

    1. Attempt to use a Prefect Secret that contains a Kubernetes API Key
    2. Attempt in-cluster connection (will only work when running on a Pod in a cluster)
    3. Attempt out-of-cluster connection using the default location for a kube config file

    The arguments `body` and `kube_kwargs` will perform an in-place update when the task
    is run. This means that it is possible to provide `body = {"info": "here"}` at
    instantiation and then provide `body = {"more": "info"}` at run time which will make
    `body = {"info": "here", "more": "info"}`. *Note*: Keys present in both instantiation
    and runtime will be replaced with the runtime value.

    Args:
        - job_name (str, optional): The name of a job to replace
        - body (dict, optional): A dictionary representation of a Kubernetes V1Job
            specification
        - namespace (str, optional): The Kubernetes namespace to patch this job in,
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
        job_name: str = None,
        body: dict = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
        **kwargs: Any
    ):
        self.job_name = job_name
        self.body = body or {}
        self.namespace = namespace
        self.kube_kwargs = kube_kwargs or {}
        self.kubernetes_api_key_secret = kubernetes_api_key_secret

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "job_name", "body", "namespace", "kube_kwargs", "kubernetes_api_key_secret"
    )
    def run(
        self,
        job_name: str = None,
        body: dict = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
    ) -> None:
        """
        Task run method.

        Args:
            - job_name (str, optional): The name of a job to replace
            - body (dict, optional): A dictionary representation of a Kubernetes V1Job
                specification
            - namespace (str, optional): The Kubernetes namespace to patch this job in,
                defaults to the `default` namespace
            - kube_kwargs (dict, optional): Optional extra keyword arguments to pass to the
                Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`)
            - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
                which stored your Kubernetes API Key; this Secret must be a string and in
                BearerToken format

        Raises:
            - ValueError: if `body` is `None`
            - ValueError: if `job_name` is `None`
        """
        if not body:
            raise ValueError("A dictionary representing a V1Job must be provided.")

        if not job_name:
            raise ValueError("The name of a Kubernetes job must be provided.")

        kubernetes_api_key = Secret(kubernetes_api_key_secret).get()

        if kubernetes_api_key:
            configuration = client.Configuration()
            configuration.api_key["authorization"] = kubernetes_api_key
            api_client = client.BatchV1Api(client.ApiClient(configuration))
        else:
            try:
                config.load_incluster_config()
            except config.config_exception.ConfigException:
                config.load_kube_config()

            api_client = client.BatchV1Api()

        body = {**self.body, **(body or {})}
        kube_kwargs = {**self.kube_kwargs, **(kube_kwargs or {})}

        api_client.replace_namespaced_job(
            name=job_name, namespace=namespace, body=body, **kube_kwargs
        )

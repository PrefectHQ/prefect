from kubernetes import client, config

from prefect import Task
from prefect.client import Secret
from prefect.utilities.tasks import defaults_from_attrs


class CreateNamespacedJob(Task):
    """
    Task for creating a namespaced job on Kubernetes.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    This task has will attempt to connect to a Kubernetes cluster in three steps with
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
            Kubernetes API (e.g. {"pretty": "...", "dry_run": "..."})
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
        **kwargs
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
    ):
        """
        Task run method.

        Args:
            - body (dict, optional): A dictionary representation of a Kubernetes V1Job
                specification
            - namespace (str, optional): The Kubernetes namespace to create this job in,
                defaults to the `default` namespace
            - kube_kwargs (dict, optional): Optional extra keyword arguments to pass to the
                Kubernetes API (e.g. {"pretty": "...", "dry_run": "..."})
            - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
                which stored your Kubernetes API Key; this Secret must be a string and in
                BearerToken format
            - **kwargs (dict, optional): additional keyword arguments to pass to the Task
                constructor
        """
        if not body:
            raise ValueError("A dictionary representing a V1Job must be provided.")

        kubernetes_api_key = Secret(kubernetes_api_key_secret).get()

        if kubernetes_api_key:
            configuration = client.Configuration()
            configuration.api_key["authorization"] = kubernetes_api_key
            self.client = client.BatchV1Api(client.ApiClient(configuration))
        else:
            try:
                config.load_incluster_config()
            except config.config_exception.ConfigException:
                config.load_kube_config()

            self.client = client.BatchV1Api()

        self.body.update(body or {})
        self.kube_kwargs.update(kube_kwargs or {})

        self.client.create_namespaced_job(
            namespace=namespace, body=self.body, **kube_kwargs
        )

class DeleteNamespacedJob(Task):
    pass

class ListNamespacedJob(Task):
    pass

class PatchNamespacedJob(Task):
    pass

class ReadNamespacedJob(Task):
    pass

class ReplaceNamespacedJob(Task):
    pass
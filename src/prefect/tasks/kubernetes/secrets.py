import base64

from typing import Any, Callable, Optional
from typing import cast as typing_cast
from kubernetes import client

from prefect.tasks.secrets.base import SecretBase
from prefect.utilities.tasks import defaults_from_attrs
from prefect.utilities.kubernetes import get_kubernetes_client


class KubernetesSecret(SecretBase):
    """
    Task for loading a Prefect secret from a kubernetes secret.

    This task will read a secret from kubernetes, returning the decoded value
    associated with `secret_key`. All initialization arguments can optionally
    be provided or overwritten at runtime.

    Note that depending on cluster configuration, you may need to ensure you
    have the proper RBAC permissions to read the secret.

    1. Attempt to use a Prefect Secret that contains a Kubernetes API Key. If
    `kubernetes_api_key_secret` = `None` then it will attempt the next two connection
    methods. By default the value is `KUBERNETES_API_KEY` so providing `None` acts as
    an override for the remote connection.
    2. Attempt in-cluster connection (will only work when running on a Pod in a cluster)
    3. Attempt out-of-cluster connection using the default location for a kube config file


    Args:
        - secret_name (string, optional): The name of the kubernetes secret object
        - secret_key (string, optional): The key to look for in the kubernetes data
        - namespace (str, optional): The Kubernetes namespace to read the secret from,
            defaults to the `default` namespace.
        - kube_kwargs (dict, optional): Optional extra keyword arguments to pass to the
            Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`)
        - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
            which stored your Kubernetes API Key; this Secret must be a string and in
            BearerToken format
        - cast (Callable[[Any], Any], optional): If provided, this will
            be called on the secret to transform it before returning. An example
            use might be passing in `json.loads` to load values from stored JSON.
        - raise_if_missing (bool): if True, an error will be raised if the secret is not found.
        - **kwargs (dict, optional): additional keyword arguments to pass to the Task
            constructor
    """

    def __init__(
        self,
        secret_name: Optional[str] = None,
        secret_key: Optional[str] = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
        cast: Callable[[Any], Any] = None,
        raise_if_missing: bool = False,
        **kwargs: Any,
    ):
        self.secret_name = secret_name
        self.secret_key = secret_key
        self.namespace = namespace
        self.kube_kwargs = kube_kwargs or {}
        self.kubernetes_api_key_secret = kubernetes_api_key_secret
        self.cast = cast
        self.raise_if_missing = raise_if_missing
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "secret_name",
        "secret_key",
        "namespace",
        "kube_kwargs",
        "kubernetes_api_key_secret",
    )
    def run(
        self,
        secret_name: Optional[str] = None,
        secret_key: Optional[str] = None,
        namespace: str = "default",
        kube_kwargs: dict = None,
        kubernetes_api_key_secret: str = "KUBERNETES_API_KEY",
    ):
        """
        Returns the value of an kubenetes secret after applying an optional `cast` function.

        Args:
            - secret_name (string, optional): The name of the kubernetes secret object
            - secret_key (string, optional): The key to look for in the kubernetes data
            - namespace (str, optional): The Kubernetes namespace to read the secret from,
                defaults to the `default` namespace.
            - kube_kwargs (dict, optional): Optional extra keyword arguments to pass to the
                Kubernetes API (e.g. `{"pretty": "...", "dry_run": "..."}`)
            - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
                which stored your Kubernetes API Key; this Secret must be a string and in
                BearerToken format

        Raises:
            - ValueError: if `raise_is_missing` is `True` and the kubernetes secret was not found.
                The value of secret_name and secret_key are mandatory as well
        """
        if not secret_name:
            raise ValueError("The name of a Kubernetes secret must be provided.")

        if not secret_key:
            raise ValueError("The key of the secret must be provided.")

        api_client = typing_cast(
            client.CoreV1Api,
            get_kubernetes_client("secret", kubernetes_api_key_secret),
        )

        secret_data = api_client.read_namespaced_secret(
            name=secret_name, namespace=namespace
        ).data

        if secret_key not in secret_data:
            if self.raise_if_missing:
                raise ValueError(f"Cannot find the key {secret_key} in {secret_name} ")
            else:
                return None

        decoded_secret = base64.b64decode(secret_data[secret_key]).decode("utf8")

        return decoded_secret if self.cast is None else self.cast(decoded_secret)

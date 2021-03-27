"""
Utility functions for interacting with Kubernetes API.
"""
from typing import Union

from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException

from prefect.client import Secret


K8S_CLIENTS = {
    "job": client.BatchV1Api,
    "pod": client.CoreV1Api,
    "service": client.CoreV1Api,
    "deployment": client.AppsV1Api,
}


KubernetesClient = Union[client.BatchV1Api, client.CoreV1Api, client.AppsV1Api]


def get_kubernetes_client(
    resource: str, kubernetes_api_key_secret: str = "KUBERNETES_API_KEY"
) -> KubernetesClient:
    """
    Utility function for loading kubernetes client object for a given resource.

    It will attempt to connect to a Kubernetes cluster in three steps with
    the first successful connection attempt becoming the mode of communication with a
    cluster.

    1. Attempt to use a Prefect Secret that contains a Kubernetes API Key. If
    `kubernetes_api_key_secret` = `None` then it will attempt the next two connection
    methods. By default the value is `KUBERNETES_API_KEY` so providing `None` acts as
    an override for the remote connection.
    2. Attempt in-cluster connection (will only work when running on a Pod in a cluster)
    3. Attempt out-of-cluster connection using the default location for a kube config file

    Args:
        - resource (str): the name of the resource to retrieve a client for. Currently
            you can use one of these values: `job`, `pod`, `service`, `deployment`
        - kubernetes_api_key_secret (str, optional): the name of the Prefect Secret
            which stored your Kubernetes API Key; this Secret must be a string and in
            BearerToken format

    Returns:
        - KubernetesClient: an initialized and authenticated Kubernetes Client
    """
    k8s_client = K8S_CLIENTS[resource]

    kubernetes_api_key = None
    if kubernetes_api_key_secret:
        kubernetes_api_key = Secret(kubernetes_api_key_secret).get()

    if kubernetes_api_key:
        configuration = client.Configuration()
        configuration.api_key["authorization"] = kubernetes_api_key
        k8s_client = k8s_client(client.ApiClient(configuration))
    else:
        try:
            config.load_incluster_config()
        except ConfigException:
            config.load_kube_config()

        k8s_client = k8s_client()

    return k8s_client

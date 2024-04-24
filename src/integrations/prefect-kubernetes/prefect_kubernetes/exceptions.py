"""Module to define common exceptions within `prefect_kubernetes`."""

from kubernetes.client.exceptions import ApiException, OpenApiException


class KubernetesJobDefinitionError(OpenApiException):
    """An exception for when a Kubernetes job definition is invalid."""


class KubernetesJobFailedError(OpenApiException):
    """An exception for when a Kubernetes job fails."""


class KubernetesResourceNotFoundError(ApiException):
    """An exception for when a Kubernetes resource cannot be found by a client."""


class KubernetesJobTimeoutError(OpenApiException):
    """An exception for when a Kubernetes job times out."""

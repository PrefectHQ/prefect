from prefect.exceptions import PrefectException


class ObjectNotFoundError(PrefectException):
    """
    Error raised by the Prefect REST API when a requested object is not found.

    If thrown during a request, this exception will be caught and
    a 404 response will be returned.
    """


class OrchestrationError(PrefectException):
    """An error raised while orchestrating a state transition"""


class MissingVariableError(PrefectException):
    """An error raised by the Prefect REST API when attempting to create or update a
    deployment with missing required variables.
    """


class FlowRunGraphTooLarge(Exception):
    """Raised to indicate that a flow run's graph has more nodes that the configured
    maximum"""

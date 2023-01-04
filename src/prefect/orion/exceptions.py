from prefect.exceptions import PrefectException


class ObjectNotFoundError(PrefectException):
    """
    Error raised by the Orion API when a requested object is not found.

    If thrown during a request, this exception will be caught and
    a 404 response will be returned.
    """


class OrchestrationError(PrefectException):
    """An error raised while orchestrating a state transition"""

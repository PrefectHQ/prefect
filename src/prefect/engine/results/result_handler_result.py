from typing import Any, List, Tuple, Type, Dict

from prefect.engine.result import Result
from prefect.engine.results import (
    AzureResult,
    ConstantResult,
    GCSResult,
    LocalResult,
    PrefectResult,
    SecretResult,
    S3Result,
)
from prefect.engine.result_handlers import (
    AzureResultHandler,
    ConstantResultHandler,
    GCSResultHandler,
    JSONResultHandler,
    LocalResultHandler,
    ResultHandler,
    S3ResultHandler,
    SecretResultHandler,
)


# a list of tuples of the form (ResultHandlerType, dict(attributes=init_kwargs), ResultType)

CONVERSIONS = [
    (ConstantResultHandler, dict(value="value"), ConstantResult),
    (GCSResultHandler, dict(bucket="bucket"), GCSResult),
    (JSONResultHandler, dict(), PrefectResult),
    (LocalResultHandler, dict(dir="dir"), LocalResult),
    (S3ResultHandler, dict(bucket="bucket", boto3_kwargs="boto3_kwargs"), S3Result),
    (SecretResultHandler, dict(secret_task="secret_task"), SecretResult),
    (
        AzureResultHandler,
        dict(
            container="container",
            connection_string="connection_string",
            connection_string_secret="connection_string_secret",
        ),
        AzureResult,
    ),
]  # type: List[Tuple[Type[ResultHandler], Dict[Any, Any], Type[Result]]]


class ResultHandlerResult(Result):
    def __init__(self, result_handler: ResultHandler, **kwargs: Any):
        kwargs.update(result_handler=result_handler)
        super().__init__(**kwargs)

    @classmethod
    def from_result_handler(cls, result_handler: ResultHandler) -> Result:
        for handler_type, attr_map, result_type in CONVERSIONS:
            if isinstance(result_handler, handler_type):
                kwargs = {
                    kwarg: getattr(result_handler, attr, None)
                    for attr, kwarg in attr_map.items()
                }
                return result_type(**kwargs)
        return cls(result_handler)

    def read(self, location: str) -> Result:
        """
        Exposes the read method of the underlying custom result handler fitting the Result
        interface.  Returns a new Result with the value read from the custom result handler.

        Args:
            - location (str): the location to read from

        Returns:
            - Result: returns a copy of this Result with the value set
        """
        new = self.copy()
        new.value = self.result_handler.read(location)
        return new

    def write(self, value_: Any, **kwargs: Any) -> Result:
        """
        Exposes the write method of the underlying custom result handler fitting the Result
        interface.

        Args:
            - value_ (Any): the value to write and attach to the result
            - **kwargs (Any, optional): unused, for interface compatibility

        Returns:
            - Result: returns a copy of this Result with the location and value set
        """
        new = self.copy()
        new.location = self.result_handler.write(value_)
        new.value = value_
        return new

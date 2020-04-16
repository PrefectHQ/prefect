from typing import Any

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
]


class ResultHandlerResult(Result):
    def __init__(self, result_handler: ResultHandler, **kwargs: Any):
        self.result_handler = result_handler
        super().__init__(**kwargs)

    @classmethod
    def from_result_handler(cls, result_handler: ResultHandler) -> Result:
        for handler_type, attr_map, result_type in CONVERSIONS:
            if isinstance(result_handler, handler_type):
                kwargs = {
                    kwarg: getattr(result_handler, attr, None)
                    for attr, kwarg in attr_map.items()
                }
                return handler_type(**kwargs)
        return cls(result_handler)

    def read(self, loc: str = None) -> Result:
        """
        Exposes the read method of the underlying custom result handler fitting the Result interface.
        Returns a new Result with the value read from the custom result handler.
        Args:
            - loc:

        Returns:
            - Result: returns a copy of this Result with the value set

        """
        new = self.copy()
        value = self.result_handler.read(loc)
        new.value = value
        return new

    def write(self, value: Any, **kwargs) -> Result:
        """
        Exposes the write method of the underlying custom result handler fitting the Result interfacec.
        Args:
            - result: the value to write and attach to the result

        Returns:
            - Result: returns a copy of this Result with the filepath and value set

        """
        new = self.copy()
        loc = self.result_handler.write(value)
        new.filepath = loc
        new.value = value
        return new

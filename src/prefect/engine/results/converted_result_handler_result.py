from typing import Any

from prefect.engine.result import Result
from prefect.engine.results import (
    S3Result,
    GCSResult,
    PrefectResult,
    ConstantResult,
)  # , AzureResult, SecretResult
from prefect.engine.result_handlers import (
    ResultHandler,
    S3ResultHandler,
    GCSResultHandler,
)  # todo: add the rest


class ConvertedResultHandlerResult(Result):
    def __init__(self, result_handler: ResultHandler, **kwargs):
        self.result_handler = result_handler
        super().__init__(**kwargs)

    @classmethod
    def from_result_handler(cls, result_handler: ResultHandler):
        if isinstance(result_handler, S3ResultHandler):
            kwargs = {
                "bucket": result_handler.bucket,
                "credentials_secret": result_handler.aws_credentials_secret,
                "boto3_kwargs": result_handler.boto3_kwargs,
            }
            return S3Result(**kwargs)

        elif isinstance(result_handler, GCSResultHandler):
            kwargs = {
                "bucket": result_handler.bucket,
                "credentials_secret": result_handler.credentials_secret,
            }
            return GCSResult(**kwargs)

        # do this for the other ones
        #
        #
        # seriously
        else:
            # this is actually a custom result handler from the user
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

import prefect
from prefect.engine.result.base import (
    Result,
    ResultInterface,
    NoResult,
    NoResultType,
    SafeResult,
)
from prefect.engine.result.gcs_result import GCSResult
from prefect.engine.result.s3_result import S3Result

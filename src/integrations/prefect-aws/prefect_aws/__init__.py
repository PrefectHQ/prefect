from . import _version
from .credentials import AwsCredentials, MinIOCredentials
from .client_parameters import AwsClientParameters
from .lambda_function import LambdaFunction
from .s3 import S3Bucket
from .ecs import ECSTask
from .secrets_manager import AwsSecret
from .workers import ECSWorker

from prefect._internal.compatibility.deprecated import (
    register_renamed_module,
)

register_renamed_module(
    "prefect_aws.projects", "prefect_aws.deployments", start_date="Jun 2023"
)

__all__ = [
    "AwsCredentials",
    "AwsClientParameters",
    "LambdaFunction",
    "MinIOCredentials",
    "S3Bucket",
    "ECSTask",
    "AwsSecret",
    "ECSWorker",
]

__version__ = _version.__version__

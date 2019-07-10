"""
This module contains a collection of tasks for interacting with AWS resources.

Note that all tasks require a Prefect Secret called `"AWS_CREDENTIALS"` that should be a JSON
document with two keys: `"ACCESS_KEY"` and `"SECRET_ACCESS_KEY"`.
"""
try:
    from prefect.tasks.aws.s3 import S3Download, S3Upload
    from prefect.tasks.aws.lambda_function import (
        LambdaCreate,
        LambdaDelete,
        LambdaInvoke,
        LambdaList,
    )
    from prefect.tasks.aws.step_function import StepActivate
except ImportError:
    raise ImportError(
        'Using `prefect.tasks.aws` requires Prefect to be installed with the "aws" extra.'
    )

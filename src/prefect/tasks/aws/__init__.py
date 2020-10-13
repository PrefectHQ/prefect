"""
This module contains a collection of tasks for interacting with AWS resources.

All AWS related tasks can be authenticated using the `AWS_CREDENTIALS` Prefect Secret that should be a dictionary with two keys: `"ACCESS_KEY"` and `"SECRET_ACCESS_KEY"`.  See [Third Party Authentication](../../../orchestration/recipes/third_party_auth.html) for more information.
"""
try:
    from prefect.tasks.aws.s3 import S3Download, S3Upload, S3List
    from prefect.tasks.aws.lambda_function import (
        LambdaCreate,
        LambdaDelete,
        LambdaInvoke,
        LambdaList,
    )
    from prefect.tasks.aws.step_function import StepActivate
    from prefect.tasks.aws.secrets_manager import AWSSecretsManager
    from prefect.tasks.aws.batch import BatchSubmit
    from prefect.tasks.aws.client_waiter import AWSClientWait
except ImportError as err:
    raise ImportError(
        'Using `prefect.tasks.aws` requires Prefect to be installed with the "aws" extra.'
    ) from err

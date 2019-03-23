try:
    from prefect.tasks.aws.s3 import S3Download, S3Upload
except ImportError:
    raise ImportError(
        'Using `prefect.tasks.aws` requires Prefect to be installed with the "aws" extra.'
    )

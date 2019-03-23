try:
    from prefect.tasks.aws.s3 import S3DownloadTask, S3UploadTask
except ImportError:
    raise ImportError(
        'Using `prefect.tasks.aws` requires Prefect to be installed with the "aws" extra.'
    )

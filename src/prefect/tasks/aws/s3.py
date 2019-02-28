import boto3
import json
import io
import uuid

from prefect import Task
from prefect.client import Secret
from prefect.utilities.tasks import defaults_from_attrs


class S3DownloadTask(Task):
    def __init__(self, aws_credentials_secret: str = "AWS_CREDENTIALS", bucket_name: str = None, **kwargs):
        self.aws_credentials_secret = aws_credentials_secret
        self.bucket_name = bucket_name
        super().__init__(**kwargs)

    @defaults_from_attrs('aws_credentials_secret', 'bucket_name')
    def run(self, key: str = None, aws_credentials_secret: str = None, bucket_name: str = None):
        ## get AWS credentials
        aws_credentials = json.loads(Secret(aws_credentials_secret).get())
        aws_access_key = aws_credentials['ACCESS_KEY']
        aws_secret_access_key = aws_credentials['SECRET_ACCESS_KEY']
        s3_client = boto3.client('s3', aws_access_key_id=aws_access_key, aws_secret_access_key=aws_secret_access_key)

        stream = io.BytesIO()

        ## download
        s3_client.download_fileobj(Bucket=bucket_name, Key=key, Fileobj=stream)

        ## prepare data and return
        stream.seek(0)
        output = stream.read()
        return output.decode()


class S3UploadTask(Task):
    def __init__(self, aws_credentials_secret: str = "AWS_CREDENTIALS", bucket_name: str = None, **kwargs):
        self.aws_credentials_secret = aws_credentials_secret
        self.bucket_name = bucket_name
        super().__init__(**kwargs)

    @defaults_from_attrs('aws_credentials_secret', 'bucket_name')
    def run(self, data: str, key: str = None, aws_credentials_secret: str = None, bucket_name: str = None):
        ## get AWS credentials
        aws_credentials = json.loads(Secret(aws_credentials_secret).get())
        aws_access_key = aws_credentials['ACCESS_KEY']
        aws_secret_access_key = aws_credentials['SECRET_ACCESS_KEY']
        s3_client = boto3.client('s3', aws_access_key_id=aws_access_key, aws_secret_access_key=aws_secret_access_key)

        ## prepare data
        try:
            stream = io.BytesIO(data)
        except TypeError:
            stream = io.BytesIO(data.encode())

        ## create key if not provided
        if key is None:
            key = uuid.uuid4()

        ## upload
        s3_client.upload_fileobj(stream, Bucket=bucket_name, Key=key)
        return key

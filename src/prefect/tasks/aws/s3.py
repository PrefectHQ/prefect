import gzip
import io
import uuid
import pendulum

from prefect import Task
from prefect.utilities.aws import get_boto_client
from prefect.utilities.tasks import defaults_from_attrs


class S3Download(Task):
    """
    Task for downloading data from an S3 bucket and returning it as a string.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    For authentication, there are two options: you can set the `AWS_CREDENTIALS` Prefect Secret
    containing your AWS access keys which will be passed directly to the `boto3` client, or you
    can [configure your flow's runtime
    environment](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#guide-configuration)
    for `boto3`.

    Args:
        - bucket (str, optional): the name of the S3 Bucket to download from
        - boto_kwargs (dict, optional): additional keyword arguments to forward to the boto client.
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(self, bucket: str = None, boto_kwargs: dict = None, **kwargs):
        self.bucket = bucket

        if boto_kwargs is None:
            self.boto_kwargs = {}
        else:
            self.boto_kwargs = boto_kwargs

        super().__init__(**kwargs)

    @defaults_from_attrs("bucket")
    def run(
        self,
        key: str,
        credentials: str = None,
        bucket: str = None,
        compression: str = None,
    ):
        """
        Task run method.

        Args:
            - key (str): the name of the Key within this bucket to retrieve
            - credentials (dict, optional): your AWS credentials passed from an upstream
                Secret task; this Secret must be a JSON string
                with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY` which will be
                passed directly to `boto3`.  If not provided here or in context, `boto3`
                will fall back on standard AWS rules for authentication.
            - bucket (str, optional): the name of the S3 Bucket to download from
            - compression (str, optional): specifies a file format for decompression, decompressing
                data upon download. Currently supports `'gzip'`.

        Returns:
            - str: the contents of this Key / Bucket, as a string
        """
        if bucket is None:
            raise ValueError("A bucket name must be provided.")

        s3_client = get_boto_client("s3", credentials=credentials, **self.boto_kwargs)

        stream = io.BytesIO()

        # download
        s3_client.download_fileobj(Bucket=bucket, Key=key, Fileobj=stream)

        # prepare data and return
        stream.seek(0)
        output = stream.read()

        # decompress data if decompression is specified
        if compression:
            if compression == "gzip":
                output = gzip.decompress(output)
            else:
                raise ValueError(f"Unrecognized compression method '{compression}'.")

        return output.decode()


class S3Upload(Task):
    """
    Task for uploading string data (e.g., a JSON string) to an S3 bucket.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    For authentication, there are two options: you can set a Prefect Secret containing your AWS
    access keys which will be passed directly to the `boto3` client, or you can [configure your
    flow's runtime
    environment](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#guide-configuration)
    for `boto3`.

    Args:
        - bucket (str, optional): the name of the S3 Bucket to upload to
        - boto_kwargs (dict, optional): additional keyword arguments to forward to the boto client.
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(self, bucket: str = None, boto_kwargs: dict = None, **kwargs):
        self.bucket = bucket

        if boto_kwargs is None:
            self.boto_kwargs = {}
        else:
            self.boto_kwargs = boto_kwargs

        super().__init__(**kwargs)

    @defaults_from_attrs("bucket")
    def run(
        self,
        data: str,
        key: str = None,
        credentials: dict = None,
        bucket: str = None,
        compression: str = None,
    ):
        """
        Task run method.

        Args:
            - data (str): the data payload to upload
            - key (str, optional): the Key to upload the data under; if not
                provided, a random `uuid` will be created
            - credentials (dict, optional): your AWS credentials passed from an upstream
                Secret task; this Secret must be a JSON string
                with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY` which will be
                passed directly to `boto3`.  If not provided here or in context, `boto3`
                will fall back on standard AWS rules for authentication.
            - bucket (str, optional): the name of the S3 Bucket to upload to
            - compression (str, optional): specifies a file format for compression,
                compressing data before upload. Currently supports `'gzip'`.

        Returns:
            - str: the name of the Key the data payload was uploaded to
        """
        if bucket is None:
            raise ValueError("A bucket name must be provided.")

        s3_client = get_boto_client("s3", credentials=credentials, **self.boto_kwargs)

        # compress data if compression is specified
        if compression:
            if compression == "gzip":
                data = gzip.compress(data)
            else:
                raise ValueError(f"Unrecognized compression method '{compression}'.")

        # prepare data
        try:
            stream = io.BytesIO(data)
        except TypeError:
            stream = io.BytesIO(data.encode())

        # create key if not provided
        if key is None:
            key = str(uuid.uuid4())

        # upload
        s3_client.upload_fileobj(stream, Bucket=bucket, Key=key)
        return key


class S3List(Task):
    """
    Task for listing files from an S3 bucket.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    For authentication, there are two options: you can set the `AWS_CREDENTIALS` Prefect Secret
    containing your AWS access keys which will be passed directly to the `boto3` client, or you
    can [configure your flow's runtime
    environment](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#guide-configuration)
    for `boto3`.

    Args:
        - bucket (str, optional): the name of the S3 Bucket to list the files of.
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(self, bucket: str = None, **kwargs):
        self.bucket = bucket
        super().__init__(**kwargs)

    @defaults_from_attrs("bucket")
    def run(
        self,
        prefix: str,
        delimiter: str = "",
        page_size: int = None,
        max_items: int = None,
        credentials: str = None,
        bucket: str = None,
        last_modified_begin: str = None,
        last_modified_end: str = None,
    ):
        """
        Task run method.

        Args:
            - prefix (str): the name of the prefix within this bucket to retrieve objects from
            - delimiter (str): indicates the key hierarchy
            - page_size (int): controls the number of items returned per page of each result
            - max_items (int): limits the maximum number of total items returned during pagination
            - credentials (dict, optional): your AWS credentials passed from an upstream
                Secret task; this Secret must be a JSON string
                with two keys: `ACCESS_KEY` and `SECRET_ACCESS_KEY` which will be
                passed directly to `boto3`.  If not provided here or in context, `boto3`
                will fall back on standard AWS rules for authentication.
            - bucket (str, optional): the name of the S3 Bucket to list the files of
            - last_modified_begin (str, optional): keep items with `LastModified` greater than
                or equal to given value. timestamp should be in `RFC 3339`, `ISO 8601` or any
                pendulum supported [format](https://pendulum.eustace.io/docs/#parsing).
            - last_modified_end (str, optional): keep items with `LastModified` less than
                or equal to given value. timestamp should be in `RFC 3339`, `ISO 8601` or any
                pendulum supported [format](https://pendulum.eustace.io/docs/#parsing).

        Returns:
            - list[str]: A list of keys that match the given prefix.
        """
        if bucket is None:
            raise ValueError("A bucket name must be provided.")

        s3_client = get_boto_client("s3", credentials=credentials)

        config = {"PageSize": page_size, "MaxItems": max_items}
        paginator = s3_client.get_paginator("list_objects_v2")
        results = paginator.paginate(
            Bucket=bucket, Prefix=prefix, Delimiter=delimiter, PaginationConfig=config
        )

        filters = []
        filtered_results = None
        # create the parts of JMESPath query
        if last_modified_end:
            filters.append(
                "(to_string(LastModified) <= '\"{}\"')".format(
                    pendulum.parse(last_modified_end).to_datetime_string()
                )
            )
        if last_modified_begin:
            filters.append(
                "(to_string(LastModified) >= '\"{}\"')".format(
                    pendulum.parse(last_modified_begin).to_datetime_string()
                )
            )

        if filters:
            # combine the parts and create the complete JMESPath query
            filtered_results = results.search(
                '{{"Contents": Contents[? {} ]}}'.format(" && ".join(filters))
            )

        files = []
        for page in filtered_results if filtered_results else results:
            files.extend(obj["Key"] for obj in page.get("Contents", []))

        return files

# `prefect-aws`

<p align="center">
    <a href="https://pypi.python.org/pypi/prefect-aws/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect-aws?color=26272B&labelColor=090422"></a>
    <a href="https://pepy.tech/badge/prefect-aws/" alt="Downloads">
        <img src="https://img.shields.io/pypi/dm/prefect-aws?color=26272B&labelColor=090422" /></a>
</p>

## Welcome

`prefect-aws` makes it easy to leverage the capabilities of AWS in your workflows.

## Getting started

### Installation

Prefect requires Python 3.8 or newer.

We recommend using a Python virtual environment manager such as pipenv, conda, or virtualenv.

Install `prefect-aws`

```bash
pip install prefect-aws
```

### Registering blocks

Register [blocks](https://docs.prefect.io/ui/blocks/) in this module to make them available for use.

```bash
prefect block register -m prefect_aws
```

A list of available blocks in `prefect-aws` and their setup instructions can be found [here](https://PrefectHQ.github.io/prefect-aws/#blocks-catalog).

### Saving credentials to a block

You will need an AWS account and credentials to use `prefect-aws`.

1. Refer to the [AWS Configuration documentation](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html#cli-configure-quickstart-creds) on how to retrieve your access key ID and secret access key
2. Copy the access key ID and secret access key
3. Create an `AWSCredenitals` block in the Prefect UI or use a Python script like the one below and replace the placeholders with your credential information and desired block name:

```python
from prefect_aws import AwsCredentials
AwsCredentials(
    aws_access_key_id="PLACEHOLDER",
    aws_secret_access_key="PLACEHOLDER",
    aws_session_token=None,  # replace this with token if necessary
    region_name="us-east-2"
).save("BLOCK-NAME-PLACEHOLDER")
```

Congrats! You can now load the saved block to use your credentials in your Python code:

```python
from prefect_aws import AwsCredentials
AwsCredentials.load("BLOCK-NAME-PLACEHOLDER")
```

### Using Prefect with AWS S3

`prefect_aws` allows you to read and write objects with AWS S3 within your Prefect flows.

The provided code snippet shows how you can use `prefect_aws` to upload a file to a AWS S3 bucket and download the same file under a different file name.

Note, the following code assumes that the bucket already exists.

```python
from pathlib import Path
from prefect import flow
from prefect_aws import AwsCredentials, S3Bucket

@flow
def s3_flow():
    # create a dummy file to upload
    file_path = Path("test-example.txt")
    file_path.write_text("Hello, Prefect!")

    aws_credentials = AwsCredentials.load("BLOCK-NAME-PLACEHOLDER")
    s3_bucket = S3Bucket(
        bucket_name="BUCKET-NAME-PLACEHOLDER",
        credentials=aws_credentials
    )

    s3_bucket_path = s3_bucket.upload_from_path(file_path)
    downloaded_file_path = s3_bucket.download_object_to_path(
        s3_bucket_path, "downloaded-test-example.txt"
    )
    return downloaded_file_path.read_text()

s3_flow()
```

### Using Prefect with AWS Secrets Manager

`prefect_aws` allows you to read and write secrets with AWS Secrets Manager within your Prefect flows.

The provided code snippet shows how you can use `prefect_aws` to write a secret to the Secret Manager, read the secret data, delete the secret, and finally return the secret data.

```python
from prefect import flow
from prefect_aws import AwsCredentials, AwsSecret

@flow
def secrets_manager_flow():
    aws_credentials = AwsCredentials.load("BLOCK-NAME-PLACEHOLDER")
    aws_secret = AwsSecret(secret_name="test-example", aws_credentials=aws_credentials)
    aws_secret.write_secret(secret_data=b"Hello, Prefect!")
    secret_data = aws_secret.read_secret()
    aws_secret.delete_secret()
    return secret_data

secrets_manager_flow()
```

### Using Prefect with AWS ECS

`prefect_aws` allows you to use [AWS ECS](https://aws.amazon.com/ecs/) as infrastructure for your deployments. Using ECS for scheduled flow runs enables the dynamic provisioning of infrastructure for containers and unlocks greater scalability. This setup gives you all of the observation and orchestration benefits of Prefect, while also providing you the scalability of ECS.

See the [ECS guide](/ecs_guide/) for a full walkthrough.

## Resources

Refer to the API documentation on the sidebar to explore all the capabilities of Prefect AWS!

For more tips on how to use blocks and tasks in Prefect integration libraries, check out the [docs](https://docs.prefect.io/integrations/usage/)!

For more information about how to use Prefect, please refer to the [Prefect documentation](https://docs.prefect.io/).

If you encounter any bugs while using `prefect-aws`, feel free to open an issue in the [`prefect`](https://github.com/PrefectHQ/prefect) repository.

If you have any questions or issues while using `prefect-aws`, you can find help in the [Prefect Slack community](https://prefect.io/slack).
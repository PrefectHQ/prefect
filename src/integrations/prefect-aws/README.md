# `prefect-aws`

<p align="center">
    <a href="https://pypi.python.org/pypi/prefect-aws/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect-aws?color=26272B&labelColor=090422"></a>
    <a href="https://pepy.tech/badge/prefect-aws/" alt="Downloads">
        <img src="https://img.shields.io/pypi/dm/prefect-aws?color=26272B&labelColor=090422" /></a>
</p>

## Welcome

Build production-ready data workflows that seamlessly integrate with AWS services. `prefect-aws` provides battle-tested blocks, tasks, and infrastructure integrations for AWS, featuring support for ECS, S3, Secrets Manager, Lambda, Batch, and Glue.

## Why use prefect-aws?

While you could integrate with AWS services directly using boto3, `prefect-aws` offers significant advantages:

- **Production-ready integrations**: Pre-built, tested components that handle common AWS patterns and edge cases
- **Unified credential management**: Secure, centralized authentication that works consistently across all AWS services
- **Built-in observability**: Automatic logging, monitoring, and state tracking for all AWS operations in your workflows
- **Infrastructure as code**: Deploy and scale your workflows on AWS ECS with minimal configuration
- **Error handling & retries**: Robust error handling with intelligent retry logic for transient AWS service issues
- **Type safety**: Full type hints and validation for all AWS service interactions

## Getting started

### Prerequisites

- An [AWS account](https://aws.amazon.com/account/) and the necessary permissions to access desired services.

### Installation

Install `prefect-aws` as a dependency of Prefect. If you don't already have `prefect` installed, it will install the newest version of `prefect` as well.

```bash
pip install "prefect[aws]"
```

## Blocks setup

### Credentials

Most AWS services require an authenticated session.
Prefect makes it simple to provide credentials via AWS Credentials blocks.

Steps:

1. Refer to the [AWS Configuration documentation](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html#cli-configure-quickstart-creds) to retrieve your access key ID and secret access key.
1. Copy the access key ID and secret access key.
1. Create an `AwsCredentials` block in the Prefect UI or use a Python script like the one below.

```python
from prefect_aws import AwsCredentials


AwsCredentials(
    aws_access_key_id="PLACEHOLDER",
    aws_secret_access_key="PLACEHOLDER",
    aws_session_token=None,  # replace this with token if necessary
    region_name="us-east-2"
).save("BLOCK-NAME-PLACEHOLDER")
```

Prefect uses the Boto3 library under the hood.
To find credentials for authentication, any data not provided to the block are sourced at runtime in the order shown in the [Boto3 docs](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html#configuring-credentials).
Prefect creates the session object using the values in the block and then, any missing values follow the sequence in the Boto3 docs.

### S3

Create a block for reading and writing files to S3.

```python
from prefect_aws import AwsCredentials
from prefect_aws.s3 import S3Bucket

S3Bucket(
    bucket_name="BUCKET-NAME-PLACEHOLDER",
    credentials=aws_credentials
).save("S3-BLOCK-NAME-PLACEHOLDER")
```

### Lambda
Invoke AWS Lambdas, synchronously or asynchronously.

```python
from prefect_aws.lambda_function import LambdaFunction
from prefect_aws.credentials import AwsCredentials

LambdaFunction(
    function_name="test_lambda_function",
    aws_credentials=credentials,
).save("LAMBDA-BLOCK-NAME-PLACEHOLDER")
```

### Secret Manager
Create a block to read, write, and delete AWS Secret Manager secrets.

```python
from prefect_aws import AwsCredentials
from prefect_aws.secrets_manager import AwsSecret

AwsSecret(
    secret_name="test_secret_name",
    aws_credentials=credentials,
).save("AWS-SECRET-BLOCK-NAME-PLACEHOLDER")

```


## Scale workflows with AWS infrastructure

### ECS (Elastic Container Service)

Deploy and scale your Prefect workflows on [AWS ECS](https://aws.amazon.com/ecs/) for production workloads. `prefect-aws` provides:

- **ECS workers**: Long-running workers for hybrid deployments with full control over execution environment
- **Auto-scaling**: Dynamic resource allocation based on workflow demands
- **Cost optimization**: Pay only for compute resources when workflows are running

See the [ECS worker deployment guide](/integrations/prefect-aws/ecs_guide) for a step-by-step walkthrough of deploying production-ready workers to your ECS cluster.

### Docker Images

Pre-built Docker images with `prefect-aws` are available for simplified deployment:

```bash
docker pull prefecthq/prefect-aws:latest
```

#### Available Tags

Image tags have the following format:
- `prefecthq/prefect-aws:latest` - Latest stable release with Python 3.12
- `prefecthq/prefect-aws:latest-python3.11` - Latest stable with Python 3.11
- `prefecthq/prefect-aws:0.5.9-python3.12` - Specific prefect-aws version with Python 3.12
- `prefecthq/prefect-aws:0.5.9-python3.12-prefect3.4.9` - Full version specification

#### Usage Examples

**Running an ECS worker:**
```bash
docker run -d \
  --name prefect-ecs-worker \
  -e PREFECT_API_URL=https://api.prefect.cloud/api/accounts/your-account/workspaces/your-workspace \
  -e PREFECT_API_KEY=your-api-key \
  prefecthq/prefect-aws:latest \
  prefect worker start --pool ecs-pool
```

**Local development:**
```bash
docker run -it --rm \
  -v $(pwd):/opt/prefect \
  prefecthq/prefect-aws:latest \
  python your_flow.py
```

## Supported AWS services

`prefect-aws` provides comprehensive integrations for key AWS services:

| Service | Integration Type | Use Cases |
|---------|-----------------|-----------|
| **S3** | `S3Bucket` block | File storage, data lake operations, deployment storage |
| **Secrets Manager** | `AwsSecret` block | Secure credential storage, API key management |
| **Lambda** | `LambdaFunction` block | Serverless function execution, event-driven processing |
| **Glue** | `GlueJobBlock` block | ETL operations, data transformation pipelines |
| **ECS** | `ECSWorker` infrastructure | Container orchestration, scalable compute workloads |
| **Batch** | `batch_submit` task | High-throughput computing, batch job processing |

**Integration types explained:**
- **Blocks**: Reusable configuration objects that can be saved and shared across flows
- **Tasks**: Functions decorated with `@task` for direct use in flows
- **Workers**: Infrastructure components for running flows on AWS compute services

Each integration includes full support for AWS IAM roles, cross-region operations, and Prefect's built-in retry and error handling mechanisms.

## Examples

### Read and write files to AWS S3

Upload a file to an AWS S3 bucket and download the same file under a different filename.
The following code assumes that the bucket already exists:

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


if __name__ == "__main__":
    s3_flow()
```

### Access secrets with AWS Secrets Manager

Write a secret to AWS Secrets Manager, read the secret data, delete the secret, and return the secret data.

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


if __name__ == "__main__":
    secrets_manager_flow()
```

### Invoke lambdas

```python
from prefect_aws.lambda_function import LambdaFunction
from prefect_aws.credentials import AwsCredentials

credentials = AwsCredentials()
lambda_function = LambdaFunction(
    function_name="test_lambda_function",
    aws_credentials=credentials,
)
response = lambda_function.invoke(
    payload={"foo": "bar"},
    invocation_type="RequestResponse",
)
response["Payload"].read()
```

### Submit AWS Glue jobs

```python
from prefect import flow
from prefect_aws import AwsCredentials
from prefect_aws.glue_job import GlueJobBlock


@flow
def example_run_glue_job():
    aws_credentials = AwsCredentials(
        aws_access_key_id="your_access_key_id",
        aws_secret_access_key="your_secret_access_key"
    )
    glue_job_run = GlueJobBlock(
        job_name="your_glue_job_name",
        arguments={"--YOUR_EXTRA_ARGUMENT": "YOUR_EXTRA_ARGUMENT_VALUE"},
    ).trigger()

    return glue_job_run.wait_for_completion()


if __name__ == "__main__":
    example_run_glue_job()
```

### Submit AWS Batch jobs

```python
from prefect import flow
from prefect_aws import AwsCredentials
from prefect_aws.batch import batch_submit


@flow
def example_batch_submit_flow():
    aws_credentials = AwsCredentials(
        aws_access_key_id="access_key_id",
        aws_secret_access_key="secret_access_key"
    )
    job_id = batch_submit(
        "job_name",
        "job_queue",
        "job_definition",
        aws_credentials
    )
    return job_id


if __name__ == "__main__":
    example_batch_submit_flow()
```

## Resources

### Documentation
- **[prefect-aws SDK Reference](https://reference.prefect.io/prefect_aws/)** - Complete API documentation for all blocks and tasks
- **[ECS Deployment Guide](/integrations/prefect-aws/ecs_guide)** - Step-by-step guide for deploying workflows on ECS
- **[Prefect Secrets Management](/v3/develop/secrets)** - Using AWS credentials with third-party services

### AWS Resources
- **[AWS Documentation](https://docs.aws.amazon.com/)** - Official AWS service documentation
- **[Boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)** - Python SDK reference for AWS services
- **[AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)** - Security recommendations for AWS access

### Community & Support
- **[Prefect Slack Community](https://prefect.io/slack)** - Get help and share experiences
- **[GitHub Issues](https://github.com/PrefectHQ/prefect/issues)** - Report bugs and request features

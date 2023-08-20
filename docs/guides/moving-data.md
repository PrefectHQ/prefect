---
description: Moving data to and from cloud providers
tags:
    - data
    - cloud providers
    - AWS
    - S3
    - Azure Storage
    - Azure Blob Storage
    - Azure
    - GCP
    - Google Cloud Storage
    - GCS
    - moving data
search:
  boost: 2
---

# How to move data to and from cloud providers

Sending data to cloud-based storage and retrieving data from that storage is a common task in data engineering.
In this guide we'll learn how to use Prefect to move data to and from AWS, Azure, and GCP blob storage.

## Prerequisites

- Prefect [installed](/getting-started/installation/)
- Authenticated with [Prefect Cloud](/cloud/cloud-quickstart/) (or self-hosted [Prefect server](/guides/host/) instance)
- A cloud provider account (e.g. [AWS](https://aws.amazon.com/))

## Install relevant Prefect integration library

In the CLI, install the Prefect integration library for your cloud provider:

=== "AWS"

    ```bash
    pip install prefect-aws
    ```

=== "Azure"

    ```bash
     pip install prefect-azure
    ```

=== "GCP"

    ```bash
     pip install prefect-gcp
    ```

## Register the block types

Register the new block types from the installed library with Prefect Cloud (or with your self-hosted Prefect server instance):

=== "AWS"

    ```bash
    prefect block register -m prefect_aws  
    ```

=== "Azure"

    ```bash
    prefect block register -m prefect_azure 
    ```

=== "GCP"

    ```bash
    prefect block register -m prefect_gcp
    ```

You should see a message in the CLI that several block types were registered.

## Create a storage bucket

Create a storage bucket in the cloud provider account.
Ensure the bucket is publicly accessible or that create a user or service account with the appropriate permissions to fetch and write data.

## Create a credentials block

If the bucket is private there are two options to authenticate:

1. Use a worker that is authenticated at deployment run time.
2. Create a block with configuration details and reference it when the storage block is created.

A credentials block specific to the cloud provider or a secret block can be created via the Prefect UI or Python code.

Below we'll use Python code to create a credentials block for the cloud provider.

!!! Warning "Credentials safety"

    Reminder, don't store credential values in public locations such as public git platform repositories.

=== "AWS"

    ```python
    from prefect_aws import AwsCredentials

    my_aws_creds = AwsCredentials(
        aws_access_key_id="123abc",
        aws_secret_access_key="ab123",
    )
    my_aws_creds.save(name="my-aws-creds-block", overwrite=True)
    ```

     Run the code to create the block. We should see a message that the block was created.

=== "Azure"

    Azure blob storage doesn't require a separate credentials block, the connection string can encode the credentials information directly. 
    In the next section we'll see it in action. 

=== "GCP"

    ```python
    from prefect import task
    from prefect_gcp import GCPCredentials

    my_gcp_creds = GCPCredentials(
        service_account_key_path="my-service-account-key-path",
    )
    my_gcp_creds.save(name="my-gcp-creds-block", overwrite=True)
    ```

    Run the code to create the block. We should see a message that the block was created.

## Create a storage block

Let's create a block for cloud provider using Python code or the UI.
In this example we'll use Python code.

=== "AWS"

    Note that the S3Bucket block is not the same as the S3 block that ships with Prefect. 
    The S3Bucket block we use in this example is part of the prefect-aws library and provides additional functionality. 

    We'll reference the credentials block created above.

    ```python
    from prefect_aws import S3Bucket

    s3bucket = S3Bucket.create(
        bucket="my-bucket-name",
        credentials="my-aws-creds-block"
        )
    s3bucket.save(name="my_s3_bucket_block", overwrite=True)
    ```

=== "Azure"

    Note that the AzureBlobStorageCredentials block is not the same as the Azure block that ships with Prefect. 
    The AzureBlobStorageCredentials block we use in this example is part of the prefect-azure library and provides additional functionality. 
    
    ```python
    from prefect_azure import AzureBlobStorageCredentials

    azure_storage = AzureBlobStorageCredentials(
        connection_string="my-connection-string",
    )
    azure_storage.save(name="my-azure-block", overwrite=True)
    ```

=== "GCP"

    Note that the GcsBucket block is not the same as the GCS block that ships with Prefect. 
    The GcsBucket block is part of the prefect-gcp library and provides additional functionality. 
    We'll use it here.

    We'll reference the credentials block created above.

    ```python
    from prefect_gcp.cloud_storage import GcsBucket

    gcsbucket = GcsBucket(
        bucket="my-bucket-name", 
        credentials="my-gcp-creds-block"
        )
    gcsbucket.save()
    ```

Run the code to create the block. We should see a message that the block was created.

## Write data

Use your new block inside a flow to write data to your cloud provider.

=== "AWS"

    ```python
    from pathlib import Path
    from prefect import flow
    from prefect_aws.s3 import S3Bucket

    @flow()
    def upload_to_s3():
        """Flow function to upload data"""
        path = Path("my_path_to/my_file.parquet")
        aws_block = S3Bucket.load("my-aws-bucket")
        aws_block.upload_from_path(from_path=path, to_path=path)

    if __name__ == "__main__":
        upload_to_s3()
    ```

=== "Azure"
    TK - probably switch to prefect-azure way

    ```python
    from prefect import flow
    from prefect.filesystems import Azure

    @flow()
    def upload_to_azure():
        """Flow function to upload data"""
        az_block = Azure.load("azure-demo")
        az_block.put_directory(local_path="my_path_to/my_file.parquet", to_path="my_path_to/my_file.parquet")

    if __name__ == "__main__":
        upload_to_azure()
    ```

=== "GCP"

    ```python
    from pathlib import Path
    from prefect import flow
    from prefect_gcp.cloud_storage import GcsBucket

    @flow()
    def upload_to_gcs():
        """Flow function to upload data"""
        path = Path("my_path_to/my_file.parquet")
        gcs_block = GcsBucket.load("my-gcs-bucket")
        gcs_block.upload_from_path(from_path=path, to_path=path)

    if __name__ == "__main__":
        upload_to_gcs()
    ```

## Read data

Use your block to read data from your cloud provider inside a flow.

=== "AWS"

    ```python

    from prefect import flow
    from prefect_aws import S3Bucket

    s3_block = S3Bucket(name="my-bucket")
    gcs_block.get_directory(from_path="my_path_to/my_file.parquet", local_path="my_path_to/my_file.parquet")
    

    ```

=== "Azure"

    ```python
    from prefect import flow

    TK - probably switch to prefect-azure way
    
    ```

=== "GCP"

    ```python
    from prefect import flow
    from prefect_gcp.cloud_storage import GcsBucket

    gcs_block = GcsBucket.load("zoom-gcs")
    gcs_block.get_directory(from_path="my_path_to/my_file.parquet", local_path="my_path_to/my_file.parquet")
    ```

The storage blocks we used contain additional convenience methods.
Check out the [prefect-aws](https://prefecthq.github.io/prefect-aws/), [prefect-azure](https://prefecthq.github.io/prefect-azure/), or[prefect-gcp](https://prefecthq.github.io/prefect-gcp/) docs and learn about additional blocks for interacting with other cloud services.

We've seen how to use Prefect to read data from and write data to cloud providers!

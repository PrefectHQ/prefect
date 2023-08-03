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

A common task in data engineering is to send data to cloud-based storage and retrieve data from that storage. In this guide you'll learn how to use Prefect to move your data to and from AWS, Azure, and GCP blob storage.

## Prerequisites 
- Prefect [installed](/getting-started/installation/)
- Authenticated with [Prefect Cloud](/cloud/cloud-quickstart/) (or self-hosted [Prefect server](/guides/host/) instance)
- An account for the cloud provider you want to use (e.g. [AWS](https://aws.amazon.com/))

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
Create a storage bucket in your cloud provider account.

=== "AWS"
     You can use the AWS CLI or the AWS UI to create a bucket:

    ```bash 
    TK
    aws s3 mb s3://my-bucket-name
    ```

=== "Azure"
    You can use the Azure CLI or the Azure UI to create a bucket:

    ```bash
    TK
    ```

=== "GCP"
    You can use the GCP CLI or the GCP UI to create a bucket:

    ```bash
    TK
    ```

## Cloud provider credentials
Ensure the bucket is publicly accessible or that you have the appropriate permissions to fetch data from and write data to it. 

=== "AWS"

    When you create the bucket, use a role with the appropriate permissions. The user will need to be able to read from and write to the bucket.

    You can also use the AWS CLI to create a user with the appropriate permissions:

    ```bash
    aws iam create-user --user-name my-user-name
    ```

    ```bash
    aws iam attach-user-policy --user-name my-user-name --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
    ```

    ```bash
    aws iam create-access-key --user-name my-user-name
    ```

    ```bash
    aws configure --profile my-user-name
    ```

    ```bash
    aws s3 mb s3://my-bucket-name
    ```

    ```bash
    aws s3 ls
    ```

    ```bash
    aws s3 cp my-file.txt s3://my-bucket-name
    ```

    ```bash
    aws s3 ls s3://my-bucket-name
    ```

    ```bash
    aws s3 rm s3://my-bucket-name/my-file.txt
    ```

    ```bash
    aws s3 rb s3://my-bucket-name
    ```

    ```
## Create a credentials block 
If you need to be authenticated to read or write ot storage you can use the Prefect UI or code to create a credentials block for your cloud provider. In this example we'll use Python code:

=== "AWS"
    ```python
    from prefect_aws import AWSCredentials

    ```
## Create a storage block
Create a block for your cloud provider using Python code or the UI. In this example we'll use Python code:

=== "AWS"

    ```python
    from prefect_aws import S3Bucket

    s3bucket = S3Bucket.create(
        name="my-bucket",
        credentials=AWSCredentials(name="my-aws-credentials"),
        bucket="my-bucket-name",
    )

    s3bucket.save()
    ```

=== "Azure"

    ```python
    from prefect_azure import AzureBlobStorage


    ```

=== "GCP"

    ```python
    from prefect_gcp import GoogleCloudStorage

    ```

Run the code to create the block. You should see a message in the CLI that the block was created.


## Write data
Use your block inside a flow to write data to your cloud provider.

=== "AWS"

    ```python
    from prefect import task, flow
    from prefect_aws import S3Bucket

    @task
    def extract():
        return [1, 2, 3]

    @task
    def transform(data):
        return [i + 1 for i in data]

    @task
    def load(data):
        print("Here's your data: {}".format(data))

    @flow(log_prints=True)
    def main():
        e = extract()
        t = transform(e)
        l = load(t)

    if __name__ == "__main__":
        main()
    ```


=== "Azure"

    ```python
    from prefect import task, flow
    from prefect_azure import AzureBlobStorage

    ```

=== "GCP"

    ```python

    from prefect import task, flow
    from prefect_gcp import GoogleCloudStorage

    ```

## Read data   
 
Use your block to read data from your cloud provider inside a flow

=== "AWS"

    ```python

    from prefect import task, flow
    from prefect_aws import S3Bucket

    my_bucket = S3Bucket(name="my-bucket")
    my_bucket.load()
    

    ```

=== "Azure"

    ```python
    from prefect import task, flow
    from prefect_azure import AzureBlobStorage
    ```

=== "GCP"

    ```python
    from prefect import task, flow
    from prefect_gcp import GoogleCloudStorage

    ```



You've seen how to use Prefect and cloud providers to read and write data!
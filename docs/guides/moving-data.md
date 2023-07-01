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

A common task in data engineering is to send data to cloud-based storage and retrieve data from that storage. In this guide you'll see how to use Prefect to orchestrate your data with AWS, Azure, and GCP storage.


## Prerequisites (TK add links)
- Prefect installed
- Prefect Cloud account (or self-hosted Prefect server instance)
- An account for the cloud provider you want to use

## Install
Install the Prefect integration library for your cloud provider:

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
Register the new block types from the installed library with Prefect Cloud (You can alternatively use a self-hosted Prefect server instance):

=== "AWS"

    ```bash
    prefect block register -n prefect_aws  
    ```

You should see a message that several block types were registered.

## Create a storage bucket
Create a storage bucket in your cloud provider account.

=== "AWS"
     You can use the AWS CLI or the AWS UI to create a bucket:

    ```bash 
    TK
    aws s3 mb s3://my-bucket-name
    ```

## Credentials
Ensure that the bucket is publicly accessible or that you have the appropriate permissions to fetch data from and write data to it. 

=== "AWS"

When you create the bucket, use a use with the appropriate permissions. The user will need to be ablre to read from and write to the bucket.

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

## Create a credentials block 
You can use the Prefect UI or code to create a credentials block for your cloud provider. In this example we'll use Python code:

=== "AWS"
    ```python
    from prefect_aws import AWSCredentials

    ```

## Create a storage block
Create a block for your cloud provider using Python code or the UI. In this example we'll use Python code:

=== "AWS"

    ```python
    from prefect_aws import S3Bucket


    ```


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
    ```

You've seen how to read and write data to cloud providers with Prefect!
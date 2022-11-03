---
description: Prefect file systems allow persisting or retrieving objects from remote or local data stores.
tags:
    - filesystems
    - storage
    - deployments
    - LocalFileSystem
    - RemoteFileSystem
---

# Filesystems

A filesystem block is an object that allows you to read and write data from paths. Prefect provides multiple built-in file system types that cover a wide range of use cases. 

- [`LocalFileSystem`](#local-file-system)
- [`RemoteFileSystem`](#remote-file-system)
- [`Azure`](#azure)
- [`GitHub`](#github)
- [`GCS`](#gcs)
- [`S3`](#s3)
- [`SMB`](#smb)

Additional file system types are available in [Prefect Collections](/collections/catalog/).

## Local filesystem

The `LocalFileSystem` block enables interaction with the files in your current development environment. 

`LocalFileSystem` properties include:

| Property | Description |
| --- | --- |
| basepath | String path to the location of files on the local filesystem. Access to files outside of the base path will not be allowed. |

```python
from prefect.filesystems import LocalFileSystem

fs = LocalFileSystem(basepath="/foo/bar")
```

!!! warning "Limited access to local file system"
    Be aware that `LocalFileSystem` access is limited to the exact path provided. This file system may not be ideal for some use cases. The execution environment for your workflows may not have the same file system as the enviornment you are writing and deploying your code on. 
    
    Use of this file system can limit the availability of results after a flow run has completed or prevent the code for a flow from being retrieved successfully at the start of a run.

## Remote file system

The `RemoteFileSystem` block enables interaction with arbitrary remote file systems. Under the hood, `RemoteFileSystem` uses [`fsspec`](https://filesystem-spec.readthedocs.io/en/latest/) and supports any file system that `fsspec` supports. 

`RemoteFileSystem` properties include:

| Property | Description |
| --- | --- |
| basepath | String path to the location of files on the remote filesystem. Access to files outside of the base path will not be allowed. |
| settings | Dictionary containing extra [parameters](https://filesystem-spec.readthedocs.io/en/latest/features.html#configuration) required to access the remote file system. |

The file system is specified using a protocol:

- `s3://my-bucket/my-folder/` will use S3
- `gcs://my-bucket/my-folder/` will use GCS
- `az://my-bucket/my-folder/` will use Azure

For example, to use it with Amazon S3:

```python
from prefect.filesystems import RemoteFileSystem

block = RemoteFileSystem(basepath="s3://my-bucket/folder/")
block.save("dev")
```

You may need to install additional libraries to use some remote storage types.

### RemoteFileSystem examples

How can we use `RemoteFileSystem` to store our flow code? The following is a use case where we use [MinIO](https://min.io/) as a storage backend:

```python
from prefect.filesystems import RemoteFileSystem

minio_block = RemoteFileSystem(
    basepath="s3://my-bucket",
    settings={
        "key": "MINIO_ROOT_USER",
        "secret": "MINIO_ROOT_PASSWORD",
        "client_kwargs": {"endpoint_url": "http://localhost:9000"},
    },
)
minio_block.save("minio")
```

## Azure

The `Azure` file system block enables interaction with Azure Datalake and Azure Blob Storage. Under the hood, the `Azure` block uses [`adlfs`](https://github.com/fsspec/adlfs).

`Azure` properties include:

| Property | Description |
| --- | --- |
| bucket_path | String path to the location of files on the remote filesystem. Access to files outside of the bucket path will not be allowed. |
| azure_storage_connection_string | Azure storage connection string. |
| azure_storage_account_name | Azure storage account name. |
| azure_storage_account_key | Azure storage account key. |
| azure_storage_tenant_id | Azure storage tenant ID. |
| azure_storage_client_id | Azure storage client ID. |
| azure_storage_client_secret | Azure storage client secret. |


To create a block:

```python
from prefect.filesystems import Azure

block = Azure(bucket_path="my-bucket/folder/")
block.save("dev")
```

To use it in a deployment:

<div class="terminal">
```bash
prefect deployment build path/to/flow.py:flow_name --name deployment_name --tag dev -sb az/dev
```
</div>

You need to install `adlfs` to use it.

## GitHub

The `GitHub` filesystem block enables interaction with GitHub repositories. This block is read-only and works with both public and private repositories.

`GitHub` properties include:

| Property | Description |
| --- | --- |
| reference | An optional reference to pin to, such as a branch name or tag. |
| repository | The URL of a GitHub repository to read from, in either HTTPS or SSH format. |
| access_token | A GitHub Personal Access Token (PAT) with `repo` scope. |

To create a block:

```python
from prefect.filesystems import GitHub

block = GitHub(
    repository="https://github.com/my-repo/",
    access_token=<my_access_token> # only required for private repos
)
block.get_directory("folder-in-repo") # specify a subfolder of repo
block.save("dev")
```

To use it in a deployment:

<div class="terminal">
```bash
prefect deployment build path/to/flow.py:flow_name --name deployment_name --tag dev -sb github/dev
```
</div>

## GCS

The `GCS` file system block enables interaction with Google Cloud Storage. Under the hood, `GCS` uses [`gcsfs`](https://gcsfs.readthedocs.io/en/latest/).

`GCS` properties include:

| Property | Description |
| --- | --- |
| bucket_path | A GCS bucket path |
| service_account_info | The contents of a service account keyfile as a JSON string.                                                                  |
| project | The project the GCS bucket resides in. If not provided, the project will be inferred from the credentials or environment.    |


To create a block:

```python
from prefect.filesystems import GCS

block = GCS(bucket_path="my-bucket/folder/")
block.save("dev")
```

To use it in a deployment:

<div class="terminal">
```bash
prefect deployment build path/to/flow.py:flow_name --name deployment_name --tag dev -sb gcs/dev
```
</div>

You need to install `gcsfs`to use it.

## S3

The `S3` file system block enables interaction with Amazon S3. Under the hood, `S3` uses [`s3fs`](https://s3fs.readthedocs.io/en/latest/).

`S3` properties include:

| Property | Description |
| --- | --- |
| bucket_path | An S3 bucket path |
| aws_access_key_id | AWS Access Key ID |
| aws_secret_access_key | AWS Secret Access Key |


To create a block:

```python
from prefect.filesystems import S3

block = S3(bucket_path="my-bucket/folder/")
block.save("dev")
```

To use it in a deployment:

<div class="terminal">
```bash
prefect deployment build path/to/flow.py:flow_name --name deployment_name --tag dev -sb s3/dev
```
</div>

You need to install `s3fs`to use this block.

## SMB

The `SMB` file system block enables interaction with SMB shared network storage. Under the hood, `SMB` uses [`smbprotocol`](https://github.com/jborean93/smbprotocol). Used to connect to Windows-based SMB shares from Linux-based Prefect flows. The SMB file system block is able to copy files, but cannot create directories.

`SMB` properties include:

| Property | Description |
| --- | --- |
| basepath | String path to the location of files on the remote filesystem. Access to files outside of the base path will not be allowed. |
| smb_host | Hostname or IP address where SMB network share is located. |
| smb_port | Port for SMB network share (defaults to 445). |
| smb_username | SMB username with read/write permissions. |
| smb_password | SMB password. |


To create a block:

```python
from prefect.filesystems import SMB

block = SMB(basepath="my-share/folder/")
block.save("dev")
```

To use it in a deployment:

<div class="terminal">
```bash
prefect deployment build path/to/flow.py:flow_name --name deployment_name --tag dev -sb smb/dev
```
</div>

You need to install `smbprotocol` to use it.


## Handling credentials for cloud object storage services

If you leverage `S3`, `GCS`, or `Azure` storage blocks, and you don't explicitly configure credentials on the respective storage block, those credentials will be inferred from the environment. Make sure to set those either explicitly on the block or as environment variables, configuration files, or IAM roles within both the build and runtime environment for your deployments.


## Filesystem package dependencies

A Prefect installation and doesn't include filesystem-specific package dependencies such as `s3fs`, `gcsfs` or `adlfs`. This includes Prefect base Docker images.

You must ensure that filesystem-specific libraries are installed in an execution environment where they will be used by flow runs.

In Dockerized deployments, you can leverage the `EXTRA_PIP_PACKAGES` environment variable. Those dependencies will be installed at runtime within your Docker container or Kubernetes Job before the flow starts running. 

Here is an example from a deployment YAML file showing how to specify the installation of `s3fs` from into your image:

```yaml
infrastructure:
  type: docker-container
  env:
    EXTRA_PIP_PACKAGES: s3fs  # could be gcsfs, adlfs, etc.
```

You may specify multiple dependencies by providing a comma-delimted list.

## Saving and loading file systems

Configuration for a file system can be saved to the Prefect API. For example:

```python
fs = RemoteFileSystem(basepath="s3://my-bucket/folder/")
fs.write_path("foo", b"hello")
fs.save("dev-s3")
```

This file system can be retrieved for later use with `load`.

```python
fs = RemoteFileSystem.load("dev-s3")
fs.read_path("foo")  # b'hello'
```

## Readable and writable file systems

Prefect provides two abstract file system types, `ReadableFileSystem` and `WriteableFileSystem`. 

- All readable file systems must implement `read_path`, which takes a file path to read content from and returns bytes. 
- All writeable file systems must implement `write_path` which takes a file path and content and writes the content to the file as bytes. 

A file system may implement both of these types.
<!-- 
## Examples
What does a working example of a MinIO-backed S3 storage block look like within a Prefect flow?

```python
from prefect import flow, task
from prefect.deployments import Deployment
from prefect.filesystems import RemoteFileSystem
from prefect.logging import get_run_logger
from prefect.packaging import FilePackager

@task
def greet_world():
    logger = get_run_logger()
    logger.info("Hello world!")

@flow
def give_greeting() -> str:
    greet_world()
    
minio_packager = FilePackager(
    filesystem=RemoteFileSystem(
        basepath="s3://my-bucket",
        settings={
            "key": MINIO_ROOT_USER,
            "secret": MINIO_ROOT_PASSWORD,
            "client_kwargs": {"endpoint_url": "http://localhost:9000"}
        }
    )
)

Deployment(
    flow=give_greeting,
    name="minio_file_package_with_remote_s3fs",
    packager=minio_packager)

if __name__ == "__main__":
    give_greeting()
```

Starting a MinIO server should output logs including login credentials that can be used as your `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD`. -->

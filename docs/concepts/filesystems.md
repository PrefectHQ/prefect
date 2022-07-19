---
description: Prefect file systems allow persisting or retrieving objects from remote or local data stores.
tags:
    - filesystems
    - storage
    - deployments
    - LocalFileSystem
    - RemoteFileSystem
---

# File systems

A file system is an object which allows you to read and write data from paths. Prefect provides two built-in file system types that cover a wide range of use cases. 

-  [`LocalFileSystem`](#local-file-system)
-  [`RemoteFileSystem`](#remote-file-system)

Additional file system types are available in [Prefect Collections](/collections/overview/).

## Local file system

The `LocalFileSystem` enables interaction with the files in your current development environment. 

`LocalFileSystem` properties include:

| Property | Description |
| --- | --- |
| basepath | String path to the location of files on the local filesystem. Access to files outside of the base path will not be allowed. |

```python
from prefect.filesystems import LocalFileSystem

fs = LocalFileSystem(basepath="/foo/bar")
```

!!! note "Limited access to local file system"
    Be aware that `LocalFileSystem` access is limited to the exact path provided. This file system may not be ideal for some use cases. The execution environment for your workflows may not have the same file system as the enviornment you are writing and deploying your code on. 
    
    Use of this file system can limit the availability of results after a flow run has completed or prevent the code for a flow from being retrieved successfully at the start of a run.

## Remote file system

The `RemoteFileSystem` enables interaction with arbitrary remote file systems. Under the hood, `RemoteFileSystem` uses [`fsspec`](https://filesystem-spec.readthedocs.io/en/latest/) and supports any file system that `fsspec` supports. 

`RemoteFileSystem` properties include:

| Property | Description |
| --- | --- |
| basepath | String path to the location of files on the remote filesystem. Access to files outside of the base path will not be allowed. |
| settings | Dictionary containing extra [parameters](https://filesystem-spec.readthedocs.io/en/latest/features.html#configuration) required to access the remote file system. |

The file system is specified using a protocol. For example, `s3://my-bucket/my-folder/` will use S3.

For example, you can use the remote file system type to connect to S3-compatible storage:

```python
from prefect.filesystems import RemoteFileSystem

RemoteFileSystem(basepath="s3://my-bucket/folder/")
```

You may need to install additional libraries to use some remote storage types.

### RemoteFileSystem examples

How can we use RemoteFileSystem to store our flow code? 
The following is a use case where we use [MinIO](https://min.io/) as a storage backend:

```
minio_file_packager = FilePackager(
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
    packager=minio_file_packager)
```

Now let's look at how we can use RemoteFileSystem with AWS S3:
```
aws_s3_file_packager = FilePackager(filesystem=RemoteFileSystem(
    basepath="s3://my-bucket",
    settings={
        "key": AWS_ACCESS_KEY_ID,
        "secret": AWS_SECRET_ACCESS_KEY
    }
))
Deployment(
    flow=give_greeting,
    name="aws_s3_file_package_with_remote_s3fs",
    packager=aws_s3_file_packager)
```

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

## Examples
What does a working example of a MinIO-backed S3 storage block look like within a Prefect flow?
```
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
Starting a MinIO server should output logs including login credentials that can be used as your MINIO_ROOT_USER and MINIO_ROOT_PASSWORD.
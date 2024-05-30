---
description: Prefect file systems allow persisting or retrieving objects from remote or local data stores.
tags:
    - filesystems
    - storage
    - deployments
    - LocalFileSystem
    - RemoteFileSystem
search:
  boost: .5
---

# Filesystems

A filesystem block is an object that allows you to read and write data from paths. Prefect provides multiple built-in file system types that cover a wide range of use cases. 

- [`LocalFileSystem`](#local-filesystem)
- [`RemoteFileSystem`](#remote-file-system)
- [`Azure`](#azure)
- [`GitHub`](#github)
- [`GitLab`](#gitlab)
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
    Be aware that `LocalFileSystem` access is limited to the exact path provided. This file system may not be ideal for some use cases. The execution environment for your workflows may not have the same file system as the environment you are writing and deploying your code on. 
    
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

You need to install `smbprotocol` to use it.


## Handling credentials for cloud object storage services

If you leverage `S3`, `GCS`, or `Azure` storage blocks, and you don't explicitly configure credentials on the respective storage block, those credentials will be inferred from the environment. Make sure to set those either explicitly on the block or as environment variables, configuration files, or IAM roles within both the build and runtime environment for your deployments.


## Filesystem package dependencies

A Prefect installation and doesn't include filesystem-specific package dependencies such as `s3fs`, `gcsfs` or `adlfs`. This includes Prefect base Docker images.

You must ensure that filesystem-specific libraries are installed in an execution environment where they will be used by flow runs.

In Dockerized deployments using the Prefect base image, you can leverage the `EXTRA_PIP_PACKAGES` environment variable. Those dependencies will be installed at runtime within your Docker container or Kubernetes Job before the flow starts running. 

In Dockerized deployments using a custom image, you must include the filesystem-specific package dependency in your image.

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
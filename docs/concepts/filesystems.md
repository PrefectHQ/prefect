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

A file system is an object which allows you to read and write data from paths. 

Prefect provides two built-in file system types that cover a wide range of use-cases. Additional file system types are available in collections.

<!-- link to collcetions -->

## Local file system

The `LocalFileSystem` type faciliates interaction with the files on your current machine. This file system may not be ideal for some use cases, as the execution environment for your workflows may not have the same file system as the one you are writing and deploying your code on. Use of this file system can limit the availability of results after a flow run has completed or prevent the code for a flow from being retrieved successfully at the start of a run.

<!-- above needs editing -->

The file system may be configured with a `basepath`. Access to files outside of the base path will not be allowed.

## Remote file system

The `RemoteFileSystem` facilitates with interaction with arbitrary remote file systems. Under the hood, it uses `fsspec` and supports any file system that `fsspec` supports. For example, you can use the remote file system type to connect to S3 compatible storage:

<!-- link to fsspec docs -->

```python
RemoteFileSystem(basepath="s3://my-bucket/folder/")
```

You may need to install additional libraries to use some remote storage types.

As with the local file system, read and write operations will not be allowed outside of the base path.



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

Prefect provides two abstract file system types, `ReadableFileSystem` and `WriteableFileSystem`. All readable file systems must implement `read_path` which takes a file path to read content from and returns bytes. All writeable file systems must implement `write_path` which takes a file path and content and writes the content to the file as bytes. A file system may implement both of these types.
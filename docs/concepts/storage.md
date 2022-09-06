---
description: Prefect storage configures local or remote data stores used for flow code, task results, and flow results.
tags:
    - storage
    - databases
    - database configuration
    - configuration
    - settings
    - AWS S3
    - Azure Blob Storage
    - Google Cloud Storage
---

# Storage

Storage lets you configure how flow code for deployments is persisted and retrieved by [Prefect agents](/concepts/work-queues). Anytime you build a deployment, a storage block is used to upload the entire directory containing your workflow code (along with supporting files) to its configured location.  This helps ensure portability of your relative imports, configuration files, and more.  Note that your environment dependencies (for example, external Python packages) still need to be managed separately.

If no storage is explicitly configured, Prefect will use `LocalFileSystem` storage by default. Local storage works fine for many local flow run scenarios, especially when testing and getting started. However, due to the inherent lack of portability, many use cases are better served by using remote storage such as S3 or Google Cloud Storage.

Prefect 2.0 supports creating multiple storage configurations and switching between storage as needed.

!!! tip "Storage uses blocks"
    [Blocks](/concepts/blocks/) is the Prefect technology underlying storage, and enables you to do so much more. 

    In addition to creating storage blocks via the Prefect CLI, you can now create storage blocks and other kinds of block configuration objects via the [Prefect UI and Prefect Cloud](/ui/blocks/).

## Configuring storage for a deployment

When building a deployment for a workflow, you have two options for configuring workflow storage:

- Use the default local storage
- Preconfigure a storage block to use

### Using the default 

Anytime you call `prefect deployment build` without providing the `--storage-block` flag, a default `LocalFileSystem` block will be used.  Note that this block will always use your present working directory as its basepath (which is usually desirable).  You can see the block's settings by inspecting the `deployment.yaml` file that Prefect creates after calling `prefect deployment build`.

While you generally can't run a deployment stored on a local file system on other machines, any agent running on the same machine will be able to successfully run your deployment.

### Configuring a block

Current options for deployment storage blocks include:

| Storage | Description |
| --- | --- |
| [Local File System](/api-ref/prefect/filesystems/#prefect.filesystems.LocalFileSystem) | Store data in a run's local file system. |
| [Remote File System](/api-ref/prefect/filesystems/#prefect.filesystems.RemoteFileSystem) | Store data in a any filesystem supported by [`fsspec`](https://filesystem-spec.readthedocs.io/en/latest/). |
| [AWS S3 Storage](/api-ref/prefect/filesystems/#prefect.filesystems.S3) | Store data in an AWS S3 bucket. |
| [Google Cloud Storage](/api-ref/prefect/filesystems/#prefect.filesystems.GCS) | Store data in a Google Cloud Platform (GCP) Cloud Storage bucket. |
| [Azure Storage](/api-ref/prefect/filesystems/#prefect.filesystems.Azure) | Store data in Azure Datalake and Azure Blob Storage. |
| [GitHub Storage](/api-ref/prefect/filesystems/#prefect.filesystems.GitHub) | Store data in a GitHub repository. |

You can create these blocks either via the UI or via Python; for example:

```python
from prefect.filesystems import S3

block = S3(bucket_path="my-bucket/a-sub-directory", aws_access_key_id="foo", aws_secret_access_key="bar")
block.save("example-block")
```

This block configuration is now available to be used by anyone with appropriate access to your Prefect API.  We can use this block to build a deployment by passing its slug to the `prefect deployment build` command as follows:

```
prefect deployment build ./flows/my_flow.py:my_flow --name "Example Deployment" --storage-block s3/example-block
```

This command will first create a flow manifest file, and then proceed to upload the contents of your flow's directory to the designated storage location. Once complete, the full deployment specification will be persisted to a newly created `deployment.yaml` file.  For more information, see [Deployments](/concepts/deployments).

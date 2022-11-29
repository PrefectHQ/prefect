---
description: Prefect storage configures local or remote data stores used for flow scripts, deployments, and flow runs.
tags:
    - storage
    - databases
    - database configuration
    - configuration
    - settings
    - AWS S3
    - Azure Blob Storage
    - Google Cloud Storage
    - SMB
---

# Storage

Storage lets you configure how flow code for deployments is persisted and retrieved by [Prefect agents](/concepts/work-queues). Anytime you build a deployment, a storage block is used to upload the entire directory containing your workflow code (along with supporting files) to its configured location.  This helps ensure portability of your relative imports, configuration files, and more.  Note that your environment dependencies (for example, external Python packages) still need to be managed separately.

If no storage is explicitly configured, Prefect will use `LocalFileSystem` storage by default. Local storage works fine for many local flow run scenarios, especially when testing and getting started. However, due to the inherent lack of portability, many use cases are better served by using remote storage such as S3 or Google Cloud Storage.

Prefect 2 supports creating multiple storage configurations and switching between storage as needed.

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

### Supported storage blocks

Current options for deployment storage blocks include:

| Storage | Description | Required Library | 
| --- | --- | --- |
| [Local File System](/api-ref/prefect/filesystems/#prefect.filesystems.LocalFileSystem) | Store code in a run's local file system. | |
| [Remote File System](/api-ref/prefect/filesystems/#prefect.filesystems.RemoteFileSystem) | Store code in a any filesystem supported by [`fsspec`](https://filesystem-spec.readthedocs.io/en/latest/). | |
| [AWS S3 Storage](/api-ref/prefect/filesystems/#prefect.filesystems.S3) | Store code in an AWS S3 bucket. | [`s3fs`](https://s3fs.readthedocs.io/en/latest/) |
| [Azure Storage](/api-ref/prefect/filesystems/#prefect.filesystems.Azure) | Store code in Azure Datalake and Azure Blob Storage. | [`adlfs`](https://github.com/fsspec/adlfs) |
| [GitHub Storage](/api-ref/prefect/filesystems/#prefect.filesystems.GitHub) | Store code in a GitHub repository. | |
| [Google Cloud Storage](/api-ref/prefect/filesystems/#prefect.filesystems.GCS) | Store code in a Google Cloud Platform (GCP) Cloud Storage bucket. | [`gcsfs`](https://gcsfs.readthedocs.io/en/latest/) |
| [SMB](/api-ref/prefect/filesystems/#prefect.filesystems.SMB) | Store code in SMB shared network storage. | [`smbprotocol`](https://github.com/jborean93/smbprotocol) |
| [GitLab Repository](https://github.com/PrefectHQ/prefect-gitlab) | Store code in a GitLab repository. | [`prefect-gitlab`](https://github.com/PrefectHQ/prefect-gitlab) |

!!! note "Accessing files may require storage filesystem libraries"
    Note that the appropriate filesystem library supporting the storage location must be installed prior to building a deployment with a storage block or accessing the storage location from flow scripts. 
    
    For example, the AWS S3 Storage block requires the [`s3fs`](https://s3fs.readthedocs.io/en/latest/) library.

    See [Filesystem package dependencies](/concepts/filesystems/#filesystem-package-dependencies) for more information about configuring filesystem libraries in your execution environment.

### Configuring a block

You can create these blocks either via the UI or via Python. 

You can [create, edit, and manage storage blocks](/ui/blocks/) in the Prefect UI and Prefect Cloud. On a Prefect Orion server, blocks are created in the server's database. On Prefect Cloud, blocks are created on a workspace.

To create a new block, select the **+** button. Prefect displays a library of block types you can configure to create blocks to be used by your flows.

![Viewing the new block library in the Prefect UI](/img/ui/orion-block-library.png)

Select **Add +** to configure a new storage block based on a specific block type. Prefect displays a **Create** page that enables specifying storage settings.

![Configurating an S3 storage block in the Prefect UI](/img/tutorials/s3-block-configuration.png)

You can also create blocks using the Prefect Python API:

```python
from prefect.filesystems import S3

block = S3(bucket_path="my-bucket/a-sub-directory", 
           aws_access_key_id="foo", 
           aws_secret_access_key="bar"
)
block.save("example-block")
```

This block configuration is now available to be used by anyone with appropriate access to your Prefect API.  We can use this block to build a deployment by passing its slug to the `prefect deployment build` command. The storage block slug is formatted as `block-type/block-name`. In this case, `s3/example-block` for an AWS S3 Bucket block named `example-block`. See [block identifiers](/concepts/deployments/#block-identifiers) for details.

<div class="terminal">
```bash
prefect deployment build ./flows/my_flow.py:my_flow --name "Example Deployment" --storage-block s3/example-block
```
</div>

This command will upload the contents of your flow's directory to the designated storage location, then the full deployment specification will be persisted to a newly created `deployment.yaml` file.  For more information, see [Deployments](/concepts/deployments).

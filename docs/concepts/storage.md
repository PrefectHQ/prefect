---
description: Prefect storage configures local or remote data stores used for flow code, task results, and flow results.
tags:
    - storage
    - databases
    - database configuration
    - configuration
    - settings
    - S3
    - Azure Blob Storage
    - Google Cloud Storage
---

# Storage

Storage lets you configure how flow code for deployments, task results, and flow results are persisted.

If no other storage is configured, Prefect uses the default [Temporary Local Storage](#temporary-local-storage).

Local storage works fine for many local flow and task run scenarios. However, to run flows using Docker or Kubernetes, you must set up remote storage such as S3, Google Cloud Storage, or Azure Blob Storage. You can also configure a self-hosted key-value store for testing.

Prefect 2.0 supports creating multiple storage configurations and switching between storage as needed.

## Configuring storage

To create a storage configuration, use the `prefect storage create` CLI command. You'll be able to select from available storage types. When necessary, you must provide storage location and authentication details.

Current storage types include:

| Storage | Description |
| --- | --- |
| [Azure Blob Storage](#azure-blob-storage) | Store data in an Azure Blob Storage container. |
| [File Storage](#file-storage) | Store data as a file on local or remote file systems. |
| [Google Cloud Storage](#google-cloud-storage) | Store data in a Google Cloud Platform (GCP) Cloud Storage bucket. |
| [KV Server Storage](#key-value-storage) | Store data by sending requests to a KV server. |
| [Local Storage](#local-storage) | Store data in a run's local file system. |
| [S3 Storage](#aws-s3-storage) | Store data in an AWS S3 bucket. |
| [Temporary Local Storage](#temporary-local-storage) | Store data in a temporary directory in a run's local file system. (Default) |

Select a storage type and follow the prompts to complete configuration. You should have details of your storage on hand to complete configuration.

<div class='termy'>
```bash
$ prefect storage create
Found the following storage types:
0) Azure Blob Storage
    Store data in an Azure blob storage container.
1) File Storage
    Store data as a file on local or remote file systems.
2) Google Cloud Storage
    Store data in a GCS bucket.
3) KV Server Storage
    Store data by sending requests to a KV server.
4) Local Storage
    Store data in a run's local file system.
5) S3 Storage
    Store data in an AWS S3 bucket.
6) Temporary Local Storage
    Store data in a temporary directory in a run's local file system.
Select a storage type to create:
```
</div>

### Setting storage

You can configure the default storage configuration by using the `prefect storage set-default` CLI command, passing the ID of the storage you want to use.

<div class='termy'>
```
$ prefect storage set-default 61354abf-7cc8-4c2c-b890-78b1f985a9fb
Updated default storage!
```
</div>

To see the IDs of available storage configurations, use the `prefect storage ls` command.

![Listing configured storage.](/img/concepts/storage-ls.png)

`prefect storage reset-default` resets the default storage option to Temporary Local Storage.

## Storage parameters

The following sections list the configuration information needed to create storage.

### AWS S3 Storage

You can use the following options to configure Amazon Simple Storage Service (AWS S3) storage for persisting Prefect flow run and result data.

| Setting | Description |
| --- | --- |
| Bucket | Name of the S3 bucket. |
| AWS Access Key ID | IAM access key ID for the account. (optional) |
| AWS Secret Access Key | IAM secret access key for the account. (optional) |
| AWS Session Token | Session token to authenticate with temporary security credentials. (optional) |
| Profile Name | Instance profile name for an IAM role. (optional) |
| Region Name | Name of the bucket's AWS region. (optional) |
| Name | Name that Prefect uses to identify this storage configuration. |

### Azure Blob Storage

You can use the following options to configure an Azure Blob Storage container for persisting Prefect flow run and result data.

| Setting | Description |
| --- | --- |
| Container | Name of the Azure Blob Storage container. |
| Connection String | Connection string for a valid key to authenticate with the Storage account. |
| Name | Name that Prefect uses to identify this storage configuration. |

### File Storage

You can use the following options to configure File Storage for persisting Prefect flow run and result data as a file on a local or remote file system.

| Setting | Description |
| --- | --- |
| Key Type | The method to use to generate file names. Defaults to "hash". (optional) |
| Base Path | Path to the storage location or folder. |
| Name | Name that Prefect uses to identify this storage configuration. |

Base Path supports any file system supported by `fsspec`. The file system is specified using a protocol. For example, "s3://my-bucket/my-folder/" will use S3. Credentials for external services will be retrieved.

Each blob is stored in a separate file. The Key Type defaults to "hash" to avoid storing duplicates. If you always want to store a new file, you can use "uuid" or "timestamp".

### Google Cloud Storage

You can use the following options to configure an GCP Cloud Storage container for persisting Prefect flow run and result data.

| Setting | Description |
| --- | --- |
| Bucket | Name of the Cloud Storage bucket. |
| Project | Name of the Google Cloud project associated with the bucket. (optional) |
| Service Account Info | Service account credentials JSON. (optional) |
| Name | Name that Prefect uses to identify this storage configuration. |

### Key-Value Storage

You can use the following options to configure a self-hosted key-value store for persisting Prefect flow run and result data. We recommend using KV storage for testing only.

| Setting | Description |
| --- | --- |
| API Address | API endpoint for the KV store. |
| Name | Name that Prefect uses to identify this storage configuration. |

### Local Storage

You can use the following options to configure Local Storage for persisting Prefect flow run and result data in the local file system.

| Setting | Description |
| --- | --- |
| Storage Path | Path to the storage folder. |
| Name | Name that Prefect uses to identify this storage configuration. |

### Temporary Local Storage

Temporary Local Storage persists Prefect flow run and result data in the local file system, using `~/.prefect/flows` and `~/.prefect/results` by default.

Temporary Local Storage works best for local development and testing. If you're using Docker or Kubernetes, you must configure remote storage such as AWS S3, Azure Blob Storage, Google Cloud Storage, or File Storage configured to use a shared file system.
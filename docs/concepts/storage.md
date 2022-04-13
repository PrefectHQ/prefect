---
description: Prefect storage configures local or remote data stores used for flow code, task results, and flow results.
tags:
    - Orion
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

Storage lets you configure how flow code, task results, and flow results data are persisted.

If no other storage is configured, Prefect uses the default Temporary Local Storage.

Local storage works fine for many local flow and task run scenarios. However, to run flows using Docker or Kubernetes, you must set up remote storage such as S3, Google Cloud Storage, or Azure Blob Storage. You can also configure a self-hosted key-value store for testing.

Prefect 2.0 supports creating multiple storage configurations and switching between storage as needed.

## Configure storage

To create a storage configuration, use the `prefect storage create` CLI command. You'll be able to select from available storage types. When necessary, you can provide storage location and authentication details.

Current storage types include:

| Storage | Description |
| --- | --- |
| Azure Blob Storage | Store data in an Azure blob storage container. |
| Google Cloud Storage | Store data in a GCS bucket. |
| KV Server Storage | Store data by sending requests to a KV server. |
| Local Storage | Store data in a run's local file system. |
| S3 Storage | Store data in an AWS S3 bucket. |
| Temporary Local Storage | Store data in a temporary directory in a run's local file system. (Default) |

Select a storage type and follow the prompts to complete configuration. You should have details of your storage on hand to complete configuration.

<div class='termy'>
```
$ prefect storage create
Found the following storage types:
0) Azure Blob Storage
    Store data in an Azure blob storage container
1) Google Cloud Storage
    Store data in a GCS bucket
2) KV Server Storage
    Store data by sending requests to a KV server
3) Local Storage
    Store data in a run's local file system
4) S3 Storage
    Store data in an AWS S3 bucket
5) Temporary Local Storage
    Store data in a temporary directory in a run's local file system
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

`prefect storage reset-default` resets the default storage option to temporary local storage.
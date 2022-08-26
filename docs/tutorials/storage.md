---
description: Learn how to configure storage and infrastructure blocks used by Prefect flow deployments.
tags:
    - Orion
    - orchestration
    - deployments
    - storage
    - filesystems
    - infrastructure
    - blocks
---

# Storage and Infrastructure

In previous tutorials, we've run flow and tasks entirely in a local execution environment using the local file system to store flow scripts. 

For production workflows, you'll most likely want to configure deployments that create flow runs in remote execution environments &mdash; a VM, a Docker container, or a Kubernetes cluster, for example. These deployments require _remote storage_ and _infrastructure_ blocks that specify where your flow code is stored and how the flow run execution environment should be configured.

Let's unpack these terms.

In Prefect, [blocks](/concepts/blocks/) are a primitive that enable you to specify configuration for interacting with external systems.

[Storage](/concepts/storage/) blocks contain configuration for interacting with file storage such as a remote filesystem, AWS S3, and so on.

[Infrastructure](/concepts/infrastructure/) blocks contain settings that [agents](/concepts/work-queues/) use to stand up execution infrastructure for a flow run.

## Prerequisites

The steps demonstrated in this tutorial assume you have access to a storage location in a cloud service such as AWS or Azure.

To create a storage block, you will need the storage location (for example, a bucket or container name) and valid authentication details such as access keys or connection strings.

## Storage

As mentioned previously, storage blocks contain configuration for interacting with file storage. This includes:

- Local storage
- Remote storage on a filesystem supported by [`fsspec`](https://filesystem-spec.readthedocs.io/en/latest/)
- AWS S3 buckets
- Azure Blob storage 
- SMB shares

Storage blocks are used, when you create a deployment, to save flow artifacts (such as your flow scripts) to a location where they can be retrieved for future flow run execution. 

Your flow code may also load storage blocks to access configuration for accessing storage, such as for reading or saving files.


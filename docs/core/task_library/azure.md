---
title: Azure
---

# Microsoft Azure

A collection of tasks for interacting with Azure resources.

Note that all tasks require a Prefect Secret called `"AZ_CREDENTIALS"` that should be a JSON
document with two keys: `"ACCOUNT_NAME"` and `"ACCOUNT_KEY"`.

## BlobStorageDownload <Badge text="task"/>

Task for downloading data from an Blob Storage container and returning it as a string. Note that all initialization arguments can optionally be provided or overwritten at runtime.

[API Reference](/api/unreleased/tasks/azure.html#prefect-tasks-azure-blobstorage-blobstoragedownload)

## BlobStorageUpload <Badge text="task"/>

Task for uploading string data (e.g., a JSON string) to an Blob Storage. Note that all initialization arguments can optionally be provided or overwritten at runtime.

[API Reference](/api/unreleased/tasks/azure.html#prefect-tasks-azure-blobstorage-blobstorageupload)

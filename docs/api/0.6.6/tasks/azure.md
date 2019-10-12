---
sidebarDepth: 2
editLink: false
---
# Azure Tasks
---
This module contains a collection of tasks for interacting with Azure resources.

Note that all tasks require a Prefect Secret called `"AZ_CREDENTIALS"` that should be a JSON
document with two keys: `"ACCOUNT_NAME"` and `"ACCOUNT_KEY"`.
 ## BlobStorageDownload
 <div class='class-sig' id='prefect-tasks-azure-blobstorage-blobstoragedownload'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.azure.blobstorage.BlobStorageDownload</p>(azure_credentials_secret="AZ_CREDENTIALS", container=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/azure/blobstorage.py#L9">[source]</a></span></div>

Task for downloading data from an Blob Storage container and returning it as a string. Note that all initialization arguments can optionally be provided or overwritten at runtime.

**Args**:     <ul class="args"><li class="args">`azure_credentials_secret (str, optional)`: the name of the Prefect Secret         that stores your Azure credentials; this Secret must be a JSON string         with two keys: `ACCOUNT_NAME` and `ACCOUNT_KEY`     </li><li class="args">`container (str, optional)`: the name of the Azure Blob Storage to download from     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the         Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-azure-blobstorage-blobstoragedownload-run'><p class="prefect-class">prefect.tasks.azure.blobstorage.BlobStorageDownload.run</p>(blob_name, azure_credentials_secret="AZ_CREDENTIALS", container=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/azure/blobstorage.py#L33">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:     <ul class="args"><li class="args">`blob_name (str)`: the name of the blob within this container to retrieve     </li><li class="args">`azure_credentials_secret (str, optional)`: the name of the Prefect Secret         that stores your Azure credentials; this Secret must be a JSON string         with two keys: `ACCOUNT_NAME` and `ACCOUNT_KEY`     </li><li class="args">`container (str, optional)`: the name of the Blob Storage container to download from</li></ul>**Returns**:     <ul class="args"><li class="args">`str`: the contents of this blob_name / container, as a string</li></ul></p>|

---
<br>

 ## BlobStorageUpload
 <div class='class-sig' id='prefect-tasks-azure-blobstorage-blobstorageupload'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.azure.blobstorage.BlobStorageUpload</p>(azure_credentials_secret="AZ_CREDENTIALS", container=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/azure/blobstorage.py#L74">[source]</a></span></div>

Task for uploading string data (e.g., a JSON string) to an Azure Blob Storage container. Note that all initialization arguments can optionally be provided or overwritten at runtime.

**Args**:     <ul class="args"><li class="args">`azure_credentials_secret (str, optional)`: the name of the Prefect Secret         that stores your Azure credentials; this Secret must be a JSON string         with two keys: `ACCOUNT_NAME` and `ACCOUNT_KEY`     </li><li class="args">`container (str, optional)`: the name of the Azure Blob Storage to upload to     </li><li class="args">`**kwargs (dict, optional)`: additional keyword arguments to pass to the         Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-azure-blobstorage-blobstorageupload-run'><p class="prefect-class">prefect.tasks.azure.blobstorage.BlobStorageUpload.run</p>(data, blob_name=None, azure_credentials_secret="AZ_CREDENTIALS", container=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/azure/blobstorage.py#L98">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:     <ul class="args"><li class="args">`data (str)`: the data payload to upload     </li><li class="args">`blob_name (str, optional)`: the name to upload the data under; if not             provided, a random `uuid` will be created     </li><li class="args">`azure_credentials_secret (str, optional)`: the name of the Prefect Secret         that stores your Azure credentials; this Secret must be a JSON string         with two keys: `ACCOUNT_NAME` and `ACCOUNT_KEY`     </li><li class="args">`container (str, optional)`: the name of the Blob Storage container to upload to</li></ul>**Returns**:     <ul class="args"><li class="args">`str`: the name of the blob the data payload was uploaded to</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on October 4, 2019 at 12:32 UTC</p>
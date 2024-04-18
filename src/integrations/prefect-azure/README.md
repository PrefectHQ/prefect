# prefect-azure

<p align="center">
    <a href="https://pypi.python.org/pypi/prefect-azure/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect-azure?color=26272B&labelColor=090422"></a>
    <a href="https://pepy.tech/badge/prefect-azure/" alt="Downloads">
        <img src="https://img.shields.io/pypi/dm/prefect-azure?color=26272B&labelColor=090422" /></a>
</p>

`prefect-azure` is a collection of Prefect integrations for orchestration workflows with Azure.

## Getting Started

### Installation

Install `prefect-azure` with `pip`

```bash
pip install prefect-azure
```

To use Blob Storage:
```bash
pip install "prefect-azure[blob_storage]"
```

To use Cosmos DB:
```bash
pip install "prefect-azure[cosmos_db]"
```

To use ML Datastore:
```bash
pip install "prefect-azure[ml_datastore]"
```

## Examples

### Download a blob

```python
from prefect import flow

from prefect_azure import AzureBlobStorageCredentials
from prefect_azure.blob_storage import blob_storage_download

@flow
def example_blob_storage_download_flow():
    connection_string = "connection_string"
    blob_storage_credentials = AzureBlobStorageCredentials(
        connection_string=connection_string,
    )
    data = blob_storage_download(
        blob="prefect.txt",
        container="prefect",
        azure_credentials=blob_storage_credentials,
    )
    return data

example_blob_storage_download_flow()
```

Use `with_options` to customize options on any existing task or flow:
```python
custom_blob_storage_download_flow = example_blob_storage_download_flow.with_options(
    name="My custom task name",
    retries=2,
    retry_delay_seconds=10,
)
```

### Run a command on an Azure container instance

```python
from prefect import flow
from prefect_azure import AzureContainerInstanceCredentials
from prefect_azure.container_instance import AzureContainerInstanceJob


@flow
def container_instance_job_flow():
    aci_credentials = AzureContainerInstanceCredentials.load("MY_BLOCK_NAME")
    container_instance_job = AzureContainerInstanceJob(
        aci_credentials=aci_credentials,
        resource_group_name="azure_resource_group.example.name",
        subscription_id="<MY_AZURE_SUBSCRIPTION_ID>",
        command=["echo", "hello world"],
    )
    return container_instance_job.run()
```

### Use Azure Container Instance as infrastructure

If we have `a_flow_module.py`:

```python
from prefect import flow, get_run_logger

@flow
def log_hello_flow(name="Marvin"):
    logger = get_run_logger()
    logger.info(f"{name} said hello!")

if __name__ == "__main__":
    log_hello_flow()
```

We can run that flow using an Azure Container Instance, but first create the infrastructure block:

```python
from prefect_azure import AzureContainerInstanceCredentials
from prefect_azure.container_instance import AzureContainerInstanceJob

container_instance_job = AzureContainerInstanceJob(
    aci_credentials=AzureContainerInstanceCredentials.load("MY_BLOCK_NAME"),
    resource_group_name="azure_resource_group.example.name",
    subscription_id="<MY_AZURE_SUBSCRIPTION_ID>",
)
container_instance_job.save("aci-dev")
```

Then, create the deployment either on the UI or through the CLI:
```bash
prefect deployment build a_flow_module.py:log_hello_flow --name aci-dev -ib container-instance-job/aci-dev
```

Visit [Prefect Deployments](https://docs.prefect.io/tutorials/deployments/) for more information about deployments.

## Azure Container Instance Worker
The Azure Container Instance worker is an excellent way to run 
your workflows on Azure. 

To get started, create an Azure Container Instances typed work pool:
```
prefect work-pool create -t azure-container-instance my-aci-work-pool
```

Then, run a worker that pulls jobs from the work pool:
```
prefect worker start -n my-aci-worker -p my-aci-work-pool
```

The worker should automatically read the work pool's type and start an 
Azure Container Instance worker.

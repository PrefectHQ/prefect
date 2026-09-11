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

## Managed identity authentication for the Prefect server database

`prefect-azure` provides a Prefect plugin that lets the **Prefect server** connect
to Azure Database for PostgreSQL using a Microsoft Entra ID (managed identity)
token instead of a password. When enabled, the server acquires a short-lived Entra
token via `DefaultAzureCredential` and supplies it to `asyncpg` on every new
connection, so tokens refresh automatically and no database password is stored
anywhere.

Enable it on the process running `prefect server start` (install `prefect-azure`
in that image/environment):

```bash
# Enable the plugin system so Prefect loads the database hook
# (on Prefect < 3.7 use PREFECT_EXPERIMENTS_PLUGINS_ENABLED=true instead)
export PREFECT_PLUGINS_ENABLED=true

export PREFECT_INTEGRATIONS_AZURE_POSTGRES_MANAGED_IDENTITY_ENABLED=true
# Optional: select a specific user-assigned identity
export PREFECT_INTEGRATIONS_AZURE_POSTGRES_MANAGED_IDENTITY_CLIENT_ID=<client-id>

# Provide a password-less connection URL (the plugin supplies the token)
export PREFECT_SERVER_DATABASE_CONNECTION_URL="postgresql+asyncpg://<entra-principal>@<host>:5432/<db>"
```

The Postgres server must have Microsoft Entra authentication enabled and the
identity mapped to a database role (via `pgaadauth`). Locally, `DefaultAzureCredential`
falls back to your `az login` identity, so the same configuration works for
development.

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

## Azure Container Instance Worker

Use the Azure Container Instance worker to run flow runs in Azure Container
Instances.

To get started, create an Azure Container Instances typed work pool:

```bash
prefect work-pool create --type azure-container-instance my-aci-work-pool
```

Then, run a worker that pulls jobs from the work pool:

```bash
prefect worker start --pool my-aci-work-pool --type azure-container-instance
```

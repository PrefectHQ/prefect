# prefect-openlineage

<p align="center">
    <!--- Insert a cover image here -->
    <!--- <br> -->
    <a href="https://pypi.python.org/pypi/prefect-openlineage/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect-openlineage?color=26272B&labelColor=090422"></a>
    <a href="https://pepy.tech/badge/prefect-openlineage/" alt="Downloads">
        <img src="https://img.shields.io/pypi/dm/prefect-openlineage?color=26272B&labelColor=090422" /></a>
</p>

## Basic Configuration

At a minimum, define a namespace, Prefect API URL and transport consisting of a type, URL and endpoint. All three can be supplied using environment variables.

For example:

```sh
export OPENLINEAGE_NAMESPACE='prefect_test' &&
export OPENLINEAGE__TRANSPORT__TYPE='http' &&
export OPENLINEAGE__TRANSPORT__URL='http://lineageconsumer.com:5000' &&
export OPENLINEAGE__TRANSPORT__ENDPOINT='/api/v1/lineage' &&
export PREFECT_API_URL='http://prefecthost.com:4200/api'
```

For more details about OpenLineage transport options and how to configure them, consult the [OpenLineage Python Client Documentation](https://openlineage.io/docs/client/python/).

## Execution

Import the `prefect_openlineage` package and execute `collect_and_process_runs()` in its own process.

For example:

```py
import prefect_openlineage
from prefect_openlineage.listener import PrefectOpenlineageListener

async def main():
    await PrefectOpenLineageListener().collect_and_process_runs()

if __name__ == "__main__":
    asyncio.run(main())
```

## Datasets

The integration looks for datasets in Prefect Artifacts. To attach input and output datasets to job runs, use `create_table_artifact()` from the Artifact library. Provide a namespace, typically the dataset URI, and name to the adapter via an artifact's `table` and `description`, respectively. Distinguish the type of dataset by appending `_output` or `_input` to the description.

For example:

```py
ol_table = [{"database_uri":"duckdb:///customers_db", "table":"customers"}]

create_table_artifact(
    key="upstream-insert",
    table=ol_table,
    description="ol-dataset_output"
)
```

Consult the [Prefect OpenLineage documentation](https://docs.prefect.io/integrations/prefect-openlineage) for more information.

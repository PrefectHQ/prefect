"""Tasks for interacting with Azure Cosmos DB"""

from functools import partial
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from anyio import to_thread

if TYPE_CHECKING:
    from azure.cosmos.database import ContainerProxy, DatabaseProxy

from prefect import task
from prefect.logging import get_run_logger
from prefect_azure.credentials import AzureCosmosDbCredentials


@task
async def cosmos_db_query_items(
    query: str,
    container: Union[str, "ContainerProxy", Dict[str, Any]],
    database: Union[str, "DatabaseProxy", Dict[str, Any]],
    cosmos_db_credentials: AzureCosmosDbCredentials,
    parameters: Optional[List[Dict[str, object]]] = None,
    partition_key: Optional[Any] = None,
    **kwargs: Any,
) -> List[Union[str, dict]]:
    """
    Return all results matching the given query.

    You can use any value for the container name in the FROM clause,
    but often the container name is used.
    In the examples below, the container name is "products,"
    and is aliased as "p" for easier referencing in the WHERE clause.

    Args:
        query: The Azure Cosmos DB SQL query to execute.
        container: The ID (name) of the container, a ContainerProxy instance,
            or a dict representing the properties of the container to be retrieved.
        database: The ID (name), dict representing the properties
            or DatabaseProxy instance of the database to read.
        cosmos_db_credentials: Credentials to use for authentication with Azure.
        parameters: Optional array of parameters to the query.
            Each parameter is a dict() with 'name' and 'value' keys.
        partition_key: Partition key for the item to retrieve.
        **kwargs: Additional keyword arguments to pass.

    Returns:
        An `list` of results.

    Example:
        Query SampleDB Persons container where age >= 44
        ```python
        from prefect import flow

        from prefect_azure import AzureCosmosDbCredentials
        from prefect_azure.cosmos_db import cosmos_db_query_items

        @flow
        def example_cosmos_db_query_items_flow():
            connection_string = "connection_string"
            cosmos_db_credentials = AzureCosmosDbCredentials(connection_string)

            query = "SELECT * FROM c where c.age >= @age"
            container = "Persons"
            database = "SampleDB"
            parameters = [dict(name="@age", value=44)]

            results = cosmos_db_query_items(
                query,
                container,
                database,
                cosmos_db_credentials,
                parameters=parameters,
                enable_cross_partition_query=True,
            )
            return results

        example_cosmos_db_query_items_flow()
        ```
    """
    logger = get_run_logger()
    logger.info("Running query from container %s in %s database", container, database)

    container_client = cosmos_db_credentials.get_container_client(container, database)
    partial_query_items = partial(
        container_client.query_items,
        query,
        parameters=parameters,
        partition_key=partition_key,
        **kwargs,
    )
    results = await to_thread.run_sync(partial_query_items)
    return results


@task
async def cosmos_db_read_item(
    item: Union[str, Dict[str, Any]],
    partition_key: Any,
    container: Union[str, "ContainerProxy", Dict[str, Any]],
    database: Union[str, "DatabaseProxy", Dict[str, Any]],
    cosmos_db_credentials: AzureCosmosDbCredentials,
    **kwargs: Any,
) -> List[Union[str, dict]]:
    """
    Get the item identified by item.

    Args:
        item: The ID (name) or dict representing item to retrieve.
        partition_key: Partition key for the item to retrieve.
        container: The ID (name) of the container, a ContainerProxy instance,
            or a dict representing the properties of the container to be retrieved.
        database: The ID (name), dict representing the properties
            or DatabaseProxy instance of the database to read.
        cosmos_db_credentials: Credentials to use for authentication with Azure.
        **kwargs: Additional keyword arguments to pass.

    Returns:
        Dict representing the item to be retrieved.

    Example:
        Read an item using a partition key from Cosmos DB.
        ```python
        from prefect import flow

        from prefect_azure import AzureCosmosDbCredentials
        from prefect_azure.cosmos_db import cosmos_db_read_item

        @flow
        def example_cosmos_db_read_item_flow():
            connection_string = "connection_string"
            cosmos_db_credentials = AzureCosmosDbCredentials(connection_string)

            item = "item"
            partition_key = "partition_key"
            container = "container"
            database = "database"

            result = cosmos_db_read_item(
                item,
                partition_key,
                container,
                database,
                cosmos_db_credentials
            )
            return result

        example_cosmos_db_read_item_flow()
        ```
    """
    logger = get_run_logger()
    logger.info(
        "Reading item %s with partition_key %s from container %s in %s database",
        item,
        partition_key,
        container,
        database,
    )

    container_client = cosmos_db_credentials.get_container_client(container, database)
    read_item = partial(container_client.read_item, item, partition_key, **kwargs)
    result = await to_thread.run_sync(read_item)
    return result


@task
async def cosmos_db_create_item(
    body: Dict[str, Any],
    container: Union[str, "ContainerProxy", Dict[str, Any]],
    database: Union[str, "DatabaseProxy", Dict[str, Any]],
    cosmos_db_credentials: AzureCosmosDbCredentials,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Create an item in the container.

    To update or replace an existing item, use the upsert_item method.

    Args:
        body: A dict-like object representing the item to create.
        container: The ID (name) of the container, a ContainerProxy instance,
            or a dict representing the properties of the container to be retrieved.
        database: The ID (name), dict representing the properties
            or DatabaseProxy instance of the database to read.
        cosmos_db_credentials: Credentials to use for authentication with Azure.
        **kwargs: Additional keyword arguments to pass.

    Returns:
        A dict representing the new item.

    Example:
        Create an item in the container.

        To update or replace an existing item, use the upsert_item method.
        ```python
        import uuid

        from prefect import flow

        from prefect_azure import AzureCosmosDbCredentials
        from prefect_azure.cosmos_db import cosmos_db_create_item

        @flow
        def example_cosmos_db_create_item_flow():
            connection_string = "connection_string"
            cosmos_db_credentials = AzureCosmosDbCredentials(connection_string)

            body = {
                "firstname": "Olivia",
                "age": 3,
                "id": str(uuid.uuid4())
            }
            container = "Persons"
            database = "SampleDB"

            result = cosmos_db_create_item(
                body,
                container,
                database,
                cosmos_db_credentials
            )
            return result

        example_cosmos_db_create_item_flow()
        ```
    """
    logger = get_run_logger()
    logger.info(
        "Creating the item within container %s under %s database",
        container,
        database,
    )

    container_client = cosmos_db_credentials.get_container_client(container, database)
    create_item = partial(container_client.create_item, body, **kwargs)
    result = await to_thread.run_sync(create_item)
    return result

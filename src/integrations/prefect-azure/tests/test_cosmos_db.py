from prefect_azure.cosmos_db import (
    cosmos_db_create_item,
    cosmos_db_query_items,
    cosmos_db_read_item,
)

from prefect import flow


async def test_cosmos_db_query_items_flow(cosmos_db_credentials):
    @flow
    async def cosmos_db_query_items_flow():
        query = "SELECT * FROM c where c.age >= @age"
        container = "Persons"
        database = "SampleDB"
        parameters = [dict(name="@age", value=44)]

        results = await cosmos_db_query_items(
            query,
            container,
            database,
            cosmos_db_credentials,
            parameters=parameters,
            enable_cross_partition_query=True,
        )
        return results

    results = await cosmos_db_query_items_flow()
    assert results == [{"name": "Someone", "age": 23}]


async def test_cosmos_db_read_item_flow(cosmos_db_credentials):
    @flow
    async def cosmos_db_read_item_flow():
        item = "item"
        partition_key = "partition_key"
        container = "container"
        database = "database"

        result = await cosmos_db_read_item(
            item, partition_key, container, database, cosmos_db_credentials
        )
        return result

    result = await cosmos_db_read_item_flow()
    assert result == {"name": "Someone", "age": 23}


async def test_cosmos_db_create_item_flow(cosmos_db_credentials):
    body = {
        "name": "Other",
        "age": 3,
    }

    @flow
    async def cosmos_db_create_item_flow():
        container = "Persons"
        database = "SampleDB"

        result = await cosmos_db_create_item(
            body, container, database, cosmos_db_credentials
        )
        return result

    result = await cosmos_db_create_item_flow()
    assert result == body

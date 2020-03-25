from unittest.mock import MagicMock
from prefect.tasks.azure.cosmosdb import CosmosDBCreateItem

import pytest

import prefect
from prefect.tasks.azure import (
    CosmosDBCreateItem,
    CosmosDBReadItems,
    CosmosDBQueryItems,
)
from prefect.utilities.configuration import set_temporary_config


class TestCosmosDBCreateItem:
    def test_initialization(self):
        task = CosmosDBCreateItem()
        assert task.azure_credentials_secret == "AZ_CREDENTIALS"

    def test_initialization_passes_to_task_constructor(self):
        task = CosmosDBCreateItem(name="test", tags=["Azure"])
        assert task.name == "test"
        assert task.tags == {"Azure"}

    # url, database_or_container_link, item
    def test_raises_if_url_not_eventually_provided(self):
        task = CosmosDBCreateItem(item={}, database_or_container_link="")
        with pytest.raises(ValueError, match="url"):
            task.run()

    def test_raises_if_link_not_eventually_provided(self):
        task = CosmosDBCreateItem(url="", item={})
        with pytest.raises(ValueError, match="database or container link"):
            task.run()

    def test_raises_if_item_not_eventually_provided(self):
        task = CosmosDBCreateItem(url="", database_or_container_link="")
        with pytest.raises(ValueError, match="item"):
            task.run()

    def test_auth_creds_are_pulled_from_secret(self, monkeypatch):
        url = "boo"
        task = CosmosDBCreateItem(url=url, database_or_container_link="foo", item={})
        client = MagicMock()
        cosmos_client = MagicMock(CosmosClient=client)
        monkeypatch.setattr(
            "prefect.tasks.azure.cosmosdb.azure.cosmos.cosmos_client", cosmos_client
        )
        auth_dict = {"AZ_COSMOS_AUTH": {"masterKey": "42"}}
        with set_temporary_config({"use_local_secrets": True}):
            with prefect.context(secrets=dict(AZ_CREDENTIALS=auth_dict)):
                task.run()
        kwargs = client.call_args[1]
        assert kwargs == {"auth": auth_dict["AZ_COSMOS_AUTH"], "url_connection": url}


class TestCosmosDBReadItem:
    def test_initialization(self):
        task = CosmosDBReadItems()
        assert task.azure_credentials_secret == "AZ_CREDENTIALS"

    def test_initialization_passes_to_task_constructor(self):
        task = CosmosDBReadItems(name="test", tags=["Azure"])
        assert task.name == "test"
        assert task.tags == {"Azure"}

    def test_raises_if_url_not_eventually_provided(self):
        task = CosmosDBReadItems(document_or_container_link="")
        with pytest.raises(ValueError, match="url"):
            task.run()

    def test_raises_if_link_not_eventually_provided(self):
        task = CosmosDBReadItems(url="")
        with pytest.raises(ValueError, match="document or container link"):
            task.run()

    def test_auth_creds_are_pulled_from_secret(self, monkeypatch):
        url = "boo"
        task = CosmosDBReadItems(url=url, document_or_container_link="foo")
        client = MagicMock()
        cosmos_client = MagicMock(CosmosClient=client)
        monkeypatch.setattr(
            "prefect.tasks.azure.cosmosdb.azure.cosmos.cosmos_client", cosmos_client
        )
        auth_dict = {"AZ_COSMOS_AUTH": {"masterKey": "42"}}
        with set_temporary_config({"use_local_secrets": True}):
            with prefect.context(secrets=dict(AZ_CREDENTIALS=auth_dict)):
                task.run()
        kwargs = client.call_args[1]
        assert kwargs == {"auth": auth_dict["AZ_COSMOS_AUTH"], "url_connection": url}

    def test_calling_readitem_with_document_link(self, monkeypatch):
        link = "/dbs/my_db/colls/my_col/docs/my_doc"
        task = CosmosDBReadItems(url="foo", document_or_container_link=link)
        client = MagicMock()
        cosmos_client = MagicMock(CosmosClient=client)
        monkeypatch.setattr(
            "prefect.tasks.azure.cosmosdb.azure.cosmos.cosmos_client", cosmos_client
        )
        auth_dict = {"AZ_COSMOS_AUTH": {"masterKey": "42"}}
        with set_temporary_config({"use_local_secrets": True}):
            with prefect.context(secrets=dict(AZ_CREDENTIALS=auth_dict)):
                task.run()
        called_function = client.mock_calls[1][0]
        assert called_function == "().ReadItem"

    def test_calling_readitems_with_document_link(self, monkeypatch):
        link = "/dbs/my_db/colls/my_col"
        task = CosmosDBReadItems(url="foo", document_or_container_link=link)
        client = MagicMock()
        cosmos_client = MagicMock(CosmosClient=client)
        monkeypatch.setattr(
            "prefect.tasks.azure.cosmosdb.azure.cosmos.cosmos_client", cosmos_client
        )
        auth_dict = {"AZ_COSMOS_AUTH": {"masterKey": "42"}}
        with set_temporary_config({"use_local_secrets": True}):
            with prefect.context(secrets=dict(AZ_CREDENTIALS=auth_dict)):
                task.run()
        called_function = client.mock_calls[1][0]
        assert called_function == "().ReadItems"


class TestCosmosDBQueryItem:
    def test_initialization(self):
        task = CosmosDBQueryItems()
        assert task.azure_credentials_secret == "AZ_CREDENTIALS"

    def test_initialization_passes_to_task_constructor(self):
        task = CosmosDBQueryItems(name="test", tags=["Azure"])
        assert task.name == "test"
        assert task.tags == {"Azure"}

    # url, database_or_container_link, item
    def test_raises_if_url_not_eventually_provided(self):
        task = CosmosDBQueryItems(query="", database_or_container_link="")
        with pytest.raises(ValueError, match="url"):
            task.run()

    def test_raises_if_link_not_eventually_provided(self):
        task = CosmosDBQueryItems(url="", query="")
        with pytest.raises(ValueError, match="database or container link"):
            task.run()

    def test_raises_if_query_not_eventually_provided(self):
        task = CosmosDBQueryItems(url="", database_or_container_link="")
        with pytest.raises(ValueError, match="query"):
            task.run()

    def test_auth_creds_are_pulled_from_secret(self, monkeypatch):
        url = "boo"
        task = CosmosDBQueryItems(url=url, database_or_container_link="foo", query="")
        client = MagicMock()
        cosmos_client = MagicMock(CosmosClient=client)
        monkeypatch.setattr(
            "prefect.tasks.azure.cosmosdb.azure.cosmos.cosmos_client", cosmos_client
        )
        auth_dict = {"AZ_COSMOS_AUTH": {"masterKey": "42"}}
        with set_temporary_config({"use_local_secrets": True}):
            with prefect.context(secrets=dict(AZ_CREDENTIALS=auth_dict)):
                task.run()
        kwargs = client.call_args[1]
        assert kwargs == {"auth": auth_dict["AZ_COSMOS_AUTH"], "url_connection": url}

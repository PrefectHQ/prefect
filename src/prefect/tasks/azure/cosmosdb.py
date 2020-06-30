from typing import Any, Dict, List, Union

import azure.cosmos.cosmos_client

from prefect import Task
from prefect.client import Secret
from prefect.utilities.tasks import defaults_from_attrs


class CosmosDBCreateItem(Task):
    """
    Task for creating an item in a Azure Cosmos database.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - url (str, optional): The url to the database.
        - database_or_container_link (str, optional): link to the database or container.
        - item (dict, optional): the item to create
        - azure_credentials_secret (str, optional): the name of the Prefect Secret that stores
            your Azure credentials; this Secret must be JSON string with the key
            `AZ_COSMOS_AUTH`. The value should be dictionary containing `masterKey` or
            `resourceTokens`, where the `masterKey` value is the default authorization key to
            use to create the client, and `resourceTokens` value is the alternative
            authorization key.
        - options (dict, optional): options to be passed to the
            `azure.cosmos.cosmos_client.CosmosClient.CreateItem` method.
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        url: str = None,
        database_or_container_link: str = None,
        item: Dict = None,
        azure_credentials_secret: str = "AZ_CREDENTIALS",
        options: Dict[Any, Any] = None,
        **kwargs
    ) -> None:
        self.url = url
        self.database_or_container_link = database_or_container_link
        self.item = item
        self.azure_credentials_secret = azure_credentials_secret
        self.options = options
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "url",
        "database_or_container_link",
        "item",
        "azure_credentials_secret",
        "options",
    )
    def run(
        self,
        url: str = None,
        database_or_container_link: str = None,
        item: Dict = None,
        azure_credentials_secret: str = "AZ_CREDENTIALS",
        options: Dict[Any, Any] = None,
    ) -> Dict[Any, Any]:
        """
        Task run method.

        Args:
            - url (str, optional): The url to the database.
            - database_or_container_link (str, optional): link to the database or container.
            - item (dict, optional): the item to create
            - azure_credentials_secret (str, optional): the name of the Prefect Secret
                that stores your Azure credentials; this Secret must be JSON string with the
                key `AZ_COSMOS_AUTH`. The value should be dictionary containing `masterKey` or
                `resourceTokens`, where the `masterKey` value is the default authorization key
                to use to create the client, and `resourceTokens` value is the alternative
                authorization key.
            - options (dict, optional): options to be passed to the
                `azure.cosmos.cosmos_client.CosmosClient.CreateItem` method.

        Returns:
            - (dict): the created item.
        """

        if url is None:
            raise ValueError("A url must be provided.")

        if database_or_container_link is None:
            raise ValueError("A database or container link must be provided.")

        if item is None:
            raise ValueError("An item must be provided.")

        azure_credentials = Secret(azure_credentials_secret).get()
        auth_dict = azure_credentials["AZ_COSMOS_AUTH"]

        client = azure.cosmos.cosmos_client.CosmosClient(
            url_connection=url, auth=auth_dict
        )

        return_item = client.CreateItem(
            database_or_container_link, item, options=options
        )

        return return_item


class CosmosDBReadItems(Task):
    """
    Task for reading items from a Azure Cosmos database.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - url (str, optional): The url to the database.
        - document_or_container_link (str, optional): link to a document or container.
            If a document link is provided, the document in question is returned, otherwise
            all docuements are returned.
        - azure_credentials_secret (str, optional): the name of the Prefect Secret
            that stores your Azure credentials; this Secret must be JSON string with the key
            `AZ_COSMOS_AUTH`. The value should be dictionary containing `masterKey` or
            `resourceTokens`, where the `masterKey` value is the default authorization key to
            use to create the client, and `resourceTokens` value is the alternative
            authorization key.
        - options (dict, optional): options to be passed to the
            `azure.cosmos.cosmos_client.CosmosClient.ReadItem` or `ReadItems` method.
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        url: str = None,
        document_or_container_link: str = None,
        azure_credentials_secret: str = "AZ_CREDENTIALS",
        options: Dict[Any, Any] = None,
        **kwargs
    ) -> None:
        self.url = url
        self.document_or_container_link = document_or_container_link
        self.azure_credentials_secret = azure_credentials_secret
        self.options = options

        super().__init__(**kwargs)

    @defaults_from_attrs(
        "url", "document_or_container_link", "azure_credentials_secret", "options"
    )
    def run(
        self,
        url: str = None,
        document_or_container_link: str = None,
        azure_credentials_secret: str = "AZ_CREDENTIALS",
        options: Dict[Any, Any] = None,
    ) -> Union[Dict[Any, Any], List[Dict[Any, Any]]]:
        """
        Task run method.

        Args:
            - url (str, optional): The url to the database.
            - document_or_container_link (str, optional): link to a document or container.
                If a document link is provided, the document in question is returned, otherwise
                all docuements are returned.
            - azure_credentials_secret (str, optional): the name of the Prefect Secret
                that stores your Azure credentials; this Secret must be JSON string with the
                key `AZ_COSMOS_AUTH`. The value should be dictionary containing `masterKey` or
                `resourceTokens`, where the `masterKey` value is the default authorization key
                to use to create the client, and `resourceTokens` value is the alternative
                authorization key.
            - options (dict, optional): options to be passed to the
                `azure.cosmos.cosmos_client.CosmosClient.ReadItem` or `ReadItems` method.

        Returns:
            - (dict or list)): a single document or all documents.
        """

        if url is None:
            raise ValueError("A url must be provided.")

        if document_or_container_link is None:
            raise ValueError("A document or container link must be provided.")

        azure_credentials = Secret(azure_credentials_secret).get()
        auth_dict = azure_credentials["AZ_COSMOS_AUTH"]

        client = azure.cosmos.cosmos_client.CosmosClient(
            url_connection=url, auth=auth_dict
        )

        if self._is_valid_document_link(document_or_container_link):
            return_obj = client.ReadItem(document_or_container_link, options=options)
        else:
            return_obj = client.ReadItems(
                document_or_container_link, feed_options=options
            )
            return_obj = list(return_obj)

        return return_obj

    @staticmethod
    def _is_valid_document_link(link: str) -> bool:
        trimmed_link = link.strip("/")
        split_link = trimmed_link.split("/")

        if (
            len(split_link) == 6
            and split_link[0] == "dbs"
            and split_link[2] == "colls"
            and split_link[4] == "docs"
        ):
            return True
        return False


class CosmosDBQueryItems(Task):
    """
    Task for creating an item in a Azure Cosmos database.
    Note that all initialization arguments can optionally be provided or overwritten at runtime.

    Args:
        - url (str, optional): The url to the database.
        - database_or_container_link (str, optional): link to the database or container.
        - query (dict, optional): the query to run
        - azure_credentials_secret (str, optional): the name of the Prefect Secret
            that stores your Azure credentials; this Secret must be JSON string with the key
            `AZ_COSMOS_AUTH`. The value should be dictionary containing `masterKey` or
            `resourceTokens`, where the `masterKey` value is the default authorization key to
            use to create the client, and `resourceTokens` value is the alternative
            authorization key.
        - options (dict, optional): options to be passed to the
            `azure.cosmos.cosmos_client.CosmosClient.QueryItems` method.
        - partition_key (str, None): Partition key for the query.
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        url: str = None,
        database_or_container_link: str = None,
        query: str = None,
        azure_credentials_secret: str = "AZ_CREDENTIALS",
        options: Dict[Any, Any] = None,
        partition_key: str = None,
        **kwargs
    ) -> None:
        self.url = url
        self.database_or_container_link = database_or_container_link
        self.query = query
        self.azure_credentials_secret = azure_credentials_secret
        self.options = options
        self.partition_key = partition_key
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "url",
        "database_or_container_link",
        "query",
        "azure_credentials_secret",
        "options",
        "partition_key",
    )
    def run(
        self,
        url: str = None,
        database_or_container_link: str = None,
        query: str = None,
        azure_credentials_secret: str = "AZ_CREDENTIALS",
        options: Dict[Any, Any] = None,
        partition_key: str = None,
    ) -> List:
        """
        Task run method.

        Args:
            - url (str, optional): The url to the database.
            - database_or_container_link (str, optional): link to the database or container.
            - query (dict, optional): the query to run
            - azure_credentials_secret (str, optional): the name of the Prefect Secret
                that stores your Azure credentials; this Secret must be JSON string with the
                key `AZ_COSMOS_AUTH`. The value should be dictionary containing `masterKey` or
                `resourceTokens`, where the `masterKey` value is the default authorization key
                to use to create the client, and `resourceTokens` value is the alternative
                authorization key.
            - options (dict, optional): options to be passed to the
                `azure.cosmos.cosmos_client.CosmosClient.QueryItems` method.
            - partition_key (str, None): Partition key for the query.

        Returns:
            - (list): a list containing the query results, one item per row.
        """

        if url is None:
            raise ValueError("A url must be provided.")

        if database_or_container_link is None:
            raise ValueError("A database or container link must be provided.")

        if query is None:
            raise ValueError("A query must be provided.")

        azure_credentials = Secret(azure_credentials_secret).get()
        auth_dict = azure_credentials["AZ_COSMOS_AUTH"]

        client = azure.cosmos.cosmos_client.CosmosClient(
            url_connection=url, auth=auth_dict
        )

        items = client.QueryItems(
            database_or_container_link,
            query,
            options=options,
            partition_key=partition_key,
        )

        return list(items)

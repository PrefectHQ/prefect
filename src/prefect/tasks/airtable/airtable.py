from typing import Any

import airtable

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class WriteAirtableRow(Task):
    """
    A task for writing a row to an Airtable table.

    Note that _all_ initialization settings can be provided / overwritten at runtime.

    Args:
        - base_key (str): the Airtable base key
        - table_name (str): the table name
        - **kwargs (optional): additional kwargs to pass to the `Task` constructor
    """

    def __init__(self, base_key: str = None, table_name: str = None, **kwargs: Any):
        self.base_key = base_key
        self.table_name = table_name
        super().__init__(**kwargs)

    @defaults_from_attrs("base_key", "table_name")
    def run(
        self,
        data: dict,
        base_key: str = None,
        table_name: str = None,
        api_key: str = None,
    ) -> dict:
        """
        Inserts data into an Airtable table

        Args:
            - data (dict): the data to insert. This should be formatted as a dictionary mapping
                each column name to a value.
            - base_key (str): the Airtable base key
            - table_name (str): the table name
            - api_key (str): an Airtable API key. This can be provided via a Prefect Secret

        Returns:
            - a dictionary containing information about the successful insert
        """
        table = airtable.Airtable(base_key, table_name, api_key)
        return table.insert(data)


class ReadAirtableRow(Task):
    """
    A task for reading a row from an Airtable table.

    Note that _all_ initialization settings can be provided / overwritten at runtime.

    Args:
        - base_key (str): the Airtable base key
        - table_name (str): the table name
        - **kwargs (optional): additional kwargs to pass to the `Task` constructor
    """

    def __init__(self, base_key: str = None, table_name: str = None, **kwargs: Any):
        self.base_key = base_key
        self.table_name = table_name
        super().__init__(**kwargs)

    @defaults_from_attrs("base_key", "table_name")
    def run(
        self,
        id: str,
        base_key: str = None,
        table_name: str = None,
        api_key: str = None,
    ) -> dict:
        """
        Reads a row an Airtable table by its id

        Args:
            - id (str): the id of the row
            - base_key (str): the Airtable base key
            - table_name (str): the table name
            - api_key (str): an Airtable API key. This can be provided via a Prefect Secret

        Returns:
            - a dictionary with the keys as the columns and the values as the row's values
        """
        table = airtable.Airtable(base_key, table_name, api_key)
        return table.get(id)

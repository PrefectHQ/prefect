from typing import Any
import warnings

import airtable

from prefect import Task
from prefect.client import Secret
from prefect.utilities.tasks import defaults_from_attrs


class WriteAirtableRow(Task):
    """
    A task for writing a row to an Airtable table.

    Note that _all_ initialization settings can be provided / overwritten at runtime.

    Args:
        - base_key (str): the Airtable base key
        - table_name (str): the table name
        - credentials_secret (str, DEPRECATED): the name of a secret that contains an Airtable API key.
        - **kwargs (optional): additional kwargs to pass to the `Task` constructor
    """

    def __init__(
        self,
        base_key: str = None,
        table_name: str = None,
        credentials_secret: str = None,
        **kwargs: Any
    ):
        self.base_key = base_key
        self.table_name = table_name
        self.credentials_secret = credentials_secret
        super().__init__(**kwargs)

    @defaults_from_attrs("base_key", "table_name", "credentials_secret")
    def run(
        self,
        data: dict,
        base_key: str = None,
        table_name: str = None,
        api_key: str = None,
        credentials_secret: str = None,
    ) -> dict:
        """
        Inserts data into an Airtable table

        Args:
            - data (dict): the data to insert. This should be formatted as a dictionary mapping
                each column name to a value.
            - base_key (str): the Airtable base key
            - table_name (str): the table name
            - api_key (str): an Airtable API key. This can be provided via a Prefect Secret
            - credentials_secret (str, DEPRECATED): the name of a secret that contains an Airtable API key.

        Returns:
            - a dictionary containing information about the successful insert
        """
        if credentials_secret is not None:
            warnings.warn(
                "The `credentials_secret` argument is deprecated. Use a `Secret` task "
                "to pass the credentials value at runtime instead.",
                UserWarning,
            )
            api_key = Secret(credentials_secret).get()
        table = airtable.Airtable(base_key, table_name, api_key)
        return table.insert(data)

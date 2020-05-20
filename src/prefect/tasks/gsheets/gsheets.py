from prefect.utilities.tasks import defaults_from_attrs
import gspread
from typing import Dict, List, Tuple, Union, Any, TypedDict, Callable
import prefect
from prefect import task, Flow, Parameter, Task
from prefect.tasks.secrets.base import SecretBase
from prefect.tasks.secrets import PrefectSecret
import pathlib
from pathlib import Path


class GsheetUpdates(TypedDict):
    """A Typed Dict to describe one of the dictionary elements returned after writing Rows"""

    spreadsheetId: str
    updatedRange: str
    updatedRows: int
    updatedColumns: int
    updatedCells: int


class GsheetResponse(TypedDict):
    """A Typed Dict to describe what's returned after writing Rows"""

    spreadsheetId: str
    tableRange: str
    updates: GsheetUpdates


class WriteGsheetRow(Task):
    """
    A task for writing a row to a Google Sheet.
    Note that _all_ initialization settings can be provided / overwritten at runtime.
    Args:
        - credentials_filename (Union[str, pathlib.Path]): Location of credentials file
        - sheet_key (str): The key corresponding to the Google Sheet
        - worksheet_name (str): The worksheet to target
        - **kwargs (optional): additional kwargs to pass to the `Task` constructor
    """

    def __init__(
        self,
        credentials_filename: Union[str, pathlib.Path] = None,
        sheet_key: str = None,
        worksheet_name: str = None,
        **kwargs: Any
    ):
        self.credentials_filename = credentials_filename
        self.sheet_key = sheet_key
        self.worksheet_name = worksheet_name
        super().__init__(**kwargs)

    @defaults_from_attrs("credentials_filename", "sheet_key", "worksheet_name")
    def run(
        self,
        data: List[Any],
        credentials_filename: Union[str, pathlib.Path] = None,
        sheet_key: str = None,
        worksheet_name: str = None,
    ) -> GsheetResponse:
        """
        Appends a row of data to a Google Sheets worksheet
        Args:
            - data (list): the data to insert. This should be formatted as a list
            - credentials_filename (Union[str, pathlib.Path]): Location of credentials file
            - sheet_key (str): The key corresponding to the Google Sheet
            - worksheet_name (str): The worksheet to target
        Returns:
            - a dictionary containing information about the successful insert
        """
        client = gspread.service_account(filename=self.credentials_filename)
        google_sheet = client.open_by_key(sheet_key)
        worksheet = google_sheet.worksheet(worksheet_name)
        return worksheet.append_row(data)


class ReadGsheetRow(Task):
    """
    A task for reading a row from a Google Sheet.
    Note that _all_ initialization settings can be provided / overwritten at runtime.
    Args:
        - credentials_filename (Union[str, pathlib.Path]): Location of credentials file
        - sheet_key (str): The key corresponding to the Google Sheet
        - worksheet_name (str): The worksheet to target
        - **kwargs (optional): additional kwargs to pass to the `Task` constructor
    """

    def __init__(
        self,
        credentials_filename: Union[str, pathlib.Path] = None,
        sheet_key: str = None,
        worksheet_name: str = None,
        **kwargs: Any
    ):
        self.credentials_filename = credentials_filename
        self.sheet_key = sheet_key
        self.worksheet_name = worksheet_name
        super().__init__(**kwargs)

    @defaults_from_attrs("credentials_filename", "sheet_key", "worksheet_name")
    def run(
        self,
        row: int,
        credentials_filename: Union[str, pathlib.Path] = None,
        sheet_key: str = None,
        worksheet_name: str = None,
    ) -> List[Any]:
        """
        Appends a row of data to a Google Sheets worksheet
        Args:
            - data (list): the data to insert. This should be formatted as a list
            - credentials_filename (Union[str, pathlib.Path]): Location of credentials file
            - sheet_key (str): The key corresponding to the Google Sheet
            - worksheet_name (str): The worksheet to target
        Returns:
            - a list of values from the row 
        """
        client = gspread.service_account(filename=self.credentials_filename)
        google_sheet = client.open_by_key(sheet_key)
        worksheet = google_sheet.worksheet(worksheet_name)
        return worksheet.row_values(row)


def gsheet_helper(fn: Callable):
    """
    A 'factory' to make tasks out of various utility methods in Google Sheets that that `gspread`
    package has. Docs here: https://gspread.readthedocs.io/en/latest/user-guide.html
    Args:
        - credentials_filename (Union[str, pathlib.Path]): Location of credentials file
        - sheet_key (str): The key corresponding to the Google Sheet
        - worksheet_name (str): The worksheet to target
        - **kwargs (optional): additional kwargs to pass to the `Task` constructor
    """

    @task
    def inner(
        credentials_filename: Union[str, pathlib.Path] = None,
        sheet_key: str = None,
        worksheet_name: str = None,
    ):
        """
        A 'factory' to make tasks out of various utility methods in Google Sheets that that `gspread`
        package has. Docs here: https://gspread.readthedocs.io/en/latest/user-guide.html
        Args: 
            - fn (Callable): A function to perform.  For instance, `lambda x: x.find("Dough")`
        """
        client = gspread.service_account(filename=self.credentials_filename)
        google_sheet = client.open_by_key(sheet_key)
        worksheet = google_sheet.worksheet(worksheet_name)
        return fn(worksheet)

    return inner

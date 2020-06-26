from prefect.utilities.tasks import defaults_from_attrs
import gspread
from typing import Any, List, Union
from prefect import Task
import pathlib


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
    ) -> dict:
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
        client = gspread.service_account(filename=credentials_filename)
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
            - row (int): The number of the row to read
            - credentials_filename (Union[str, pathlib.Path]): Location of credentials file
            - sheet_key (str): The key corresponding to the Google Sheet
            - worksheet_name (str): The worksheet to target

        Returns:
            - a list of values from the row
        """
        client = gspread.service_account(filename=credentials_filename)
        google_sheet = client.open_by_key(sheet_key)
        worksheet = google_sheet.worksheet(worksheet_name)
        return worksheet.row_values(row)

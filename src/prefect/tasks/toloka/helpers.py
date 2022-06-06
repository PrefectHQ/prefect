__all__ = [
    "download_json",
]

import requests
from prefect import task
from typing import Any


@task
def download_json(url: str) -> Any:
    """
    Task to download and parse JSON data stored at a given URL.
    Args:
        - url (str): URL to download.

    Returns:
        - Any: the content at this URL, being parsed from JSON.
    """
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

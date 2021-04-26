from typing import Any, List
from prefect.client import Client


def set_key_value(key: str, value: str) -> str:
    """
    Set key value pair, overwriting values for existing key

    Args:
        - key (str): the name of the key
        - value (Any): A json compatible value

    Returns:
        - id (str): the id of the key value pair
    """
    client = Client()
    return client.set_key_value(key=key, value=value)


def get_key_value(key: str) -> Any:
    """
    Get the value for a key

    Args:
        - key (str): the name of the key

    Returns:
        - value (Any): A json compatible value
    """
    client = Client()
    return client.get_key_value(key=key)


def delete_key(key: str) -> bool:
    """
    Delete a key value pair

    Args:
        - key (str): the name of the key

    Returns:
        - success (bool): Whether or not deleting the key succeeded
    """
    client = Client()
    return client.delete_key_value(key=key)


def list_keys() -> List[str]:
    """
    List all keys

    Returns:
        - keys (list): A list of keys
    """
    client = Client()
    return client.list_keys()

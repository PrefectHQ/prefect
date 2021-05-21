from typing import Any, List

import prefect
from prefect.utilities.graphql import with_args
from prefect.client import Client
from prefect.utilities.exceptions import ClientError


def set_key_value(key: str, value: Any) -> str:
    """
    Set key value pair, overwriting values for existing key

    Args:
        - key (str): the name of the key
        - value (Any): A json compatible value

    Returns:
        - id (str): the id of the key value pair

    Raises:
        - ClientError: if using Prefect Server instead of Cloud
    """
    if prefect.config.backend != "cloud":
        raise ClientError("Key Value operations are Cloud only")

    mutation = {
        "mutation($input: set_key_value_input!)": {
            "set_key_value(input: $input)": {"id"}
        }
    }

    client = Client()
    result = client.graphql(
        query=mutation, variables=dict(input=dict(key=key, value=value))
    )

    return result.data.set_key_value.id


def get_key_value(key: str) -> Any:
    """
    Get the value for a key

    Args:
        - key (str): the name of the key

    Returns:
        - value (Any): A json compatible value

    Raises:
        - ValueError: if the specified key does not exist
        - ClientError: if using Prefect Server instead of Cloud
    """
    if prefect.config.backend != "cloud":
        raise ClientError("Key Value operations are Cloud only")

    query = {
        "query": {with_args("key_value", {"where": {"key": {"_eq": key}}}): {"value"}}
    }
    client = Client()
    result = client.graphql(query)  # type: Any
    if len(result.data.key_value) == 0:
        raise ValueError(f"No value found for key: {key}")
    return result.data.key_value[0].value


def delete_key(key: str) -> bool:
    """
    Delete a key value pair

    Args:
        - key (str): the name of the key

    Returns:
        - success (bool): Whether or not deleting the key succeeded

    Raises:
        - ValueError: if the specified key does not exist
        - ClientError: if using Prefect Server instead of Cloud
    """
    if prefect.config.backend != "cloud":
        raise ClientError("Key Value operations are Cloud only")

    query = {
        "query": {with_args("key_value", {"where": {"key": {"_eq": key}}}): {"id"}}
    }
    mutation = {
        "mutation($input: delete_key_value_input!)": {
            "delete_key_value(input: $input)": {"success"}
        }
    }

    client = Client()
    key_value_id_query = client.graphql(query=query)
    if len(key_value_id_query.data.key_value) == 0:
        raise ValueError(f"No key {key} found to delete")
    result = client.graphql(
        query=mutation,
        variables=dict(
            input=dict(key_value_id=key_value_id_query.data.key_value[0].id)
        ),
    )

    return result.data.delete_key_value.success


def list_keys() -> List[str]:
    """
    List all keys

    Returns:
        - keys (list): A list of keys

    Raises:
        - ClientError: if using Prefect Server instead of Cloud
    """
    if prefect.config.backend != "cloud":
        raise ClientError("Key Value operations are Cloud only")
    client = Client()
    result = client.graphql(
        {"query": {"key_value(order_by: {key: asc})": {"key"}}}
    )  # type: ignore
    return [res["key"] for res in result.data.key_value]

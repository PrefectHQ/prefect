import json

import prefect
from prefect.environments import Environment


def from_file(path: str) -> "Environment":
    """
    Loads a serialized Environment class from a file

    Args:
        - path (str): the path of a file to deserialize as an Environment

    Returns:
        - Environment: an Environment object
    """
    schema = prefect.serialization.environment.EnvironmentSchema()
    with open(path, "r") as f:
        return schema.load(json.load(f))

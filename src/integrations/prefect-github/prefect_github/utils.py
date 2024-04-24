"""Utilities to assist with using generated collections."""

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Union

SNAKE_CASE_REGEX1 = re.compile("(.)([A-Z][a-z]+)")
SNAKE_CASE_REGEX2 = re.compile("([a-z0-9])([A-Z])")


def camel_to_snake_case(string: str) -> str:
    """
    Converts CamelCase and lowerCamelCase to snake_case.
    Args:
        string: The string in CamelCase or lowerCamelCase to convert.
    Returns:
        A snake_case version of the string.
    """
    string = SNAKE_CASE_REGEX1.sub(r"\1_\2", string)
    return SNAKE_CASE_REGEX2.sub(r"\1_\2", string).lower()


def initialize_return_fields_defaults(config_path: Union[Path, str]) -> List:
    """
    Reads config_path to parse out the desired default fields to return.
    Args:
        config_path: The path to the config file.
    """
    with open(config_path, "r") as f:
        config = json.load(f)

    return_fields_defaults = defaultdict(lambda: [])
    for op_type, sub_op_types in config.items():
        for sub_op_type in sub_op_types:
            if isinstance(sub_op_type, str):
                return_fields_defaults[(op_type,)].append(
                    camel_to_snake_case(sub_op_type)
                )
            elif isinstance(sub_op_type, dict):
                sub_op_type_key = list(sub_op_type.keys())[0]
                return_fields_defaults[(op_type, sub_op_type_key)] = [
                    camel_to_snake_case(field) for field in sub_op_type[sub_op_type_key]
                ]
    return return_fields_defaults


def strip_kwargs(**kwargs: Dict) -> Dict:
    """
    Drops keyword arguments if value is None because sgqlc.Operation
    errors out if a keyword argument is provided, but set to None.

    Args:
        **kwargs: Input keyword arguments.

    Returns:
        Stripped version of kwargs.
    """
    stripped_dict = {}
    for k, v in kwargs.items():
        if isinstance(v, dict):
            v = strip_kwargs(**v)
        if v is not None:
            stripped_dict[k] = v
    return stripped_dict or {}

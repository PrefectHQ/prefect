import math
from typing import Any, Union, Dict, List


def _sanitize_nan_values(
    item: Union[Dict[str, List[Any]], List[Dict[str, Any]], List[List[Any]]]
) -> Union[Dict[str, List[Any]], List[Dict[str, Any]], List[List[Any]]]:
    """
    Sanitize NaN values in a given item. The item can be a dict, list or float.
    """
    # TODO: Actually use type hints here
    if isinstance(item, list):
        return [_sanitize_nan_values(sub_item) for sub_item in item]  # type: ignore

    elif isinstance(item, dict):  # type: ignore
        return {k: _sanitize_nan_values(v) for k, v in item.items()}  # type: ignore

    elif isinstance(item, float) and math.isnan(item):
        return None  # type: ignore

    else:
        return item

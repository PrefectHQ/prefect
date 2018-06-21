from typing import Tuple, Type, TypeVar, Union

T = TypeVar("T")


def validate_type(obj: T, expected_types: Union[Type, Tuple[Type, ...]]) -> T:
    if not isinstance(obj, expected_types):
        raise TypeError(f'Expected type "{expected_types}"; received {type(obj)}')
    return obj

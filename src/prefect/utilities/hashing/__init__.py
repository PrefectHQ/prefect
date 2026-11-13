import hashlib
import json
from functools import partial
from pathlib import Path
from typing import Any, Callable, Optional, Union

import cloudpickle  # type: ignore  # no stubs available

from prefect.exceptions import HashError
from prefect.serializers import JSONSerializer

_md5 = partial(hashlib.md5, usedforsecurity=False)

_TUPLE_TAG = "__tuple__"
_DICT_TAG = "__dict__"
_JSON_KEY_TYPES = (str, int, float, bool, type(None))
# JSON payloads always start with `[`, so prefixed tagged payloads can never
# collide with untagged ones
_TAGGED_PAYLOAD_PREFIX = b"\x00"


def _tag_json_lossy_types(obj: Any) -> tuple[Any, bool]:
    """
    Recursively tag tuples and dicts with non-string keys so that values JSON would
    otherwise conflate (e.g. `(1, 2)` and `[1, 2]`, `{1: "a"}` and `{"1": "a"}`)
    serialize differently.

    Returns the tagged value and whether any tuple or non-string-key dict was found.
    """
    if isinstance(obj, tuple):
        items = [_tag_json_lossy_types(item) for item in obj]
        return {_TUPLE_TAG: [item for item, _ in items]}, True
    if isinstance(obj, list):
        items = [_tag_json_lossy_types(item) for item in obj]
        return [item for item, _ in items], any(lossy for _, lossy in items)
    if isinstance(obj, dict):
        if all(isinstance(key, str) for key in obj):
            tagged = {key: _tag_json_lossy_types(value) for key, value in obj.items()}
            lossy = any(lossy for _, lossy in tagged.values())
            if len(obj) == 1 and next(iter(obj)) in (_TUPLE_TAG, _DICT_TAG):
                # Escape dicts that look like tags so they can't collide with them
                return {_DICT_TAG: [[key, v] for key, (v, _) in tagged.items()]}, lossy
            return {key: v for key, (v, _) in tagged.items()}, lossy
        for key in obj:
            if not isinstance(key, _JSON_KEY_TYPES):
                raise TypeError(
                    f"keys must be str, int, float, bool or None, not {type(key).__name__}"
                )
        # Sorted by each key's JSON encoding so the result is independent of
        # insertion order, matching `sort_keys=True` for string-keyed dicts
        items = sorted(obj.items(), key=lambda item: json.dumps(item[0]))
        return {
            _DICT_TAG: [[key, _tag_json_lossy_types(value)[0]] for key, value in items]
        }, True
    return obj, False


def stable_hash(*args: Union[str, bytes], hash_algo: Callable[..., Any] = _md5) -> str:
    """Given some arguments, produces a stable 64-bit hash of their contents.

    Supports bytes and strings. Strings will be UTF-8 encoded.

    Args:
        *args: Items to include in the hash.
        hash_algo: Hash algorithm from hashlib to use.

    Returns:
        A hex hash.
    """
    h = hash_algo()
    for a in args:
        if isinstance(a, str):
            a = a.encode()
        h.update(a)
    return h.hexdigest()


def file_hash(path: str, hash_algo: Callable[..., Any] = _md5) -> str:
    """Given a path to a file, produces a stable hash of the file contents.

    Args:
        path (str): the path to a file
        hash_algo: Hash algorithm from hashlib to use.

    Returns:
        str: a hash of the file contents
    """
    contents = Path(path).read_bytes()
    return stable_hash(contents, hash_algo=hash_algo)


def hash_objects(
    *args: Any,
    hash_algo: Callable[..., Any] = _md5,
    raise_on_failure: bool = False,
    **kwargs: Any,
) -> Optional[str]:
    """
    Attempt to hash objects by dumping to JSON or serializing with cloudpickle.

    Args:
        *args: Positional arguments to hash
        hash_algo: Hash algorithm to use
        raise_on_failure: If True, raise exceptions instead of returning None
        **kwargs: Keyword arguments to hash

    Returns:
        A hash string or None if hashing failed

    Raises:
        HashError: If objects cannot be hashed and raise_on_failure is True
    """
    json_error = None
    pickle_error = None

    try:
        serializer = JSONSerializer(dumps_kwargs={"sort_keys": True})
        tagged_args = [_tag_json_lossy_types(arg) for arg in args]
        tagged_kwargs = {
            key: _tag_json_lossy_types(value) for key, value in kwargs.items()
        }
        lossy = any(lossy for _, lossy in tagged_args) or any(
            lossy for _, lossy in tagged_kwargs.values()
        )
        if not lossy:
            # Keep hashes for JSON-native inputs identical to previous releases
            return stable_hash(serializer.dumps((args, kwargs)), hash_algo=hash_algo)
        payload = (
            [arg for arg, _ in tagged_args],
            {key: value for key, (value, _) in tagged_kwargs.items()},
        )
        return stable_hash(
            _TAGGED_PAYLOAD_PREFIX, serializer.dumps(payload), hash_algo=hash_algo
        )
    except Exception as e:
        json_error = str(e)

    try:
        return stable_hash(cloudpickle.dumps((args, kwargs)), hash_algo=hash_algo)  # type: ignore[reportUnknownMemberType]
    except Exception as e:
        pickle_error = str(e)

    if raise_on_failure:
        msg = (
            "Unable to create hash - objects could not be serialized.\n"
            f"  JSON error: {json_error}\n"
            f"  Pickle error: {pickle_error}"
        )
        raise HashError(msg)

    return None

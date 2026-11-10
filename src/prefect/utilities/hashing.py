import hashlib
import json
from functools import partial
from pathlib import Path
from typing import Any, Callable, Optional, Union

import cloudpickle  # type: ignore  # no stubs available

from prefect.exceptions import HashError
from prefect.serializers import JSONSerializer, prefect_json_object_encoder

_md5 = partial(hashlib.md5, usedforsecurity=False)


def _encode_for_hash(value: Any) -> Any:
    """Recursively encode a value into a JSON-serializable structure that
    preserves container and mapping-key types.

    The standard library JSON encoder erases two distinctions that matter
    for hashing task inputs: tuples serialize exactly like lists, and
    mapping keys are coerced to strings (so `{1: "a"}` and `{"1": "a"}`
    serialize identically). To keep distinct inputs hashing differently,
    tuples are tagged and mappings are encoded as sorted lists of
    `[key, value]` pairs, so key types survive serialization. Any other
    value is left untouched for the serializer to handle as before.
    """
    if isinstance(value, tuple):
        return {"__prefect_tuple__": [_encode_for_hash(item) for item in value]}
    if isinstance(value, list):
        return [_encode_for_hash(item) for item in value]
    if isinstance(value, dict):
        pairs = [
            (_encode_for_hash(key), _encode_for_hash(item))
            for key, item in value.items()
        ]
        pairs.sort(
            key=lambda pair: json.dumps(
                pair[0], sort_keys=True, default=prefect_json_object_encoder
            )
        )
        return {"__prefect_dict__": pairs}
    return value


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
        return stable_hash(
            serializer.dumps(_encode_for_hash((args, kwargs))),
            hash_algo=hash_algo,
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

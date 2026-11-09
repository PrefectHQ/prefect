import hashlib
import json
from functools import partial
from pathlib import Path
from typing import Any, Callable, Optional, Union

import cloudpickle  # type: ignore  # no stubs available

from prefect.exceptions import HashError
from prefect.serializers import JSONSerializer

_md5 = partial(hashlib.md5, usedforsecurity=False)


def _encode_for_hashing(obj: Any) -> Any:
    """Recursively convert a value into a JSON-serializable structure.

    Plain JSON erases type distinctions that matter for cache keys: tuples
    serialize exactly like lists, and int dict keys are coerced to strings,
    so different inputs would hash identically and serve stale cached
    results. This encoding tags every value with its type so that inputs
    differing only by container or key type hash differently, while inputs
    that are equal keep the same hash. Dict entries and set items are
    sorted so key/insertion order does not affect the hash.

    Values this cannot represent (bytes, datetimes, arbitrary objects, ...)
    are returned unchanged and handled by the JSON serializer's object
    encoder (or the cloudpickle fallback) exactly as before.
    """
    if obj is None:
        return {"__prefect_type__": "none", "value": None}
    if isinstance(obj, bool):
        return {"__prefect_type__": "bool", "value": obj}
    if isinstance(obj, int):
        return {"__prefect_type__": "int", "value": obj}
    if isinstance(obj, float):
        return {"__prefect_type__": "float", "value": obj}
    if isinstance(obj, str):
        return {"__prefect_type__": "str", "value": obj}
    if isinstance(obj, tuple):
        return {
            "__prefect_type__": "tuple",
            "items": [_encode_for_hashing(item) for item in obj],
        }
    if isinstance(obj, list):
        return {
            "__prefect_type__": "list",
            "items": [_encode_for_hashing(item) for item in obj],
        }
    if isinstance(obj, (set, frozenset)):
        items = sorted(
            (_encode_for_hashing(item) for item in obj),
            key=lambda item: json.dumps(item, sort_keys=True, default=str),
        )
        return {
            "__prefect_type__": "set" if isinstance(obj, set) else "frozenset",
            "items": items,
        }
    if isinstance(obj, dict):
        entries = [
            [_encode_for_hashing(key), _encode_for_hashing(value)]
            for key, value in obj.items()
        ]
        entries.sort(
            key=lambda entry: json.dumps(entry[0], sort_keys=True, default=str)
        )
        return {"__prefect_type__": "dict", "entries": entries}
    return obj


def _contains_ambiguous_type(obj: Any, _seen: Optional[set[int]] = None) -> bool:
    """Return True if plain JSON would erase a type distinction in `obj`.

    JSON serializes tuples exactly like lists, coerces non-string dict
    keys to strings, and has no set representation, so inputs differing
    only by those types would hash identically. Those are the only cases
    that need the type-tagged encoding: for anything else the legacy
    encoding is already unambiguous, and using it keeps hashes stable
    across upgrades. That matters for persistent hashes computed with
    `hash_objects`, such as block schema checksums: re-encoding an
    unchanged block schema must not change its checksum, or the next
    save would create a duplicate schema instead of matching the
    persisted one.

    The top-level `(args, kwargs)` wrapper passed to `hash_objects` is
    not scanned: callers pass each positional argument and keyword value
    separately so the wrapper tuple itself never triggers the tagged
    path. The scan is cycle-safe; unhashable or exotic values that JSON
    cannot represent are left for the serializer / cloudpickle fallback
    exactly as before.
    """
    if isinstance(obj, (tuple, set, frozenset)):
        return True
    if isinstance(obj, dict):
        if _seen is None:
            _seen = set()
        if id(obj) in _seen:
            return False
        _seen.add(id(obj))
        for key, value in obj.items():
            if not isinstance(key, str):
                return True
            if _contains_ambiguous_type(value, _seen):
                return True
        return False
    if isinstance(obj, list):
        if _seen is None:
            _seen = set()
        if id(obj) in _seen:
            return False
        _seen.add(id(obj))
        return any(_contains_ambiguous_type(item, _seen) for item in obj)
    return False


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

    The JSON encoding is type-preserving where it needs to be: tuples hash
    differently from lists, and int dict keys hash differently from str
    dict keys, so inputs that differ only by container or key type do not
    collide. Inputs with no such ambiguity hash exactly as before, so
    persistent hashes (for example block schema checksums) do not change
    on upgrade; only cache keys for ambiguous inputs change, which is the
    point of the fix.

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
        if any(_contains_ambiguous_type(arg) for arg in args) or any(
            _contains_ambiguous_type(value) for value in kwargs.values()
        ):
            payload = _encode_for_hashing((args, kwargs))
        else:
            # Unambiguous inputs hash exactly as before, preserving
            # persistent hashes such as block schema checksums.
            payload = (args, kwargs)
        return stable_hash(
            serializer.dumps(payload),
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

import hashlib
import sys
from functools import partial
from pathlib import Path
from typing import Optional, Union

import cloudpickle

from prefect.serializers import JSONSerializer

if sys.version_info[:2] >= (3, 9):
    _md5 = partial(hashlib.md5, usedforsecurity=False)
else:
    _md5 = hashlib.md5


def stable_hash(*args: Union[str, bytes], hash_algo=_md5) -> str:
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


def file_hash(path: str, hash_algo=_md5) -> str:
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
    *args, hash_algo=_md5, raise_on_failure: bool = False, **kwargs
) -> Optional[str]:
    """
    Attempt to hash objects by dumping to JSON or serializing with cloudpickle.
    On failure of both, `None` will be returned; to raise on failure, set
    `raise_on_failure=True`.
    """
    try:
        serializer = JSONSerializer(dumps_kwargs={"sort_keys": True})
        return stable_hash(serializer.dumps((args, kwargs)), hash_algo=hash_algo)
    except Exception:
        pass

    try:
        return stable_hash(cloudpickle.dumps((args, kwargs)), hash_algo=hash_algo)
    except Exception:
        if raise_on_failure:
            raise

    return None

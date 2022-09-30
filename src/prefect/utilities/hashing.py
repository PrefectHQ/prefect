import hashlib
import json
from pathlib import Path
from typing import Optional, Union

import cloudpickle
from pydantic import BaseModel


class HashableJSONEncoder(json.JSONEncoder):
    """
    Produces hashable JSON representations of objects that are not
    JSON serializable by the default encoder.
    """

    def default(self, obj):

        # Convert bytes to hex string
        if isinstance(obj, bytes):
            return obj.hex()

        # Convert set to list and sort it to produce stable hash
        if isinstance(obj, set):
            set_as_list = list(obj)
            set_as_list.sort()
            return set_as_list

        # Convert Pydantic model instances, such as Blocks, to JSON string
        # using Pydantic's .json() method
        if isinstance(obj, BaseModel):
            return obj.json(sort_keys=True)

        return json.JSONEncoder.default(self, obj)


def stable_hash(*args: Union[str, bytes], hash_algo=hashlib.md5) -> str:
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


def file_hash(path: str, hash_algo=hashlib.md5) -> str:
    """Given a path to a file, produces a stable hash of the file contents.

    Args:
        path (str): the path to a file
        hash_algo: Hash algorithm from hashlib to use.

    Returns:
        str: a hash of the file contents
    """
    contents = Path(path).read_bytes()
    return stable_hash(contents, hash_algo=hash_algo)


def hash_objects(*args, hash_algo=hashlib.md5, **kwargs) -> Optional[str]:
    """
    Attempt to hash objects by dumping to JSON or serializing with cloudpickle.
    On failure of both, `None` will be returned
    """
    try:
        return stable_hash(
            json.dumps((args, kwargs), sort_keys=True, cls=HashableJSONEncoder),
            hash_algo=hash_algo,
        )
    except Exception:
        pass

    try:
        return stable_hash(cloudpickle.dumps((args, kwargs)), hash_algo=hash_algo)
    except Exception:
        pass

    return None

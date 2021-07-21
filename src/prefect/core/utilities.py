import hashlib
import asyncio
import contextvars
from pathlib import Path
from functools import wraps


def file_hash(path) -> str:
    contents = Path(path).read_bytes()
    return hashlib.md5(contents).hexdigest()


def sync(fn):
    """
    Create a synchronous version of a function; if there is an event loop already this
    will throw an exception
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.get_event_loop().run_until_complete(fn(*args, **kwargs))

    return wrapper

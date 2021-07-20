import hashlib
import asyncio
from pathlib import Path


def file_hash(path) -> str:
    contents = Path(path).read_bytes()
    return hashlib.md5(contents).hexdigest()


def sync(fn, *args, **kwargs):
    """
    Run an async function synchronously
    """
    return asyncio.get_event_loop().run_until_complete(fn(*args, **kwargs))

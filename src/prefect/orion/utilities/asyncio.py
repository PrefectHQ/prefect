import asyncio
import functools
from typing import Any, Callable


async def run_in_threadpool(fn: Callable, *args, **kwargs) -> Any:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, functools.partial(fn, *args, **kwargs))

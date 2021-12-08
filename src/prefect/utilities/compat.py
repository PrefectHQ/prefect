"""
Utilities for Python version compatibility
"""
import sys

if sys.version_info < (3, 9):
    # https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread

    import asyncio
    import functools

    async def asyncio_to_thread(fn, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, functools.partial(fn, *args, **kwargs))

else:
    from asyncio import to_thread as asyncio_to_thread

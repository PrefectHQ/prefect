import inspect
from typing import Any, Union

from prefect.filesystems import NullFileSystem, WritableFileSystem


def call_explicitly_sync_block_method(
    block: Union[WritableFileSystem, NullFileSystem],
    method: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> Any:
    """
    Call a block method synchronously.

    TODO: remove this once we have explicit sync/async methods on all storage blocks

    see https://github.com/PrefectHQ/prefect/issues/15008
    """
    # Pass _sync=True to ensure we get synchronous execution even when called
    # from an async context (e.g., within a sync flow running in an async test)
    return getattr(block, method)(*args, _sync=True, **kwargs)


async def call_explicitly_async_block_method(
    block: Union[WritableFileSystem, NullFileSystem],
    method: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> Any:
    """
    TODO: remove this once we have explicit async methods on all storage blocks

    see https://github.com/PrefectHQ/prefect/issues/15008
    """
    if hasattr(block, f"a{method}"):  # explicit async method
        return await getattr(block, f"a{method}")(*args, **kwargs)
    elif hasattr(getattr(block, method, None), "aio"):  # sync_compatible
        return await getattr(block, method).aio(block, *args, **kwargs)
    else:  # should not happen in prefect, but users can override impls
        maybe_coro = getattr(block, method)(*args, **kwargs)
        if inspect.isawaitable(maybe_coro):
            return await maybe_coro
        else:
            return maybe_coro

import asyncio
import time

import pytest

from prefect.utilities.timeout import timeout, timeout_async


class CustomTimeoutError(TimeoutError): ...


def test_timeout_raises_custom_error_type_sync():
    with pytest.raises(CustomTimeoutError):
        with timeout(seconds=0.1, timeout_exc_type=CustomTimeoutError):
            time.sleep(1)


async def test_timeout_raises_custom_error_type_async():
    with pytest.raises(CustomTimeoutError):
        with timeout_async(seconds=0.1, timeout_exc_type=CustomTimeoutError):
            await asyncio.sleep(1)


@pytest.mark.parametrize("timeout_context", [timeout, timeout_async])
def test_timeout_raises_if_non_timeout_exception_type_passed(timeout_context):
    with pytest.raises(ValueError, match="must be a subclass of `TimeoutError`"):
        with timeout_context(timeout_exc_type=Exception):
            pass

import asyncio
import time

import pytest

from prefect.utilities.timeout import timeout, timeout_async


class CustomTimeoutError(TimeoutError):
    ...


def test_timeout_raises_custom_error_type_sync():
    with pytest.raises(CustomTimeoutError):
        with timeout(seconds=0.1, timeout_exc_type=CustomTimeoutError):
            time.sleep(1)


async def test_timeout_raises_custom_error_type_async():
    with pytest.raises(CustomTimeoutError):
        with timeout_async(seconds=0.1, timeout_exc_type=CustomTimeoutError):
            await asyncio.sleep(1)

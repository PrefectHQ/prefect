import sys
from typing import Any

import pytest

from prefect import flow, task


@pytest.mark.parametrize(
    "method,args",
    [
        ("submit", (None,)),
        ("map", ([None],)),
    ],
)
async def test_awaiting_previously_async_task_methods_fail(
    method: str,
    args: Any,
):
    @task
    async def get_random_number(_) -> int:
        return 42

    @flow
    async def run_a_task():
        await getattr(get_random_number, method)(*args)

    if sys.version_info >= (3, 14):
        match = "object can't be awaited"
    else:
        match = "can't be used in 'await' expression"

    with pytest.raises(TypeError, match=match):
        await run_a_task()

import concurrent.futures

import pytest

from prefect._internal.concurrency.supervisors import AsyncSupervisor, SyncSupervisor


def fake_submit_fn(__fn, *args, **kwargs):
    future = concurrent.futures.Future()
    future.set_result(__fn(*args, **kwargs))
    return future


def fake_fn(*args, **kwargs):
    pass


@pytest.mark.parametrize("cls", [AsyncSupervisor, SyncSupervisor])
async def test_supervisor_repr(cls):
    supervisor = cls(submit_fn=fake_submit_fn)
    assert repr(supervisor) == f"<{cls.__name__}(fake_submit_fn, owner='MainThread')>"
    supervisor.submit(fake_fn, 1, 2)
    assert (
        repr(supervisor)
        == f"<{cls.__name__}(fake_submit_fn, submitted=fake_fn, owner='MainThread')>"
    )

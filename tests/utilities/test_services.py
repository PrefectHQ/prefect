import statistics

import httpx
import pytest

from prefect.testing.utilities import AsyncMock
from prefect.utilities.services import critical_service_loop


async def test_critical_service_loop_operates_normally():
    workload = AsyncMock(
        side_effect=[
            None,
            None,
            None,
            None,
            None,
            KeyboardInterrupt,
        ]
    )

    await critical_service_loop(workload, 0.0)

    assert workload.await_count == 6


async def test_tolerates_single_intermittent_error():
    workload = AsyncMock(
        side_effect=[
            None,
            httpx.ConnectError("woops"),
            None,
            None,
            None,
            KeyboardInterrupt,
        ]
    )

    await critical_service_loop(workload, 0.0)

    assert workload.await_count == 6


async def test_tolerates_two_consecutive_errors():
    workload = AsyncMock(
        side_effect=[
            None,
            httpx.ConnectError("woops"),
            httpx.TimeoutException("oofta"),
            None,
            None,
            KeyboardInterrupt,
        ]
    )

    await critical_service_loop(workload, 0.0)

    assert workload.await_count == 6


async def test_tolerates_majority_errors():
    workload = AsyncMock(
        side_effect=[
            httpx.ConnectError("woops"),
            None,
            httpx.TimeoutException("oofta"),
            httpx.TimeoutException("boo"),
            None,
            KeyboardInterrupt,
        ]
    )

    await critical_service_loop(workload, 0.0)

    assert workload.await_count == 6


@pytest.mark.flaky(max_runs=3)
async def test_quits_after_3_consecutive_errors(capsys: pytest.CaptureFixture):
    workload = AsyncMock(
        side_effect=[
            None,
            httpx.TimeoutException("oofta"),
            httpx.TimeoutException("boo"),
            httpx.ConnectError("woops"),
            None,
            KeyboardInterrupt,
        ]
    )

    await critical_service_loop(workload, 0.0, consecutive=3)

    assert workload.await_count == 4
    result = capsys.readouterr()
    assert "Failed the last 3 attempts" in result.out
    assert "Examples of recent errors" in result.out
    assert "httpx.ConnectError: woops" in result.out
    assert "httpx.TimeoutException: boo" in result.out


async def test_consistent_sleeps_between_loops(monkeypatch):
    workload = AsyncMock(
        side_effect=[
            None,
            None,
            None,
            None,
            None,
            KeyboardInterrupt,
        ]
    )
    sleeper = AsyncMock()

    monkeypatch.setattr("prefect.utilities.services.anyio.sleep", sleeper)
    await critical_service_loop(workload, 0.0)
    assert workload.await_count == 6

    sleep_times = [call.args[0] for call in sleeper.await_args_list]
    assert sleep_times == [
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    ]


async def test_jittered_sleeps_between_loops(monkeypatch):
    workload = AsyncMock(
        side_effect=[
            None,
            None,
            None,
            None,
            None,
            KeyboardInterrupt,
        ]
    )
    sleeper = AsyncMock()

    monkeypatch.setattr("prefect.utilities.services.anyio.sleep", sleeper)
    await critical_service_loop(workload, 42, jitter_range=0.3)
    assert workload.await_count == 6

    sleep_times = [call.args[0] for call in sleeper.await_args_list]
    assert statistics.variance(sleep_times) > 0
    assert min(sleep_times) > 42 * (1 - 0.3)
    assert max(sleep_times) < 42 * (1 + 0.3)

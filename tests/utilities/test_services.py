import statistics

import httpx
import pytest

from prefect.testing.utilities import AsyncMock
from prefect.utilities.services import critical_service_loop


class UncapturedException(BaseException):
    pass


async def test_critical_service_loop_operates_normally():
    workload = AsyncMock(
        side_effect=[
            None,
            None,
            None,
            None,
            None,
            UncapturedException,
        ]
    )

    with pytest.raises(UncapturedException):
        await critical_service_loop(workload, 0.0)

    assert workload.await_count == 6


async def test_critical_service_loop_does_not_capture_keyboard_interrupt():
    workload = AsyncMock(side_effect=KeyboardInterrupt)

    with pytest.raises(KeyboardInterrupt):
        await critical_service_loop(workload, 0.0)

    assert workload.await_count == 1


async def test_tolerates_single_intermittent_error():
    workload = AsyncMock(
        side_effect=[
            None,
            httpx.ConnectError("woops"),
            None,
            None,
            None,
            UncapturedException,
        ]
    )

    with pytest.raises(UncapturedException):
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
            UncapturedException,
        ]
    )

    with pytest.raises(UncapturedException):
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
            UncapturedException,
        ]
    )

    with pytest.raises(UncapturedException):
        await critical_service_loop(workload, 0.0)

    assert workload.await_count == 6


async def test_quits_after_3_consecutive_errors(capsys: pytest.CaptureFixture):
    workload = AsyncMock(
        side_effect=[
            None,
            httpx.TimeoutException("oofta"),
            httpx.TimeoutException("boo"),
            httpx.ConnectError("woops"),
            None,
            None,
        ]
    )

    with pytest.raises(RuntimeError, match="Service exceeded error threshold"):
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
            UncapturedException,
        ]
    )
    sleeper = AsyncMock()

    monkeypatch.setattr("prefect.utilities.services.anyio.sleep", sleeper)

    with pytest.raises(UncapturedException):
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
            UncapturedException,
        ]
    )
    sleeper = AsyncMock()

    monkeypatch.setattr("prefect.utilities.services.anyio.sleep", sleeper)

    with pytest.raises(UncapturedException):
        await critical_service_loop(workload, 42, jitter_range=0.3)

    assert workload.await_count == 6

    sleep_times = [call.args[0] for call in sleeper.await_args_list]
    assert statistics.variance(sleep_times) > 0
    assert min(sleep_times) > 42 * (1 - 0.3)
    assert max(sleep_times) < 42 * (1 + 0.3)


async def test_captures_all_http_500_errors():
    workload = AsyncMock(
        side_effect=[
            None,
            httpx.HTTPStatusError(
                "foo", request=None, response=httpx.Response(status_code=500)
            ),
            None,
            httpx.HTTPStatusError(
                "foo", request=None, response=httpx.Response(status_code=501)
            ),
            None,
            httpx.HTTPStatusError(
                "foo", request=None, response=httpx.Response(status_code=502)
            ),
            httpx.HTTPStatusError(
                "foo", request=None, response=httpx.Response(status_code=503)
            ),
            UncapturedException,
        ]
    )

    with pytest.raises(UncapturedException):
        await critical_service_loop(workload, 0.0)

    assert workload.await_count == 8


async def test_does_not_capture_other_http_status_errors():
    workload = AsyncMock(
        side_effect=[
            None,
            httpx.HTTPStatusError(
                "foo", request=None, response=httpx.Response(status_code=403)
            ),
            None,
            UncapturedException,
        ]
    )

    with pytest.raises(httpx.HTTPStatusError):
        await critical_service_loop(workload, 0.0)

    assert workload.await_count == 2


async def test_backoff_quits_after_6_consecutive_errors_twice(
    capsys: pytest.CaptureFixture,
):
    workload = AsyncMock(
        side_effect=[
            None,
            httpx.TimeoutException("oofta"),
            httpx.TimeoutException("boo"),
            httpx.ConnectError("woops"),
            httpx.TimeoutException("oofta"),
            httpx.TimeoutException("boo"),
            httpx.ConnectError("woops"),
            None,
        ]
    )

    with pytest.raises(RuntimeError, match="Service exceeded error threshold"):
        await critical_service_loop(workload, 0.0, consecutive=3, backoff=2)

    assert workload.await_count == 7
    result = capsys.readouterr()
    assert "Failed the last 3 attempts" in result.out
    assert "Examples of recent errors" in result.out
    assert "httpx.ConnectError: woops" in result.out
    assert "httpx.TimeoutException: boo" in result.out


async def test_backoff_does_not_exit_after_5_consecutive_errors(
    capsys: pytest.CaptureFixture,
):
    workload = AsyncMock(
        side_effect=[
            None,
            httpx.TimeoutException("oofta"),
            httpx.TimeoutException("boo"),
            httpx.ConnectError("woops"),
            httpx.TimeoutException("oofta"),
            httpx.TimeoutException("boo"),
            None,
            UncapturedException,
        ]
    )

    with pytest.raises(UncapturedException):
        await critical_service_loop(workload, 0.0, consecutive=3, backoff=2)

    assert workload.await_count == 8
    result = capsys.readouterr()
    assert "Failed the last 3 attempts" in result.out
    assert "Examples of recent errors" in result.out
    assert "httpx.ConnectError: woops" in result.out
    assert "httpx.TimeoutException: boo" in result.out


async def test_backoff_reset_on_success(
    capsys: pytest.CaptureFixture,
):
    workload = AsyncMock(
        side_effect=[
            None,
            httpx.TimeoutException("oofta"),
            httpx.TimeoutException("boo"),
            httpx.ConnectError("woops"),
            httpx.TimeoutException("oofta"),
            httpx.TimeoutException("boo"),
            None,  # Reset on success so another 5 should run
            httpx.TimeoutException("oofta"),
            httpx.TimeoutException("boo"),
            httpx.ConnectError("woops"),
            httpx.TimeoutException("oofta"),
            httpx.TimeoutException("boo"),
            None,
            UncapturedException,
        ]
    )

    with pytest.raises(UncapturedException):
        await critical_service_loop(workload, 0.0, consecutive=3, backoff=2)

    assert workload.await_count == 14
    result = capsys.readouterr()
    assert "Failed the last 3 attempts" in result.out
    assert "Examples of recent errors" in result.out
    assert "httpx.ConnectError: woops" in result.out
    assert "httpx.TimeoutException: boo" in result.out


async def test_backoff_increases_interval_on_each_consecutive_group(
    capsys: pytest.CaptureFixture, mock_anyio_sleep
):
    workload = AsyncMock(
        side_effect=[
            # 1s
            httpx.TimeoutException("oofta"),
            httpx.TimeoutException("boo"),
            # 2s
            httpx.TimeoutException("oofta"),
            httpx.TimeoutException("boo"),
            httpx.TimeoutException("oofta"),
            # 4s
            httpx.TimeoutException("boo"),
            httpx.ConnectError("woops"),
            httpx.TimeoutException("oofta"),
            # 8s
            httpx.TimeoutException("boo"),
            httpx.TimeoutException("oofta"),
            httpx.TimeoutException("boo"),
            # 16s
            httpx.ConnectError("woops"),
            httpx.TimeoutException("oofta"),
            httpx.TimeoutException("boo"),
            # 32s
            httpx.ConnectError("woops"),
            # exit
            UncapturedException,
        ]
    )

    with mock_anyio_sleep.assert_sleeps_for(
        1 * 2 + 2 * 3 + 4 * 3 + 8 * 3 + 16 * 3 + 32
    ):
        with pytest.raises(UncapturedException):
            await critical_service_loop(workload, 1, consecutive=3, backoff=6)

    assert workload.await_count == 16


async def test_sleeps_for_interval(capsys: pytest.CaptureFixture, mock_anyio_sleep):
    workload = AsyncMock(
        side_effect=[
            httpx.TimeoutException("oofta"),
            httpx.TimeoutException("boo"),
            None,
            UncapturedException,
        ]
    )

    with mock_anyio_sleep.assert_sleeps_for(1 * 3):
        with pytest.raises(UncapturedException):
            await critical_service_loop(workload, 1, consecutive=3)

    assert workload.await_count == 4

import logging

from prefect.workers._worker_channel._transport import WorkerChannelTransport


def test_reconnect_delay_caps_before_float_overflow():
    transport = WorkerChannelTransport(
        api_url="http://localhost:4200/api",
        work_pool_name="test-work-pool",
        logger=logging.getLogger("test-worker-channel"),
        reconnect_base_seconds=1.0,
        reconnect_max_seconds=30.0,
    )

    assert transport.reconnect_delay(1) == 1.0
    assert transport.reconnect_delay(6) == 30.0
    assert transport.reconnect_delay(1025) == 30.0

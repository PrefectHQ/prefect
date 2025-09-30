from prefect import flow
from prefect.client.schemas.objects import (
    ConcurrencyLimitConfig,
    ConcurrencyLimitStrategy,
)
from prefect.testing.utilities import prefect_test_harness


@flow
def slow_starting_flow():
    """Simulates a slow-starting flow."""
    import time

    time.sleep(2)  # Simulate startup delay
    return "completed"


async def test_concurrency_lease_survives_delay(monkeypatch):
    """Test that flows with startup delays succeed when lease duration is sufficient."""

    # Set custom lease durations via environment variables
    monkeypatch.setenv(
        "PREFECT_SERVER_CONCURRENCY_LEASE_DURATION", "10"
    )  # 10 seconds for renewals
    monkeypatch.setenv(
        "PREFECT_SERVER_CONCURRENCY_INITIAL_LEASE_TIMEOUT", "10"
    )  # 10 seconds for initial lease

    async with prefect_test_harness():
        # Deploy flow with concurrency limit
        deployment = await slow_starting_flow.to_deployment(
            name="test-deployment",
            concurrency_limit=ConcurrencyLimitConfig(
                limit=1, collision_strategy=ConcurrencyLimitStrategy.CANCEL_NEW
            ),
        )

        # Run the flow
        flow_run = await deployment.create_flow_run()
        result = await flow_run.wait_for_completion()

        # Should complete successfully
        assert result.is_completed()


async def test_concurrency_lease_timeout_with_short_duration(monkeypatch):
    """Test that flows fail when lease duration is too short."""

    # Set very short lease durations via environment variables
    monkeypatch.setenv(
        "PREFECT_SERVER_CONCURRENCY_LEASE_DURATION", "1"
    )  # 1 second for renewals - too short
    monkeypatch.setenv(
        "PREFECT_SERVER_CONCURRENCY_INITIAL_LEASE_TIMEOUT", "1"
    )  # 1 second for initial lease - too short

    async with prefect_test_harness():
        # Deploy flow with concurrency limit
        deployment = await slow_starting_flow.to_deployment(
            name="test-deployment-short",
            concurrency_limit=ConcurrencyLimitConfig(
                limit=1, collision_strategy=ConcurrencyLimitStrategy.CANCEL_NEW
            ),
        )

        # Run the flow
        flow_run = await deployment.create_flow_run()
        result = await flow_run.wait_for_completion()

        # Should fail due to lease timeout
        assert result.is_failed()
        assert "lease renewal failed" in result.message.lower()


async def test_default_lease_duration_unchanged():
    """Test that the default lease duration behavior is unchanged."""

    # Don't set any custom lease duration - should use default 300 seconds
    async with prefect_test_harness():
        # Deploy flow with concurrency limit
        deployment = await slow_starting_flow.to_deployment(
            name="test-deployment-default",
            concurrency_limit=ConcurrencyLimitConfig(
                limit=1, collision_strategy=ConcurrencyLimitStrategy.CANCEL_NEW
            ),
        )

        # Run the flow
        flow_run = await deployment.create_flow_run()
        result = await flow_run.wait_for_completion()

        # Should complete successfully with default settings
        assert result.is_completed()

#!/usr/bin/env python3
"""
Test script to verify flow run state change logging.
This creates a simple flow and runs it to trigger state transitions
while enabling debug logging to see all the state change logs.
"""

import asyncio
import logging
from prefect import flow, get_run_logger
from prefect.client import get_client


# Configure debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Enable debug logging for the key modules
loggers_to_debug = [
    'prefect.flow_engine',
    'prefect.server.api.flow_runs',
    'prefect.server.models.flow_runs',
    'prefect.server.orchestration.instrumentation_policies',
]

for logger_name in loggers_to_debug:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)


@flow(name="test-flow-state-logging")
def test_flow():
    """A simple test flow to trigger state transitions."""
    run_logger = get_run_logger()
    run_logger.info("Starting test flow execution")
    
    # Do some simple work
    import time
    time.sleep(1)
    
    run_logger.info("Test flow execution completed")
    return "Flow completed successfully"


@flow(name="test-flow-with-failure")
def test_flow_with_failure():
    """A test flow that raises an exception to test failure state transitions."""
    run_logger = get_run_logger()
    run_logger.info("Starting test flow with planned failure")
    
    # Raise an exception to trigger failure state
    raise ValueError("This is a planned test failure")


async def test_async_flow():
    """Test async flow state transitions."""
    
    @flow(name="test-async-flow")
    async def async_test_flow():
        run_logger = get_run_logger()
        run_logger.info("Starting async test flow execution")
        
        # Do some async work
        await asyncio.sleep(1)
        
        run_logger.info("Async test flow execution completed")
        return "Async flow completed successfully"
    
    return await async_test_flow()


def main():
    """Run tests to verify state change logging."""
    print("=" * 60)
    print("Testing Flow Run State Change Logging")
    print("=" * 60)
    
    # Test 1: Successful sync flow
    print("\n1. Testing successful sync flow execution...")
    try:
        result = test_flow()
        print(f"✓ Sync flow completed: {result}")
    except Exception as e:
        print(f"✗ Sync flow failed: {e}")
    
    # Test 2: Failed sync flow
    print("\n2. Testing failed sync flow execution...")
    try:
        result = test_flow_with_failure()
        print(f"✗ Flow should have failed but returned: {result}")
    except Exception as e:
        print(f"✓ Flow failed as expected: {e}")
    
    # Test 3: Successful async flow
    print("\n3. Testing successful async flow execution...")
    try:
        result = asyncio.run(test_async_flow())
        print(f"✓ Async flow completed: {result}")
    except Exception as e:
        print(f"✗ Async flow failed: {e}")
    
    print("\n" + "=" * 60)
    print("Test completed. Check the debug logs above for state transitions.")
    print("You should see logs prefixed with:")
    print("- 'Flow run <id> attempting state transition'")
    print("- 'Flow run <id> state transition result'")
    print("- 'SERVER: Flow run <id> orchestration requested'")
    print("- 'API: Flow run <id> set_state request'")
    print("=" * 60)


if __name__ == "__main__":
    main()
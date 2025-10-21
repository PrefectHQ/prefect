#!/usr/bin/env python3
"""
Test hello_world with debug logging enabled and verify the logging works.
"""

import logging
import time
from prefect import flow, task, tags

# Configure debug logging with a simpler format for clarity
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s | %(name)s | %(message)s'
)

# Enable debug logging for all state change modules
loggers_to_debug = [
    'prefect.flow_engine',
    'prefect.task_engine',
    'prefect.server.api.flow_runs',
    'prefect.server.api.task_runs',
    'prefect.server.models.flow_runs',
    'prefect.server.models.task_runs',
    'prefect.server.orchestration.instrumentation_policies',
]

print("Enabling debug logging for:")
for logger_name in loggers_to_debug:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    print(f"  - {logger_name}")

@task(name="test-task")
def test_task(value: int):
    """A simple test task."""
    return value * 2

@flow(log_prints=True)
def test_flow_with_task(name: str = "Marvin") -> None:
    """Flow with both flow and task state transitions."""
    print(f"Hello, {name}!")
    result = test_task(5)
    print(f"Task result: {result}")
    return result

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Testing flow and task state transitions with debug logging")
    print("=" * 60)
    
    # Give some time for server startup
    time.sleep(2)
    
    # run the flow with a task
    with tags("test"):
        result = test_flow_with_task("Debug Test")
    
    print("\n" + "=" * 60)
    print("Test completed! Debug logs should show state transitions above.")
    print("=" * 60)
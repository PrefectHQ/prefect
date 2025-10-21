#!/usr/bin/env python3
"""
Test script to verify task run state change logging.
This creates a simple flow with tasks and runs it to trigger task state transitions
while enabling debug logging to see all the task state change logs.
"""

import asyncio
import logging
from prefect import flow, task, get_run_logger


# Configure debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Enable debug logging for the key modules
loggers_to_debug = [
    'prefect.task_engine',
    'prefect.server.api.task_runs',
    'prefect.server.models.task_runs',
    'prefect.server.orchestration.instrumentation_policies',
]

for logger_name in loggers_to_debug:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)


@task(name="simple-test-task")
def test_task(value: int):
    """A simple test task to trigger state transitions."""
    run_logger = get_run_logger()
    run_logger.info(f"Processing value: {value}")
    
    # Do some simple work
    result = value * 2
    
    run_logger.info(f"Task completed with result: {result}")
    return result


@task(name="failing-test-task")
def failing_task():
    """A test task that raises an exception to test failure state transitions."""
    run_logger = get_run_logger()
    run_logger.info("Starting task that will fail")
    
    # Raise an exception to trigger failure state
    raise ValueError("This is a planned test task failure")


@task(name="async-test-task")
async def async_test_task(value: str):
    """An async test task to trigger async state transitions."""
    run_logger = get_run_logger()
    run_logger.info(f"Processing async value: {value}")
    
    # Do some async work
    await asyncio.sleep(0.5)
    
    result = f"Processed: {value}"
    run_logger.info(f"Async task completed with result: {result}")
    return result


@flow(name="test-flow-with-tasks")
def test_flow_with_tasks():
    """A test flow that runs multiple tasks to trigger various state transitions."""
    run_logger = get_run_logger()
    run_logger.info("Starting test flow with tasks")
    
    # Test successful task
    result1 = test_task(5)
    run_logger.info(f"Task 1 result: {result1}")
    
    # Test async task
    result2 = async_test_task("hello")
    run_logger.info(f"Task 2 result: {result2}")
    
    # Test failing task
    try:
        failing_task()
    except Exception as e:
        run_logger.info(f"Task 3 failed as expected: {e}")
    
    return {"task1": result1, "task2": result2}


@flow(name="test-flow-with-multiple-tasks")  
def test_flow_multiple_tasks():
    """A test flow that runs multiple tasks in parallel."""
    run_logger = get_run_logger()
    run_logger.info("Starting test flow with multiple tasks")
    
    # Create multiple tasks to run in parallel
    futures = []
    for i in range(3):
        future = test_task.submit(i + 1)
        futures.append(future)
    
    # Wait for all tasks to complete
    results = [future.result() for future in futures]
    run_logger.info(f"All tasks completed with results: {results}")
    
    return results


def main():
    """Run tests to verify task state change logging."""
    print("=" * 60)
    print("Testing Task Run State Change Logging")
    print("=" * 60)
    
    # Test 1: Flow with successful and failing tasks
    print("\n1. Testing flow with successful and failing tasks...")
    try:
        result = test_flow_with_tasks()
        print(f"✓ Flow with tasks completed: {result}")
    except Exception as e:
        print(f"✗ Flow with tasks failed: {e}")
    
    # Test 2: Flow with multiple parallel tasks
    print("\n2. Testing flow with multiple parallel tasks...")
    try:
        result = test_flow_multiple_tasks()
        print(f"✓ Flow with multiple tasks completed: {result}")
    except Exception as e:
        print(f"✗ Flow with multiple tasks failed: {e}")
    
    # Test 3: Individual task execution
    print("\n3. Testing individual task execution...")
    try:
        result = test_task(10)
        print(f"✓ Individual task completed: {result}")
    except Exception as e:
        print(f"✗ Individual task failed: {e}")
    
    print("\n" + "=" * 60)
    print("Test completed. Check the debug logs above for task state transitions.")
    print("You should see logs prefixed with:")
    print("- 'Task run <id> attempting state transition'")
    print("- 'Task run <id> state transition result'")
    print("- 'SERVER: Task run <id> orchestration requested'")
    print("- 'API: Task run <id> set_state request'")
    print("=" * 60)


if __name__ == "__main__":
    main()
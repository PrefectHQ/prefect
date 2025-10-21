#!/usr/bin/env python3
"""
Test state logging by setting up logging first, then importing prefect.
"""

import logging

# Configure debug logging FIRST, before importing prefect
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)

# Enable debug logging for all state change modules BEFORE importing prefect
loggers_to_debug = [
    'prefect.flow_engine',
    'prefect.task_engine', 
    'prefect.server.api.flow_runs',
    'prefect.server.api.task_runs',
    'prefect.server.models.flow_runs',
    'prefect.server.models.task_runs',
    'prefect.server.orchestration.instrumentation_policies',
]

print("Setting up debug logging for:")
for logger_name in loggers_to_debug:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    print(f"  - {logger_name}")

# NOW import prefect after logging is set up
from prefect import flow, task, tags

@task(name="simple-task")
def simple_task():
    """A simple task to trigger state transitions."""
    return "Task completed!"

@flow(name="simple-flow")
def simple_flow():
    """A simple flow to trigger state transitions."""
    result = simple_task()
    return result

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Running simple flow to test state transition logging")
    print("=" * 60)
    
    # Run a simple flow
    result = simple_flow()
    print(f"Final result: {result}")
    
    print("=" * 60)
    print("Check debug logs above for state transitions!")
    print("=" * 60)
#!/usr/bin/env python3
"""
Test script to verify STLOGGING prefix appears in all logging layers
"""

import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Configure logging to show all debug messages
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-8s | %(name)s - %(message)s'
)

# Enable debug logging for our specific loggers
loggers = [
    'prefect.flow_engine',
    'prefect.task_engine', 
    'prefect.server.api.flow_runs',
    'prefect.server.api.task_runs',
    'prefect.server.models.flow_runs',
    'prefect.server.models.task_runs',
    'prefect.server.orchestration.instrumentation_policies'
]

for logger_name in loggers:
    logging.getLogger(logger_name).setLevel(logging.DEBUG)

# Import prefect after logging setup
from prefect import task, flow

@task
def hello_task(name: str = "world") -> str:
    return f"Hello {name}!"

@flow
def hello_flow(name: str = "world") -> str:
    message = hello_task(name)
    print(message)
    return message

if __name__ == "__main__":
    print("Running hello_flow to test STLOGGING prefix...")
    result = hello_flow()
    print(f"Flow completed with result: {result}")
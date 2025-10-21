#!/usr/bin/env python3
"""
Test hello_world with debug logging enabled to see state transitions.
"""

import logging
from prefect import flow, tags

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

@flow(log_prints=True)
def hello(name: str = "Marvin") -> None:
    """Log a friendly greeting."""
    print(f"Hello, {name}!")

if __name__ == "__main__":
    print("=" * 60)
    print("Testing hello_world with debug logging enabled")
    print("=" * 60)
    
    # run the flow with default parameters
    with tags("test"):
        hello()  # Logs: "Hello, Marvin!"
    
    print("=" * 60)
    print("Check the debug logs above for flow state transitions!")
    print("=" * 60)
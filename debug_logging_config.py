# Debug logging configuration for flow run state changes
# This file can be used to configure logging when running Prefect flows

# To enable debug logging when running flows, set the following environment variables:
# export PREFECT_LOGGING_LEVEL=DEBUG
# export PYTHONPATH=/Users/vkrot/workspace/prefect/src:$PYTHONPATH

# Or use this Python configuration in your scripts:

import logging

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Enable debug logging for flow run state change components
FLOW_STATE_LOGGERS = [
    'prefect.flow_engine',                                    # Flow engine state transitions
    'prefect.server.api.flow_runs',                          # API endpoint logging
    'prefect.server.models.flow_runs',                       # Server model logging  
    'prefect.server.orchestration.instrumentation_policies', # Orchestration policy logging
    'prefect.client.orchestration',                          # Client-side state changes
]

# Enable debug logging for task run state change components
TASK_STATE_LOGGERS = [
    'prefect.task_engine',                                    # Task engine state transitions
    'prefect.server.api.task_runs',                          # Task API endpoint logging
    'prefect.server.models.task_runs',                       # Task server model logging
    'prefect.server.orchestration.instrumentation_policies', # Task orchestration policy logging
]

# Combined list of all state change loggers
ALL_STATE_LOGGERS = FLOW_STATE_LOGGERS + TASK_STATE_LOGGERS

def enable_flow_state_debug_logging():
    """Enable debug logging for all flow run state change components."""
    for logger_name in FLOW_STATE_LOGGERS:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        print(f"Enabled DEBUG logging for: {logger_name}")

def enable_task_state_debug_logging():
    """Enable debug logging for all task run state change components."""
    for logger_name in TASK_STATE_LOGGERS:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        print(f"Enabled DEBUG logging for: {logger_name}")

def enable_all_state_debug_logging():
    """Enable debug logging for all flow and task state change components."""
    for logger_name in ALL_STATE_LOGGERS:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        print(f"Enabled DEBUG logging for: {logger_name}")

# Example usage:
# from debug_logging_config import enable_all_state_debug_logging
# enable_all_state_debug_logging()
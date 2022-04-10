"""
This module contains a collection of tasks to interact with Hightouch.
"""

try:
    from prefect.tasks.hightouch.hightouch_tasks import HightouchRunSync
except ImportError as err:
    raise ImportError(
        'Using `prefect.tasks.hightouch` requires Prefect to be installed with the "hightouch" extra.'
    ) from err

__all__ = ["HightouchRunSync"]

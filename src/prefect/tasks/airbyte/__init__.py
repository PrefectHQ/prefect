"""
This module contains a task for triggering [Airbyte](https://airbyte.io/) connection sync jobs
"""
from .airbyte import AirbyteConnectionTask

__all__ = ["AirbyteConnectionTask"]

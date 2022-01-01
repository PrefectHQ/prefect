"""
This module contains a task for starting and monitoring [Census](https://getcensus.com/) sync jobs
"""
from .census import CensusSyncTask

__all__ = ["CensusSyncTask"]

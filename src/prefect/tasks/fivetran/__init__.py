"""
This module contains a task for starting and monitoring [Fivetran](https://fivetran.com/) connector sync jobs
"""
from .fivetran import FivetranSyncTask

__all__ = ["FivetranSyncTask"]

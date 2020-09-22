"""
This module contains a collection of tasks for interacting with MySQL databases via
the pymysql library.
"""
import warnings

try:
    from prefect.tasks.mysql.mysql import MySQLExecute, MySQLFetch

    warnings.warn(
        "Importing from `prefect.contrib.tasks` has been deprecated and instead should be `prefect.tasks`"
    )
except ImportError:
    raise ImportError(
        'Using `prefect.contrib.tasks.mysql` requires Prefect to be installed with the "mysql" extra.'
    )

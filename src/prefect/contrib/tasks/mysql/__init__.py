"""
This module contains a collection of tasks for interacting with MySQL databases via
the pymysql library.
"""

try:
    from prefect.contrib.tasks.mysql.mysql import MySQLExecute, MySQLFetch
except ImportError:
    raise ImportError(
        'Using `prefect.contrib.tasks.mysql` requires Prefect to be installed with the "mysql" extra.'
    )

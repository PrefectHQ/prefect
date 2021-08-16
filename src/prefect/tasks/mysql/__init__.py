"""
This module contains a collection of tasks for interacting with MySQL databases via
the pymysql library.
"""
try:
    from prefect.tasks.mysql.mysql import MySQLExecute, MySQLFetch
except ImportError as import_error:
    raise ImportError(
        'Using `prefect.tasks.mysql` requires Prefect to be installed with the "mysql" extra.'
    ) from import_error

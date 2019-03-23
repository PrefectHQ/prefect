import sqlite3 as sql
from contextlib import closing
from typing import Any, cast

import prefect
from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class SQLiteQuery(Task):
    """
    Task for executing a single query against a sqlite3 database; returns
    the result (if any) from the query.

    Args:
        - db (str): the location of the database (.db) file
        - query (str, optional): the optional _default_ query to execute at runtime;
            can also be provided as a keyword to `run`, which takes precendence over this default.
            Note that a query should consist of a _single SQL statement_.
        - **kwargs (optional): additional keyword arguments to pass to the
            standard Task initalization
    """

    def __init__(self, db: str, query: str = None, **kwargs: Any):
        self.db = db
        self.query = query
        super().__init__(**kwargs)

    @defaults_from_attrs("query")
    def run(self, query: str = None):
        """
        Args:
            - query (str, optional): the optional query to execute at runtime;
                if not provided, `self.query` will be used instead. Note that a query should consist of a _single SQL statement_.

        Returns:
            - [Any]: the results of the query
        """
        query = cast(str, query)
        with closing(sql.connect(self.db)) as conn:
            with closing(conn.cursor()) as cursor:
                cursor.execute(query)
                out = cursor.fetchall()
                conn.commit()
        return out


class SQLiteScript(Task):
    """
    Task for executing a SQL script against a sqlite3 database.

    Args:
        - db (str): the location of the database (.db) file
        - script (str, optional): the optional _default_ script string to render at runtime;
            can also be provided as a keyword to `run`, which takes precendence over this default.
        - **kwargs (optional): additional keyword arguments to pass to the
            standard Task initialization
    """

    def __init__(self, db: str, script: str = None, **kwargs: Any):
        self.db = db
        self.script = script
        super().__init__(**kwargs)

    @defaults_from_attrs("script")
    def run(self, script: str = None):
        """
        Args:
            - script (str, optional): the optional script to execute at runtime;
                if not provided, `self.script` will be used instead.
        """
        with closing(sql.connect(self.db)) as conn:
            with closing(conn.cursor()) as cursor:
                cursor.executescript(script)
                conn.commit()

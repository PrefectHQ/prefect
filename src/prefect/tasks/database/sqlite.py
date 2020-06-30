import sqlite3 as sql
from contextlib import closing
from typing import Any, cast

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class SQLiteQuery(Task):
    """
    Task for executing a single query against a sqlite3 database; returns
    the result (if any) from the query.

    Args:
        - db (str, optional): the location of the database (.db) file
        - query (str, optional): the optional _default_ query to execute at runtime;
            can also be provided as a keyword to `run`, which takes precendence over this default.
            Note that a query should consist of a _single SQL statement_.
        - **kwargs (optional): additional keyword arguments to pass to the
            standard Task initalization
    """

    def __init__(self, db: str = None, query: str = None, **kwargs: Any):
        self.db = db
        self.query = query
        super().__init__(**kwargs)

    @defaults_from_attrs("db", "query")
    def run(self, db: str = None, query: str = None):
        """
        Args:
            - db (str, optional): the location of the database (.db) file;
                if not provided, `self.db` will be used instead.
            - query (str, optional): the optional query to execute at runtime;
                if not provided, `self.query` will be used instead. Note that a
                query should consist of a _single SQL statement_.

        Returns:
            - [Any]: the results of the query
        """
        db = cast(str, db)
        query = cast(str, query)
        with closing(sql.connect(db)) as conn:
            with closing(conn.cursor()) as cursor:
                cursor.execute(query)
                out = cursor.fetchall()
                conn.commit()
        return out


class SQLiteScript(Task):
    """
    Task for executing a SQL script against a sqlite3 database.

    Args:
        - db (str, optional): the location of the database (.db) file
        - script (str, optional): the optional _default_ script string to render at runtime;
            can also be provided as a keyword to `run`, which takes precendence over this default.
        - **kwargs (optional): additional keyword arguments to pass to the
            standard Task initialization
    """

    def __init__(self, db: str = None, script: str = None, **kwargs: Any):
        self.db = db
        self.script = script
        super().__init__(**kwargs)

    @defaults_from_attrs("db", "script")
    def run(self, db: str = None, script: str = None):
        """
        Args:
            - db (str, optional): the location of the database (.db) file;
                if not provided, `self.db` will be used instead.
            - script (str, optional): the optional script to execute at runtime;
                if not provided, `self.script` will be used instead.
        """
        with closing(sql.connect(db)) as conn:
            with closing(conn.cursor()) as cursor:
                cursor.executescript(script)
                conn.commit()

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
            can also be provided as a keyword to `run`, which takes precedence over this default.
            Note that a query should consist of a _single SQL statement_.
        - data (tuple, optional): values to use when `query` is a parametrized string. See
            https://docs.python.org/3/library/sqlite3.html for more details.
        - **kwargs (optional): additional keyword arguments to pass to the
            standard Task initalization
    """

    def __init__(
        self, db: str = None, query: str = None, data: tuple = (), **kwargs: Any
    ):
        self.db = db
        self.query = query
        self.data = data
        super().__init__(**kwargs)

    @defaults_from_attrs("db", "query", "data")
    def run(self, db: str = None, query: str = None, data: tuple = ()):
        """
        Args:
            - db (str, optional): the location of the database (.db) file;
                if not provided, `self.db` will be used instead.
            - query (str, optional): the optional query to execute at runtime;
                if not provided, `self.query` will be used instead. Note that a
                query should consist of a _single SQL statement_.
            - data (tuple, optional): values to use when query is a parametrized string. See
                https://docs.python.org/3/library/sqlite3.html for more details.

        Returns:
            - [Any]: the results of the query
        """
        db = cast(str, db)
        query = cast(str, query)
        data = cast(tuple, data)

        if db is None:
            raise ValueError("The db must be specified")

        if query is None:
            raise ValueError("The query string must be specified")

        if "?" in query and not data:
            raise ValueError(
                "The data inputs must be specified as a tuple if query "
                "contains parametrized values '?'"
            )

        with closing(sql.connect(db)) as conn:
            with closing(conn.cursor()) as cursor:
                cursor.execute(query, data)
                out = cursor.fetchall()
        return out


class SQLiteScript(Task):
    """
    Task for executing a SQL script against a sqlite3 database; does not
    return any values, but useful for creating tables and inserting values into the tables.

    Args:
        - db (str, optional): the location of the database (.db) file
        - script (str, optional): the optional _default_ script string to render at runtime;
            can also be provided as a keyword to `run`, which takes precedence over this default.
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
        if db is None:
            raise ValueError("The db must be specified")

        if script is None:
            raise ValueError("The query script string must be specified")

        with closing(sql.connect(db)) as conn:
            with closing(conn.cursor()) as cursor:
                cursor.executescript(script)

# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import sqlite3 as sql
from contextlib import closing

import prefect
from prefect import Task


class SQLiteQueryTask(Task):
    """
    Args:
        - db (str): the location of the database (.db) file
        - query (str, optional): the optional _default_ query to execute at runtime;
            can also be provided as a keyword to `run`, which takes precendence over this default.
            Note that a query should consist of a _single SQL statement_.
        - **kwargs (optional): additional keyword arguments to pass to the
            standard Task constructor
    """

    def __init__(self, db: str, query: str = None, **kwargs) -> None:
        self.db = db
        self.query = query
        super().__init__(**kwargs)

    def run(self, query: str = None):
        """
        Args:
            - query (str, optional): the optional query to execute at runtime;
                if not provided, `self.query` will be used instead. Note that a query should consist of a _single SQL statement_.

        Returns:
            - [Any]: the results of the query
        """
        query = self.query if query is None else query
        with closing(sql.connect(self.db)) as conn:
            with closing(conn.cursor()) as cursor:
                cursor.execute(query)
                out = cursor.fetchall()
                conn.commit()
        return out


class SQLiteScriptTask(Task):
    """
    Args:
        - script (str, optional): the optional _default_ query string to render at runtime;
            can also be provided as a keyword to `run`, which takes precendence over this default.
        - db (str, optional): the optional _default_ template string to render at runtime;
            can also be provided as a keyword to `run`, which takes precendence over this default.
        - **kwargs (optional): additional keyword arguments to pass to the
            standard Task constructor
    """

    def __init__(self, db: str, script: str = None, **kwargs) -> None:
        self.db = db
        self.script = script
        super().__init__(**kwargs)

    def run(self, script: str = None):
        """
        Args:
            - query (str, optional): the optional query to execute at runtime;
                if not provided, `self.query` will be used instead. Note that a query should consist of a _single SQL statement_.
        """
        script = self.script if script is None else script
        with closing(sql.connect(self.db)) as conn:
            with closing(conn.cursor()) as cursor:
                cursor.executescript(script)
                conn.commit()

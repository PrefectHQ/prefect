# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

import sqlite3 as sql
from contextlib import closing

import prefect
from prefect import Task


class SqliteTask(Task):
    """
    Args:
        - query (str, optional): the optional _default_ template string to render at runtime;
            can also be provided as a keyword to `run`, which takes precendence over this default.
        - db (str, optional): the optional _default_ template string to render at runtime;
            can also be provided as a keyword to `run`, which takes precendence over this default.
        - **kwargs (optional): additional keyword arguments to pass to the
            standard Task constructor
    """

    def __init__(self, query: str = None, db: str = ":memory:", **kwargs) -> None:
        self.db = db
        self.query = query
        super().__init__(**kwargs)

    def run(self, query: str = None):
        """
        Args:
            - query (str, optional): the template string to render; if not
                provided, `self.template` will be used

        Returns:
            - str: the rendered string
        """
        query = self.query if query is None else query
        with closing(sql.connect(self.db)) as conn:
            with closing(conn.cursor()) as cursor:
                cursor.executescript(query)
                out = cursor.fetchall()
                conn.commit()
        return out

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs

import pymysql.cursors
import logging
from typing import Any, Callable, Union


class MySQLExecute(Task):
    """
    Task for executing a query against a MySQL database.

    Args:
        - db_name (str): name of MySQL database
        - user (str): user name used to authenticate
        - password (str): password used to authenticate
        - host (str): database host address
        - port (int, optional): port used to connect to MySQL database, defaults to 3307
            if not provided
        - query (str, optional): query to execute against database
        - commit (bool, optional): set to True to commit transaction, defaults to false
        - charset (str, optional): charset you want to use (defaults to utf8mb4)
        - ssl (dict, optional): A dict of arguments similar to mysql_ssl_set()’s
                parameters used for establishing encrypted connections using SSL
        - **kwargs (Any, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        db_name: str = None,
        user: str = None,
        password: str = None,
        host: str = None,
        port: int = 3306,
        query: str = None,
        commit: bool = False,
        charset: str = "utf8mb4",
        ssl: dict = None,
        **kwargs: Any,
    ):
        self.db_name = db_name
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.query = query
        self.commit = commit
        self.charset = charset
        self.ssl = ssl
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "db_name",
        "user",
        "password",
        "host",
        "port",
        "query",
        "commit",
        "charset",
        "ssl",
    )
    def run(
        self,
        db_name: str = None,
        user: str = None,
        password: str = None,
        host: str = None,
        port: int = None,
        query: str = None,
        commit: bool = None,
        charset: str = None,
        ssl: dict = None,
    ) -> int:
        """
        Task run method. Executes a query against MySQL database.

        Args:
            - db_name (str): name of MySQL database
            - user (str): user name used to authenticate
            - password (str): password used to authenticate
            - host (str): database host address
            - port (int, optional): port used to connect to MySQL database, defaults to 3307
                if not provided
            - query (str, optional): query to execute against database
            - commit (bool, optional): set to True to commit transaction, defaults to false
            - charset (str, optional): charset you want to use (defaults to "utf8mb4")
            - ssl (dict, optional): A dict of arguments similar to mysql_ssl_set()’s
                parameters used for establishing encrypted connections using SSL. To connect
                with SSL, at least `ssl_ca`, `ssl_cert`, and `ssl_key` must be specified.

        Returns:
            - executed (int): number of affected rows

        Raises:
            - pymysql.MySQLError
        """
        if not query:
            raise ValueError("A query string must be provided")

        conn = pymysql.connect(
            host=host,
            user=user,
            password=password,
            db=db_name,
            charset=charset,
            port=port,
            ssl=ssl,
        )

        try:
            with conn.cursor() as cursor:
                executed = cursor.execute(query)
                if commit:
                    conn.commit()

            conn.close()
            logging.debug("Execute Results: %s", executed)
            return executed

        except (Exception, pymysql.MySQLError) as e:
            conn.close()
            logging.debug("Execute Error: %s", e)
            raise e


class MySQLFetch(Task):
    """
    Task for fetching results of query from MySQL database.

    Args:
        - db_name (str): name of MySQL database
        - user (str): user name used to authenticate
        - password (str): password used to authenticate
        - host (str): database host address
        - port (int, optional): port used to connect to MySQL database, defaults to 3307 if not
            provided
        - fetch (str, optional): one of "one" "many" or "all", used to determine how many
            results to fetch from executed query
        - fetch_count (int, optional): if fetch = 'many', determines the number of results to
            fetch, defaults to 10
        - query (str, optional): query to execute against database
        - commit (bool, optional): set to True to commit transaction, defaults to false
        - charset (str, optional): charset of the query, defaults to "utf8mb4"
        - cursor_type (Union[str, Callable], optional): The cursor type to use.
            Can be `'cursor'` (the default), `'dictcursor'`, `'sscursor'`, `'ssdictcursor'`,
            or a full cursor class.
        - ssl (dict, optional): A dict of arguments similar to mysql_ssl_set()’s
                parameters used for establishing encrypted connections using SSL. To connect
                with SSL, at least `ssl_ca`, `ssl_cert`, and `ssl_key` must be specified.
        - **kwargs (Any, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        db_name: str = None,
        user: str = None,
        password: str = None,
        host: str = None,
        port: int = 3306,
        fetch: str = "one",
        fetch_count: int = 10,
        query: str = None,
        commit: bool = False,
        charset: str = "utf8mb4",
        cursor_type: Union[str, Callable] = "cursor",
        ssl: dict = None,
        **kwargs: Any,
    ):
        self.db_name = db_name
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.fetch = fetch
        self.fetch_count = fetch_count
        self.query = query
        self.commit = commit
        self.charset = charset
        self.cursor_type = cursor_type
        self.ssl = ssl
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "db_name",
        "user",
        "password",
        "host",
        "port",
        "fetch",
        "fetch_count",
        "query",
        "commit",
        "charset",
        "cursor_type",
        "ssl",
    )
    def run(
        self,
        db_name: str = None,
        user: str = None,
        password: str = None,
        host: str = None,
        port: int = None,
        fetch: str = None,
        fetch_count: int = None,
        query: str = None,
        commit: bool = None,
        charset: str = None,
        cursor_type: Union[str, Callable] = None,
        ssl: dict = None,
    ) -> Any:
        """
        Task run method. Executes a query against MySQL database and fetches results.

        Args:
            - db_name (str): name of MySQL database
            - user (str): user name used to authenticate
            - password (str): password used to authenticate
            - host (str): database host address
            - port (int, optional): port used to connect to MySQL database, defaults to 3307 if not
                provided
            - fetch (str, optional): one of "one" "many" or "all", used to determine how many
                results to fetch from executed query
            - fetch_count (int, optional): if fetch = 'many', determines the number of results to
                fetch, defaults to 10
            - query (str, optional): query to execute against database
            - commit (bool, optional): set to True to commit transaction, defaults to false
            - charset (str, optional): charset of the query, defaults to "utf8mb4"
            - cursor_type (Union[str, Callable], optional): The cursor type to use.
                Can be `'cursor'` (the default), `'dictcursor'`, `'sscursor'`, `'ssdictcursor'`,
                or a full cursor class.
            - ssl (dict, optional): A dict of arguments similar to mysql_ssl_set()’s
                    parameters used for establishing encrypted connections using SSL

        Returns:
            - results (tuple or list of tuples): records from provided query

        Raises:
            - pymysql.MySQLError
        """
        if not query:
            raise ValueError("A query string must be provided")

        if fetch not in {"one", "many", "all"}:
            raise ValueError(
                "The 'fetch' parameter must be one of the following - ('one', 'many', 'all')"
            )

        cursor_types = {
            "cursor": pymysql.cursors.Cursor,
            "dictcursor": pymysql.cursors.DictCursor,
            "sscursor": pymysql.cursors.SSCursor,
            "ssdictcursor": pymysql.cursors.SSDictCursor,
        }

        if callable(cursor_type):
            cursor_class = cursor_type
        elif isinstance(cursor_type, str):
            cursor_class = cursor_types.get(cursor_type.lower())
        else:
            cursor_class = None

        if not cursor_class:
            raise TypeError(
                f"'cursor_type' should be one of {list(cursor_types.keys())} or a "
                f"full cursor class, got {cursor_type}"
            )

        conn = pymysql.connect(
            host=host,
            user=user,
            password=password,
            db=db_name,
            charset=charset,
            port=port,
            cursorclass=cursor_class,
            ssl=ssl,
        )

        try:
            with conn.cursor() as cursor:
                cursor.execute(query)

                # override mypy inferred type since we redefine with incompatible types
                results: Any

                if fetch == "all":
                    results = cursor.fetchall()
                elif fetch == "many":
                    results = cursor.fetchmany(fetch_count)
                else:
                    results = cursor.fetchone()

                if commit:
                    conn.commit()

            conn.close()
            logging.debug("Fetch Results: %s", results)
            return results

        except (Exception, pymysql.MySQLError) as e:
            conn.close()
            logging.debug("Fetch Error: %s", e)
            raise e

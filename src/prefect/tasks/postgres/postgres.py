import psycopg2 as pg

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class PostgresExecute(Task):
    """
    Task for executing a query against a Postgres database.

    Args:
        - db_name (str): name of Postgres database
        - user (str): user name used to authenticate
        - host (str): database host address
        - port (int, optional): port used to connect to Postgres database, defaults to 5432 if
            not provided
        - query (str, optional): query to execute against database
        - data (tuple, optional): values to use in query, must be specified using placeholder
            is query string
        - commit (bool, optional): set to True to commit transaction, defaults to false
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        db_name: str,
        user: str,
        host: str,
        port: int = 5432,
        query: str = None,
        data: tuple = None,
        commit: bool = False,
        **kwargs
    ):
        self.db_name = db_name
        self.user = user
        self.host = host
        self.port = port
        self.query = query
        self.data = data
        self.commit = commit
        super().__init__(**kwargs)

    @defaults_from_attrs("query", "data", "commit")
    def run(
        self,
        query: str = None,
        data: tuple = None,
        commit: bool = False,
        password: str = None,
    ):
        """
        Task run method. Executes a query against Postgres database.

        Args:
            - query (str, optional): query to execute against database
            - data (tuple, optional): values to use in query, must be specified using
                placeholder is query string
            - commit (bool, optional): set to True to commit transaction, defaults to false
            - password (str): password used to authenticate; should be provided from a `Secret` task

        Returns:
            - None

        Raises:
            - ValueError: if query parameter is None or a blank string
            - DatabaseError: if exception occurs when executing the query
        """
        if not query:
            raise ValueError("A query string must be provided")

        # connect to database, open cursor
        # allow psycopg2 to pass through any exceptions raised
        conn = pg.connect(
            dbname=self.db_name,
            user=self.user,
            password=password,
            host=self.host,
            port=self.port,
        )

        # try to execute query
        # context manager automatically rolls back failed transactions
        try:
            with conn:
                with conn.cursor() as cursor:
                    executed = cursor.execute(query=query, vars=data)
                    if commit:
                        conn.commit()
                    else:
                        conn.rollback()

            conn.close()
            return executed

        # pass through error, and ensure connection is closed
        except (Exception, pg.DatabaseError):
            conn.close()
            raise


class PostgresFetch(Task):
    """
    Task for fetching results of query from Postgres database.

    Args:
        - db_name (str): name of Postgres database
        - user (str): user name used to authenticate
        - host (str): database host address
        - port (int, optional): port used to connect to Postgres database, defaults to 5432 if
            not provided
        - fetch (str, optional): one of "one" "many" or "all", used to determine how many
            results to fetch from executed query
        - fetch_count (int, optional): if fetch = 'many', determines the number of results to
            fetch, defaults to 10
        - query (str, optional): query to execute against database
        - data (tuple, optional): values to use in query, must be specified using placeholder
            is query string
        - commit (bool, optional): set to True to commit transaction, defaults to false
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        db_name: str,
        user: str,
        host: str,
        port: int = 5432,
        fetch: str = "one",
        fetch_count: int = 10,
        query: str = None,
        data: tuple = None,
        commit: bool = False,
        **kwargs
    ):
        self.db_name = db_name
        self.user = user
        self.host = host
        self.port = port
        self.fetch = fetch
        self.fetch_count = fetch_count
        self.query = query
        self.data = data
        self.commit = commit
        super().__init__(**kwargs)

    @defaults_from_attrs("fetch", "fetch_count", "query", "data", "commit")
    def run(
        self,
        fetch: str = "one",
        fetch_count: int = 10,
        query: str = None,
        data: tuple = None,
        commit: bool = False,
        password: str = None,
    ):
        """
        Task run method. Executes a query against Postgres database and fetches results.

        Args:
            - fetch (str, optional): one of "one" "many" or "all", used to determine how many
                results to fetch from executed query
            - fetch_count (int, optional): if fetch = 'many', determines the number of results
                to fetch, defaults to 10
            - query (str, optional): query to execute against database
            - data (tuple, optional): values to use in query, must be specified using
                placeholder is query string
            - commit (bool, optional): set to True to commit transaction, defaults to false
            - password (str): password used to authenticate; should be provided from a `Secret` task

        Returns:
            - records (tuple or list of tuples): records from provided query

        Raises:
            - ValueError: if query parameter is None or a blank string
            - DatabaseError: if exception occurs when executing the query
        """
        if not query:
            raise ValueError("A query string must be provided")

        if fetch not in {"one", "many", "all"}:
            raise ValueError(
                "The 'fetch' parameter must be one of the following - ('one', 'many', 'all')"
            )

        # connect to database, open cursor
        # allow psycopg2 to pass through any exceptions raised
        conn = pg.connect(
            dbname=self.db_name,
            user=self.user,
            password=password,
            host=self.host,
            port=self.port,
        )

        # try to execute query
        # context manager automatically rolls back failed transactions
        try:
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute(query=query, vars=data)

                    # fetch results
                    if fetch == "all":
                        records = cursor.fetchall()
                    elif fetch == "many":
                        records = cursor.fetchmany(fetch_count)
                    else:
                        records = cursor.fetchone()

                    if commit:
                        conn.commit()

            conn.close()
            return records

        # pass through error, and ensure connection is closed
        except (Exception, pg.DatabaseError):
            conn.close()
            raise

import pyodbc

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class SqlServerExecute(Task):
    """
    Task for executing a query against a SQL Server database.

    Args:
        - db_name (str): name of SQL Server database
        - user (str): user name used to authenticate
        - host (str): database host address
        - port (int, optional): port used to connect to SQL Server database, defaults to 1433 if
            not provided
        - driver (str, optional): driver used to communicate with SQL Server database
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
        port: int = 1433,
        driver: str = "ODBC Driver 17 for SQL Server",
        query: str = None,
        data: tuple = None,
        commit: bool = False,
        **kwargs
    ):
        self.db_name = db_name
        self.user = user
        self.host = host
        self.port = port
        self.driver = driver
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
        Task run method. Executes a query against SQL Server database.

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

        # connect to database
        cnxn = pyodbc.connect(
            driver=self.driver,
            host=self.host,
            database=self.db_name,
            port=self.port,
            user=self.user,
            password=password,
        )

        # try to execute query
        # context manager automatically rolls back failed transactions
        try:
            with cnxn.cursor() as cursor:
                executed = cursor.execute(query=query, vars=data)
                if commit:
                    cnxn.commit()
                else:
                    cnxn.rollback()

            return executed

        # ensure connection is closed
        finally:
            cnxn.close()


class SqlServerExecuteMany(Task):
    """
    Task for executing many queries against a SQL Server database.

    Args:
        - db_name (str): name of SQL Server database
        - user (str): user name used to authenticate
        - host (str): database host address
        - port (int, optional): port used to connect to SQL Server database, defaults to 1433 if
            not provided
        - driver (str, optional): driver used to communicate with SQL Server database
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
        port: int = 1433,
        driver: str = "ODBC Driver 17 for SQL Server",
        query: str = None,
        data: tuple = None,
        commit: bool = False,
        **kwargs
    ):
        self.db_name = db_name
        self.user = user
        self.host = host
        self.port = port
        self.driver = driver
        self.query = query
        self.data = data
        self.commit = commit
        super().__init__(**kwargs)

    @defaults_from_attrs("query", "data", "commit")
    def run(
        self,
        query: str = None,
        data: list = None,
        commit: bool = False,
        password: str = None,
        fast_executemany=False,
    ):
        """
        Task run method. Executes many queries against SQL Server database.

        Args:
            - query (str, optional): query to execute against database
            - data (List[tuple], optional): list of values to use in query, must be specified using
                placeholder
            - commit (bool, optional): set to True to commit transaction, defaults to false
            - password (str): password used to authenticate; should be provided from a `Secret` task
            - fast_executemany (bool, optional): sends all params to the DB server in one bundle with
                the SQL statement. DB executes the SQL against all the params as one DB transaction

        Returns:
            - None

        Raises:
            - ValueError: if query parameter is None or a blank string
            - DatabaseError: if exception occurs when executing the query
        """
        if not query:
            raise ValueError("A query string must be provided")

        if not data:
            raise ValueError("A data list must be provided")

        # connect to database
        cnxn = pyodbc.connect(
            driver=self.driver,
            host=self.host,
            database=self.db_name,
            port=self.port,
            user=self.user,
            password=password,
        )

        # try to execute query
        # context manager automatically rolls back failed transactions
        try:
            with cnxn.cursor() as cursor:

                if fast_executemany:
                    cursor.fast_executemany = True

                executed = cursor.executemany(query, data)

                if commit:
                    cnxn.commit()
                else:
                    cnxn.rollback()

            return executed

        # ensure connection is closed
        finally:
            cnxn.close()


class SqlServerFetch(Task):
    """
    Task for fetching results of query from SQL Server database.

    Args:
        - db_name (str): name of SQL Server database
        - user (str): user name used to authenticate
        - host (str): database host address
        - port (int, optional): port used to connect to SQL Server database, defaults to 5432 if
            not provided
        - driver (str, optional): driver used to communicate with SQL Server database
        - fetch (str, optional): one of "one" "many" or "all", used to determine how many
                results to fetch from executed query
        - fetch_count (int, optional): if fetch = 'many', determines the number of results
                to fetch, defaults to 10
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
        port: int = 1433,
        driver: str = "ODBC Driver 17 for SQL Server",
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
        self.driver = driver
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
        Task run method. Executes a query against SQL Server database and fetches results.

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

        # connect to database
        cnxn = pyodbc.connect(
            driver=self.driver,
            host=self.host,
            database=self.db_name,
            port=self.port,
            user=self.user,
            password=password,
        )
        # try to execute query
        # context manager automatically rolls back failed transactions
        try:
            with cnxn.cursor() as crsr:
                if data:
                    crsr.execute(query, data)
                else:
                    crsr.execute(query)

                # fetch results
                if fetch == "all":
                    records = crsr.fetchall()
                elif fetch == "many":
                    records = crsr.fetchmany(fetch_count)
                else:
                    records = crsr.fetchone()

                if commit:
                    cnxn.commit()

            return records

        # ensure connection is closed
        finally:
            cnxn.close()

from pathlib import Path
from typing import Iterable, Union
import warnings
import pyexasol

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class ExasolExecute(Task):
    """
    Task for executing a query against a Exasol database.

    Args:
        - dsn (str, optional): dsn string of the database (server:port)
        - user (str, optional, DEPRECATED): user name used to authenticate. Deprecated,
            should be passed at runtime instead.
        - password (str, optional, DEPRECATED): password used to authenticate. Deprecated,
            should be passed at runtime instead.
        - query (str, optional): query to execute against database
        - query_params (dict, optional): Values for SQL query placeholders
        - autocommit (bool, optional): turn autocommit on or off (default: False)
        - commit (bool, optional): set to True to commit transaction, defaults to True
            (only necessary if autocommit = False)
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        dsn: str = "",
        user: str = "",
        password: str = "",
        query: str = None,
        query_params: dict = None,
        autocommit: bool = False,
        commit: bool = True,
        **kwargs,
    ):
        if user or password:
            warnings.warn(
                "Passing `user` or `password` to the `ExasolExecute` constructor "
                "is deprecated. These should be passed as runtime arguments instead."
            )

        self.user = user
        self.password = password

        self.dsn = dsn
        self.query = query
        self.query_params = query_params
        self.autocommit = autocommit
        self.commit = commit
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "dsn", "user", "password", "query", "query_params", "autocommit", "commit"
    )
    def run(
        self,
        user: str,
        password: str,
        dsn: str = "",
        query: str = None,
        query_params: dict = None,
        autocommit: bool = False,
        commit: bool = True,
        **kwargs,
    ):
        """
        Task run method. Executes a query against Exasol database.

        Args:
            - user (str): user name used to authenticate
            - password (str): password used to authenticate; should be provided from a `Secret` task
            - dsn (str, optional): dsn string of the database (server:port)
            - query (str, optional): query to execute against database
            - query_params (dict, optional): Values for SQL query placeholders
            - autocommit (bool, optional): turn autocommit on or off (default: False)
            - commit (bool, optional): set to True to commit transaction, defaults to True
                (only necessary if autocommit = False)
            - **kwargs (dict, optional): additional connection parameter (connection_timeout...)

        Returns:
            - ExaStatement object

        Raises:
            - ValueError: if dsn string is not provided
            - ValueError: if query parameter is None or a blank string
            - Exa*Error: multiple exceptions raised from the underlying pyexasol package
                (e.g. ExaQueryError, ExaAuthError..)
        """
        if not dsn:
            raise ValueError("A dsn string must be provided.")
        if not query:
            raise ValueError("A query string must be provided.")

        con = pyexasol.connect(
            dsn=dsn,
            user=user,
            password=password,
            autocommit=autocommit,
            **kwargs,
        )

        # try to execute query
        # context manager automatically rolls back failed transactions
        with con as db:
            result = db.execute(query, query_params)
            if not autocommit:
                if commit:
                    con.commit()
                else:
                    con.rollback()

            return result


class ExasolFetch(Task):
    """
    Task for fetching results of query from Exasol database.

    Args:
        - dsn (str, optional): dsn string of the database (server:port)
        - user (str, optional, DEPRECATED): user name used to authenticate. Deprecated,
            should be passed at runtime instead.
        - password (str, optional, DEPRECATED): password used to authenticate. Deprecated,
            should be passed at runtime instead.
        - fetch (str, optional): one of "one" "many" "val" or "all", used to determine how many
            results to fetch from executed query
        - fetch_size (int, optional): if fetch = 'many', determines the number of results to
            fetch, defaults to 10
        - query (str, optional): query to execute against database
        - query_params (dict, optional): Values for SQL query placeholders
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        dsn: str = "",
        user: str = "",
        password: str = "",
        fetch: str = "one",
        fetch_size: int = 10,
        query: str = None,
        query_params: dict = None,
        **kwargs,
    ):
        if user or password:
            warnings.warn(
                "Passing `user` or `password` to the `ExasolFetch` constructor "
                "is deprecated. These should be passed as runtime arguments instead."
            )

        self.user = user
        self.password = password

        self.dsn = dsn
        self.fetch = fetch
        self.fetch_size = fetch_size
        self.query = query
        self.query_params = query_params
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "dsn", "user", "password", "fetch", "fetch_size", "query", "query_params"
    )
    def run(
        self,
        user: str,
        password: str,
        dsn: str = "",
        fetch: str = "one",
        fetch_size: int = 10,
        query: str = None,
        query_params: dict = None,
        **kwargs,
    ):
        """
        Task run method. Executes a query against Exasol database and fetches results.

        Args:
            - user (str): user name used to authenticate
            - password (str): password used to authenticate; should be provided from a `Secret` task
            - dsn (str, optional): dsn string of the database (server:port)
            - fetch (str, optional): one of "one" "many" "val" or "all", used to determine how many
                results to fetch from executed query
            - fetch_size (int, optional): if fetch = 'many', determines the number of results
                to fetch, defaults to 10
            - query (str, optional): query to execute against database
            - query_params (dict, optional): Values for SQL query placeholders
            - **kwargs (dict, optional): additional connection parameter
                (autocommit, connection_timeout...)

        Returns:
            - records (None, str, tuple, list of tuples, dict, or list of dicts):
                records from provided query

        Raises:
            - ValueError: if dsn string is not provided
            - ValueError: if query parameter is None or a blank string
            - Exa*Error: multiple exceptions raised from the underlying pyexasol package
                (e.g. ExaQueryError, ExaAuthError..)
        """
        if not dsn:
            raise ValueError("A dsn string must be provided.")
        if not query:
            raise ValueError("A query string must be provided.")

        if fetch not in {"one", "many", "val", "all"}:
            raise ValueError(
                "The 'fetch' parameter must be one of the following - ('one', 'many', 'val', 'all')."
            )
        con = pyexasol.connect(
            dsn=dsn,
            user=user,
            password=password,
            **kwargs,
        )
        # try to execute query
        # context manager automatically rolls back failed transactions
        with con as db:
            query = db.execute(query, query_params)
            if fetch == "all":
                return query.fetchall()
            elif fetch == "many":
                return query.fetchmany(fetch_size)
            elif fetch == "val":
                return query.fetchval()
            else:
                return query.fetchone()


class ExasolImportFromIterable(Task):
    """
    Task for importing a iterable with data into the Exasol database.

    Args:
        - dsn (str, optional): dsn string of the database (server:port)
        - user (str, optional, DEPRECATED): user name used to authenticate. Deprecated,
            should be passed at runtime instead.
        - password (str, optional, DEPRECATED): password used to authenticate. Deprecated,
            should be passed at runtime instead.
        - target_schema (str, optional): target schema for importing data
        - target_table (str, optional): target table for importing data
        - data (Iterable, optional): an iterable which holds the import data
        - import_params (dict, optional): custom parameters for IMPORT query
        - autocommit (bool, optional): turn autocommit on or off (default: False)
        - commit (bool, optional): set to True to commit transaction, defaults to false
            (only necessary if autocommit = False)
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        dsn: str = "",
        user: str = "",
        password: str = "",
        target_schema: str = None,
        target_table: str = None,
        data: Iterable = None,
        import_params: dict = None,
        autocommit: bool = False,
        commit: bool = True,
        **kwargs,
    ):
        if user or password:
            warnings.warn(
                "Passing `user` or `password` to the `ExasolImportFromIterable` constructor "
                "is deprecated. These should be passed as runtime arguments instead."
            )

        self.user = user
        self.password = password

        self.dsn = dsn
        self.target_schema = target_schema
        self.target_table = target_table
        self.data = data
        self.import_params = import_params
        self.autocommit = autocommit
        self.commit = commit
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "dsn",
        "user",
        "password",
        "target_schema",
        "target_table",
        "data",
        "import_params",
        "autocommit",
        "commit",
    )
    def run(
        self,
        user: str,
        password: str,
        dsn: str = "",
        target_schema: str = None,
        target_table: str = None,
        data: Iterable = None,
        import_params: dict = None,
        autocommit: bool = False,
        commit: bool = True,
        **kwargs,
    ):
        """
        Task run method. Executes a query against Postgres database.

        Args:
            - user (str): user name used to authenticate
            - password (str): password used to authenticate; should be provided from a `Secret` task
            - dsn (str, optional): dsn string of the database (server:port)
            - target_schema (str, optional): target schema for importing data
            - target_table (str, optional): target table for importing data
            - data (Iterable, optional): an iterable which holds the import data
            - import_params (dict, optional): custom parameters for IMPORT query
            - autocommit (bool, optional): turn autocommit on or off (default: False)
            - commit (bool, optional): set to True to commit transaction, defaults to false
                (only necessary if autocommit = False)
            - **kwargs (dict, optional): additional connection parameter (connection_timeout...)

        Returns:
            - Nothing

        Raises:
            - ValueError: if dsn string is not provided
            - ValueError: if `data` is not provided or is empty
            - ValueError: if `target_table` is not provided
            - Exa*Error: multiple exceptions raised from the underlying pyexasol package
                (e.g. ExaQueryError, ExaAuthError..)
        """
        if not dsn:
            raise ValueError("A dsn string must be provided.")
        if not data or len(data) == 0:
            raise ValueError("Import Data must be provided.")
        if not target_table:
            raise ValueError("Target table must be provided.")

        if not target_schema:
            target = target_table
        else:
            target = (target_schema, target_table)

        con = pyexasol.connect(
            dsn=dsn,
            user=user,
            password=password,
            autocommit=autocommit,
            **kwargs,
        )

        # try to execute query
        # context manager automatically rolls back failed transactions
        with con as db:
            db.import_from_iterable(data, target, import_params)
            if not autocommit:
                if commit:
                    con.commit()
                else:
                    con.rollback()

        return


class ExasolExportToFile(Task):
    """
    Task for exporting data of an Exasol database into a single csv.

    Args:
        - dsn (str, optional): dsn string of the database (server:port)
        - user (str, optional, DEPRECATED): user name used to authenticate. Deprecated,
            should be passed at runtime instead.
        - password (str, optional, DEPRECATED): password used to authenticate. Deprecated,
            should be passed at runtime instead.
        - destination ([str, Path], optional): Path to file or file-like object
        - query_or_table (str, optional): SQL query or table for export
            could be:
                1. SELECT * FROM S.T
                2. tablename
                3. (schemaname, tablename)
        - query_params (dict, optional): Values for SQL query placeholders
        - export_params (dict, optional): custom parameters for EXPORT query
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        dsn: str = "",
        user: str = "",
        password: str = "",
        destination: Union[str, Path] = None,
        query_or_table: Union[str, tuple] = None,
        query_params: dict = None,
        export_params: dict = None,
        **kwargs,
    ):
        if user or password:
            warnings.warn(
                "Passing `user` or `password` to the `ExasolExportToFile` constructor "
                "is deprecated. These should be passed as runtime arguments instead."
            )

        self.user = user
        self.password = password

        self.dsn = dsn
        self.destination = destination
        self.query_or_table = query_or_table
        self.query_params = query_params
        self.export_params = export_params
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "dsn",
        "user",
        "password",
        "destination",
        "query_or_table",
        "query_params",
        "export_params",
    )
    def run(
        self,
        user: str,
        password: str,
        dsn: str = "",
        destination: Union[str, Path] = None,
        query_or_table: Union[str, tuple] = None,
        query_params: dict = None,
        export_params: dict = None,
        **kwargs,
    ):
        """
        Task run method. Executes a query against Postgres database.

        Args:
            - user (str): user name used to authenticate
            - password (str): password used to authenticate; should be provided from a `Secret` task
            - dsn (str, optional): dsn string of the database (server:port)
            - destination ([str, Path], optional): Path to file or file-like object
            - query_or_table (str, optional): SQL query or table for export
                could be:
                    1. SELECT * FROM S.T
                    2. tablename
                    3. (schemaname, tablename)
            - query_params (dict, optional): Values for SQL query placeholders
            - export_params (dict, optional): custom parameters for EXPORT query
            - **kwargs (dict, optional): additional connection parameter (connection_timeout...)

        Returns:
            - Nothing

        Raises:
            - ValueError: if dsn string is not provided
            - ValueError: if destination is not provided
            - ValueError: if no query or table are provided
            - Exa*Error: multiple exceptions raised from the underlying pyexasol package
                (e.g. ExaQueryError, ExaAuthError..)
        """
        if not dsn:
            raise ValueError("A dsn string must be provided.")
        if not destination:
            raise ValueError("A destination must be provided.")
        if not query_or_table:
            raise ValueError("A query or a table must be provided.")

        con = pyexasol.connect(
            dsn=dsn,
            user=user,
            password=password,
            **kwargs,
        )

        # try to execute query
        # context manager automatically rolls back failed transactions
        with con as db:
            db.export_to_file(
                destination,
                query_or_table,
                query_params,
                export_params,
            )

        return

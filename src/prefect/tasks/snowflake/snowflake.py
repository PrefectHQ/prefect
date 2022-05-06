from pathlib import Path
from typing import Optional

import snowflake.connector as sf
from snowflake.connector.cursor import SnowflakeCursor

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class SnowflakeQuery(Task):
    """
    Task for executing a query against a Snowflake database.

    Args:
        - account (str): Snowflake account name, see Snowflake connector
             package documentation for details.
        - user (str): User name used to authenticate.
        - password (str, optional): Password used to authenticate.
            `password` or `private_key` must be present, unless `authenticator` is provided.
        - private_key (bytes, optional): PEM to authenticate.
            `password` or `private_key` must be present, unless `authenticator` is provided.
        - database (str, optional): Name of the default database to use.
        - schema (int, optional): Name of the default schema to use.
        - role (str, optional): Name of the default role to use.
        - warehouse (str, optional): Name of the default warehouse to use.
        - query (str, optional): Query to execute against database.
        - data (tuple, optional): Values to use in query, must be specified using placeholder
            in query string.
        - autocommit (bool, optional): Set to True to autocommit, defaults to None, which
            takes Snowflake AUTOCOMMIT parameter.
        - cursor_type (SnowflakeCursor, optional): Specify the type of database
            cursor to use for the query, defaults to SnowflakeCursor.
        - authenticator (str, optional): Type of authenticator to use for initiating
            connection (oauth, externalbrowser...), refer to Snowflake
            [Python Connector API](https://docs.snowflake.com/en/user-guide/python-connector-api.html#connect)
            documentation for details. Note that `externalbrowser` will only work in an environment
            where a browser is available, default to None.
        - token (str, optional): OAuth or JWT Token to provide when authenticator
            is set to oauth, default to None.
        - **kwargs (dict, optional): Additional keyword arguments to pass to the
            Task constructor.
    """  # noqa

    def __init__(
        self,
        account: str = None,
        user: str = None,
        password: Optional[str] = None,
        private_key: Optional[bytes] = None,
        database: Optional[str] = None,
        schema: Optional[str] = None,
        role: Optional[str] = None,
        warehouse: Optional[str] = None,
        query: str = None,
        data: Optional[tuple] = None,
        autocommit: Optional[bool] = None,
        cursor_type: SnowflakeCursor = SnowflakeCursor,
        authenticator: Optional[str] = None,
        token: Optional[str] = None,
        **kwargs,
    ):
        self.account = account
        self.user = user
        self.password = password
        self.private_key = private_key
        self.database = database
        self.schema = schema
        self.role = role
        self.warehouse = warehouse
        self.query = query
        self.data = data
        self.autocommit = autocommit
        self.cursor_type = cursor_type
        self.authenticator = authenticator
        self.token = token
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "account",
        "user",
        "password",
        "private_key",
        "database",
        "schema",
        "role",
        "warehouse",
        "query",
        "data",
        "autocommit",
        "cursor_type",
        "authenticator",
        "token",
    )
    def run(
        self,
        account: str = None,
        user: str = None,
        password: Optional[str] = None,
        private_key: Optional[bytes] = None,
        database: Optional[str] = None,
        schema: Optional[str] = None,
        role: Optional[str] = None,
        warehouse: Optional[str] = None,
        query: str = None,
        data: Optional[tuple] = None,
        autocommit: Optional[bool] = None,
        cursor_type: SnowflakeCursor = SnowflakeCursor,
        authenticator: Optional[str] = None,
        token: Optional[str] = None,
    ):
        """
        Task run method. Executes a query against Snowflake database.

        Args:
            - account (str, optional): Snowflake account name, see Snowflake connector
                package documentation for details.
            - user (str, optional): User name used to authenticate.
            - password (str, optional): Password used to authenticate.
                `password` or `private_key` must be present, unless `authenticator` is provided
            - private_key (bytes, optional): PEM to authenticate.
                `password` or `private_key` must be present, unless `authenticator` is provided
            - database (str, optional): Name of the default database to use.
            - schema (int, optional): Name of the default schema to use.
            - role (str, optional): Name of the default role to use.
            - warehouse (str, optional): Name of the default warehouse to use.
            - query (str, optional): Query to execute against database.
            - data (tuple, optional): Values to use in query, must be specified using placeholder
                in query string.
            - autocommit (bool, optional): Set to True to autocommit, defaults to None, which
                takes Snowflake AUTOCOMMIT parameter.
            - cursor_type (SnowflakeCursor, optional): Specify the type of database
                cursor to use for the query, defaults to SnowflakeCursor.
            - authenticator (str, optional): Type of authenticator to use for initiating
                connection (oauth, externalbrowser...), refer to Snowflake
                [Python Connector API](https://docs.snowflake.com/en/user-guide/python-connector-api.html#connect)
                documentation for details. Note that `externalbrowser` will only work in an environment
                where a browser is available, default to None.
            - token (str, optional): OAuth or JWT Token to provide when authenticator
                is set to oauth, default to None.

        Returns:
            - List[List]: Output of cursor.fetchall().

        Raises:
            - ValueError: If a required parameter is not supplied.
            - DatabaseError: If exception occurs when executing the query.
        """  # noqa
        auth_kwargs = (password, private_key, authenticator, token)
        if not account:
            raise ValueError("An account must be provided")
        if all(auth_kwarg is None for auth_kwarg in auth_kwargs):
            raise ValueError(
                f"An authentication keyword must be provided: {auth_kwargs}"
            )
        if not query:
            raise ValueError("A query string must be provided")

        # build the connection parameter dictionary
        # we will remove `None` values next
        connect_params = {
            "account": account,
            "user": user,
            "password": password,
            "private_key": private_key,
            "database": database,
            "schema": schema,
            "role": role,
            "warehouse": warehouse,
            "autocommit": autocommit,
            "authenticator": authenticator,
            "token": token,
            # required to track task's usage in the Snowflake Partner Network Portal
            "application": f"Prefect_{self.__class__.__name__}",
        }

        # filter out unset values
        connect_params = {
            param: value for param, value in connect_params.items() if value is not None
        }

        # connect to database, open cursor
        conn = sf.connect(**connect_params)
        # context manager automatically rolls back failed transactions and closes
        with conn:
            with conn.cursor(cursor_type) as cursor:
                executed = cursor.execute(query, params=data).fetchall()
        return executed


class SnowflakeQueriesFromFile(Task):
    """
    Task for executing queries loaded from a file against a Snowflake database.
    Return a list containings the results of the queries.

    Note that using execute_string() is vulnerable to SQL injection.

    Args:
        - account (str, optional): Snowflake account name, see Snowflake connector
             package documentation for details.
        - user (str, optional): User name used to authenticate.
        - password (str, optional): Password used to authenticate.
            `password` or `private_key` must be present, unless `authenticator` is provided.
        - private_key (bytes, optional): PEM to authenticate.
            `password` or `private_key` must be present, unless `authenticator` is provided.
        - database (str, optional): Name of the default database to use.
        - schema (int, optional): Name of the default schema to use.
        - role (str, optional): Name of the default role to use.
        - warehouse (str, optional): Name of the default warehouse to use.
        - file_path (str, optional): File path to load query from.
        - autocommit (bool, optional): Set to True to autocommit, defaults to None, which
            takes Snowflake AUTOCOMMIT parameter.
        - cursor_type (SnowflakeCursor, optional): Specify the type of database
            cursor to use for the query, defaults to SnowflakeCursor.
        - authenticator (str, optional): Type of authenticator to use for initiating
            connection (oauth, externalbrowser...), refer to Snowflake
            [Python Connector API](https://docs.snowflake.com/en/user-guide/python-connector-api.html#connect)
            documentation for details. Note that `externalbrowser` will only work in an environment
            where a browser is available, default to None.
        - token (str, optional): OAuth or JWT Token to provide when authenticator
            is set to oauth, default to None.
        - **kwargs (dict, optional): Additional keyword arguments to pass to the
            Task constructor.
    """  # noqa

    def __init__(
        self,
        account: str = None,
        user: str = None,
        password: Optional[str] = None,
        private_key: Optional[bytes] = None,
        database: Optional[str] = None,
        schema: Optional[str] = None,
        role: Optional[str] = None,
        warehouse: Optional[str] = None,
        file_path: str = None,
        autocommit: Optional[bool] = None,
        cursor_type: SnowflakeCursor = SnowflakeCursor,
        authenticator: Optional[str] = None,
        token: Optional[str] = None,
        **kwargs,
    ):
        self.account = account
        self.user = user
        self.password = password
        self.private_key = private_key
        self.database = database
        self.schema = schema
        self.role = role
        self.warehouse = warehouse
        self.file_path = file_path
        self.autocommit = autocommit
        self.cursor_type = cursor_type
        self.authenticator = authenticator
        self.token = token
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "account",
        "user",
        "password",
        "private_key",
        "database",
        "schema",
        "role",
        "warehouse",
        "file_path",
        "autocommit",
        "cursor_type",
        "authenticator",
        "token",
    )
    def run(
        self,
        account: str = None,
        user: str = None,
        password: Optional[str] = None,
        private_key: Optional[bytes] = None,
        database: Optional[str] = None,
        schema: Optional[str] = None,
        role: Optional[str] = None,
        warehouse: Optional[str] = None,
        file_path: str = None,
        autocommit: Optional[bool] = None,
        cursor_type: SnowflakeCursor = SnowflakeCursor,
        authenticator: Optional[str] = None,
        token: Optional[str] = None,
    ):
        """
        Task run method. Executes a query against Snowflake database.

        Args:
            - account (str): Snowflake account name, see Snowflake connector
                package documentation for details.
            - user (str): User name used to authenticate.
            - password (str, optional): Password used to authenticate.
                `password` or `private_key` must be present, unless `authenticator` is provided.
            - private_key (bytes, optional): PEM to authenticate.
                `password` or `private_key` must be present, unless `authenticator` is provided.
            - database (str, optional): Name of the default database to use.
            - schema (int, optional): Name of the default schema to use.
            - role (str, optional): Name of the default role to use.
            - warehouse (str, optional): Name of the default warehouse to use.
            - file_path (str, optional): File path to load query from.
            - autocommit (bool, optional): Set to True to autocommit, defaults to None, which
                takes Snowflake AUTOCOMMIT parameter.
            - cursor_type (SnowflakeCursor, optional): Specify the type of database
                cursor to use for the query, defaults to SnowflakeCursor.
            - authenticator (str, optional): Type of authenticator to use for initiating
                connection (oauth, externalbrowser...), refer to Snowflake
                [Python Connector API](https://docs.snowflake.com/en/user-guide/python-connector-api.html#connect)
                documentation for details. Note that `externalbrowser` will only work in an environment
                where a browser is available, default to None.
            - token (str, optional): OAuth or JWT Token to provide when authenticator
                is set to oauth, default to None.

        Returns:
            - List[List]: Containing the results of the different queries executed.

        Raises:
            - ValueError: If query parameter is None or a blank string.
            - DatabaseError: If exception occurs when executing the query.
            - FileNotFoundError: If File does not exist.
        """  # noqa
        auth_kwargs = (password, private_key, authenticator, token)
        if account is None:
            raise ValueError("An account must be provided")
        if user is None:
            raise ValueError("A user must be provided")
        if all(auth_kwarg is None for auth_kwarg in auth_kwargs):
            raise ValueError(
                f"An authentication keyword must be provided: {auth_kwargs}"
            )
        if file_path is None:
            raise ValueError("A file path must be provided")

        # build the connection parameter dictionary
        # we will remove `None` values next
        connect_params = {
            "account": account,
            "user": user,
            "password": password,
            "private_key": private_key,
            "database": database,
            "schema": schema,
            "role": role,
            "warehouse": warehouse,
            "autocommit": autocommit,
            "authenticator": authenticator,
            "token": token,
            # required to track task's usage in the Snowflake Partner Network Portal
            "application": f"Prefect_{self.__class__.__name__}",
        }

        # filter out unset values
        connect_params = {
            param: value for param, value in connect_params.items() if value is not None
        }

        # connect to database, open cursor
        conn = sf.connect(**connect_params)

        # try to execute query
        # context manager automatically rolls back failed transactions
        # load query from file
        query = Path(file_path).read_text()
        with conn:
            cursor_list = conn.execute_string(query, cursor_class=cursor_type)
            result = [cursor.fetchall() for cursor in cursor_list]
        return result

from pathlib import Path
import snowflake.connector as sf
from snowflake.connector.cursor import SnowflakeCursor

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class SnowflakeQuery(Task):
    """
    Task for executing a query against a Snowflake database.

    Args:
        - account (str): snowflake account name, see snowflake connector
             package documentation for details
        - user (str): user name used to authenticate
        - password (str, optional): password used to authenticate.
            password or private_key must be present
        - private_key (bytes, optional): pem to authenticate.
            password or private_key must be present
        - database (str, optional): name of the default database to use
        - schema (int, optional): name of the default schema to use
        - role (str, optional): name of the default role to use
        - warehouse (str, optional): name of the default warehouse to use
        - query (str, optional): query to execute against database
        - data (tuple, optional): values to use in query, must be specified using placeholder
            in query string
        - autocommit (bool, optional): set to True to autocommit, defaults to None, which
            takes snowflake AUTOCOMMIT parameter
        - cursor_type (SnowflakeCursor, optional): specify the type of database
            cursor to use for the query, defaults to SnowflakeCursor
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        account: str = None,
        user: str = None,
        password: str = None,
        private_key: bytes = None,
        database: str = None,
        schema: str = None,
        role: str = None,
        warehouse: str = None,
        query: str = None,
        data: tuple = None,
        autocommit: bool = None,
        cursor_type: SnowflakeCursor = SnowflakeCursor,
        **kwargs
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
    )
    def run(
        self,
        account: str = None,
        user: str = None,
        password: str = None,
        private_key: bytes = None,
        database: str = None,
        schema: str = None,
        role: str = None,
        warehouse: str = None,
        query: str = None,
        data: tuple = None,
        autocommit: bool = None,
        cursor_type: SnowflakeCursor = SnowflakeCursor,
    ):
        """
        Task run method. Executes a query against snowflake database.

        Args:
            - account (str, optional): snowflake account name, see snowflake connector
                package documentation for details
            - user (str, optional): user name used to authenticate
            - password (str, optional): password used to authenticate.
                password or private_lkey must be present
            - private_key (bytes, optional): pem to authenticate.
                password or private_key must be present
            - database (str, optional): name of the default database to use
            - schema (int, optional): name of the default schema to use
            - role (str, optional): name of the default role to use
            - warehouse (str, optional): name of the default warehouse to use
            - query (str, optional): query to execute against database
            - data (tuple, optional): values to use in query, must be specified using placeholder
                in query string
            - autocommit (bool, optional): set to True to autocommit, defaults to None, which
                takes snowflake AUTOCOMMIT parameter
            - cursor_type (SnowflakeCursor, optional): specify the type of database
                cursor to use for the query, defaults to SnowflakeCursor

        Returns:
            - List[List]: output of cursor.fetchall()

        Raises:
            - ValueError: if a required parameter is not supplied
            - DatabaseError: if exception occurs when executing the query
        """
        if not account:
            raise ValueError("An account must be provided")
        if not user:
            raise ValueError("A user must be provided")
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
        }

        # filter out unset values
        connect_params = {
            param: value
            for (param, value) in connect_params.items()
            if value is not None
        }

        # connect to database, open cursor
        conn = sf.connect(**connect_params)
        # try to execute query
        # context manager automatically rolls back failed transactions
        try:
            with conn:
                with conn.cursor(cursor_type) as cursor:
                    executed = cursor.execute(query, params=data).fetchall()
            conn.close()
            return executed

        # pass through error, and ensure connection is closed
        except Exception as error:
            conn.close()
            raise error


class SnowflakeQueriesFromFile(Task):
    """
    Task for executing queries loaded from a file against a Snowflake database.
    Return a list containings the results of the queries.

    Note that using execute_string() is vulnerable to SQL injection.

    Args:
        - account (str, optional): snowflake account name, see snowflake connector
             package documentation for details
        - user (str, optional): user name used to authenticate
        - password (str, optional): password used to authenticate.
            password or private_lkey must be present
        - private_key (bytes, optional): pem to authenticate.
            password or private_key must be present
        - database (str, optional): name of the default database to use
        - schema (int, optional): name of the default schema to use
        - role (str, optional): name of the default role to use
        - warehouse (str, optional): name of the default warehouse to use
        - file_path (str, optional): file path to load query from
        - autocommit (bool, optional): set to True to autocommit, defaults to None, which
            takes snowflake AUTOCOMMIT parameter
        - cursor_type (SnowflakeCursor, optional): specify the type of database
            cursor to use for the query, defaults to SnowflakeCursor
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        account: str = None,
        user: str = None,
        password: str = None,
        private_key: bytes = None,
        database: str = None,
        schema: str = None,
        role: str = None,
        warehouse: str = None,
        file_path: str = None,
        autocommit: bool = None,
        cursor_type: SnowflakeCursor = SnowflakeCursor,
        **kwargs
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
    )
    def run(
        self,
        account: str,
        user: str,
        password: str = None,
        private_key: bytes = None,
        database: str = None,
        schema: str = None,
        role: str = None,
        warehouse: str = None,
        file_path: str = None,
        autocommit: bool = None,
        cursor_type: SnowflakeCursor = SnowflakeCursor,
    ):
        """
        Task run method. Executes a query against snowflake database.

        Args:
            - account (str): snowflake account name, see snowflake connector
                package documentation for details
            - user (str): user name used to authenticate
            - password (str, optional): password used to authenticate.
                password or private_lkey must be present
            - private_key (bytes, optional): pem to authenticate.
                password or private_key must be present
            - database (str, optional): name of the default database to use
            - schema (int, optional): name of the default schema to use
            - role (str, optional): name of the default role to use
            - warehouse (str, optional): name of the default warehouse to use
            - file_path (str, optional): file path to load query from
            - autocommit (bool, optional): set to True to autocommit, defaults to None, which
                takes snowflake AUTOCOMMIT parameter
            - cursor_type (SnowflakeCursor, optional): specify the type of database
                cursor to use for the query, defaults to SnowflakeCursor

        Returns:
            - List[List]: containing the results of the different queries executed

        Raises:
            - ValueError: if query parameter is None or a blank string
            - DatabaseError: if exception occurs when executing the query
            - FileNotFoundError: if File does not exist
        """
        if account is None:
            raise ValueError("An account must be provided")
        if user is None:
            raise ValueError("A user must be provided")
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
        }

        # filter out unset values
        connect_params = {
            param: value
            for (param, value) in connect_params.items()
            if value is not None
        }

        # connect to database, open cursor
        conn = sf.connect(**connect_params)

        # try to execute query
        # context manager automatically rolls back failed transactions
        try:
            # load query from file
            query = Path(file_path).read_text()

            with conn:
                result = []
                cursor_list = conn.execute_string(query, cursor_class=cursor_type)

                for cursor in cursor_list:
                    result.append(cursor.fetchall())
                    # return fetch for each cursor
            return result

        # ensure connection is closed
        finally:
            conn.close()

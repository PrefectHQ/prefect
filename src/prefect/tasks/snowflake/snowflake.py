from pathlib import Path
import snowflake.connector as sf

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
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "account",
        "user",
        "password",
        "private_key",
        "database",
        "schema",
        "role",
        "query",
        "data",
        "autocommit",
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

        Returns:
            - List[List]: output of cursor.fetchall()

        Raises:
            - ValueError: if query parameter is None or a blank string
            - DatabaseError: if exception occurs when executing the query
        """
        if not query:
            raise ValueError("A query string must be provided")

        # build the connection parameter dictionary
        # we will remove `None` values next
        connect_params = {
            "account": (account or self.account),
            "user": (user or self.user),
            "password": (password or self.password),
            "private_key": (private_key or self.private_key),
            "database": (database or self.database),
            "schema": (schema or self.schema),
            "role": (role or self.role),
            "warehouse": (warehouse or self.warehouse),
            "autocommit": (autocommit or self.autocommit),
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
                with conn.cursor() as cursor:
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
        **kwargs
    ):
        self.account = account
        self.user = user
        self.password = password
        self.database = database
        self.schema = schema
        self.role = role
        self.warehouse = warehouse
        self.file_path = file_path
        self.autocommit = autocommit
        self.private_key = private_key
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "account",
        "user",
        "password",
        "private_key",
        "database",
        "schema",
        "role",
        "file_path",
        "autocommit",
    )
    @defaults_from_attrs("file_path", "autocommit")
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

        Returns:
            - List[List]: containing the results of the different queries executed

        Raises:
            - ValueError: if query parameter is None or a blank string
            - DatabaseError: if exception occurs when executing the query
            - FileNotFoundError: if File does not exist
        """
        if not file_path:
            raise ValueError("A file path must be provided")

        # build the connection parameter dictionary
        # we will remove `None` values next
        connect_params = {
            "account": (account or self.account),
            "user": (user or self.user),
            "password": (password or self.password),
            "private_key": (private_key or self.private_key),
            "database": (database or self.database),
            "schema": (schema or self.schema),
            "role": (role or self.role),
            "warehouse": (warehouse or self.warehouse),
            "autocommit": (autocommit or self.autocommit),
        }

        # filter out unset values
        connect_params = {
            param: value
            for (param, value) in connect_params.items()
            if value is not None
        }

        # connect to database, open cursor
        conn = sf.connect(**connect_params)

        # load query from file
        query = Path(file_path).read_text()

        # try to execute query
        # context manager automatically rolls back failed transactions
        try:
            with conn:
                result = []
                cursor_list = conn.execute_string(query)

                for cursor in cursor_list:
                    result.append(cursor.fetchall())
                    # return fetch for each cursor
            conn.close()
            return result

        # pass through error, and ensure connection is closed
        except Exception as error:
            conn.close()
            raise error

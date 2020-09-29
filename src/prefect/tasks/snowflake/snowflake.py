import snowflake.connector as sf

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class SnowflakeQuery(Task):
    """
    Task for executing a query against a snowflake database.

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
            is query string
        - autocommit (bool, optional): set to True to autocommit, defaults to None, which
            takes snowflake AUTOCOMMIT parameter
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        account: str,
        user: str,
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
        self.database = database
        self.schema = schema
        self.role = role
        self.warehouse = warehouse
        self.query = query
        self.data = data
        self.autocommit = autocommit
        self.private_key = private_key
        super().__init__(**kwargs)

    @defaults_from_attrs("query", "data", "autocommit")
    def run(self, query: str = None, data: tuple = None, autocommit: bool = None):
        """
        Task run method. Executes a query against snowflake database.

        Args:
            - query (str, optional): query to execute against database
            - data (tuple, optional): values to use in query, must be specified using
                placeholder is query string
            - autocommit (bool, optional): set to True to autocommit, defaults to None
                which takes the snowflake AUTOCOMMIT parameter

        Returns:
            - None

        Raises:
            - ValueError: if query parameter is None or a blank string
            - DatabaseError: if exception occurs when executing the query
        """
        if not query:
            raise ValueError("A query string must be provided")

        # build the connection parameter dictionary
        # we will remove `None` values next
        connect_params = {
            "account": self.account,
            "user": self.user,
            "password": self.password,
            "private_key": self.private_key,
            "database": self.database,
            "schema": self.schema,
            "role": self.role,
            "warehouse": self.warehouse,
            "autocommit": self.autocommit,
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
                    executed = cursor.execute(query, params=data)

            conn.close()
            return executed

        # pass through error, and ensure connection is closed
        except Exception as error:
            conn.close()
            raise error

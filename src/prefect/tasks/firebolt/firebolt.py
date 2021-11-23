from firebolt.db import Connection

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class FireboltQuery(Task):

    def __init__(
            self,
            engine_url: str = None,
            database: str = None,
            username: str = None,
            password: str = None,
            api_endpoint: str = None,
            query: str = None,
            **kwargs
    ):
        """
        Task for executing a query against a Firebolt database.

        Args:
            - engine url (str, optional): engine url of the engine to use
            - database (str): name of the database to use
            - username (str): username used to authenticate
            - password (str): password used to authenticate.
            - api_endpoint (str): default API endpoint of firebolt
            - query (str): query to execute against database
            - **kwargs (dict, optional): additional keyword arguments to pass to the Task constructor
        """

        self.engine_url = engine_url
        self.database = database
        self.username = username
        self.password = password
        self.api_endpoint = api_endpoint
        self.query = query
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "engine_url",
        "database",
        "username",
        "password",
        "api_endpoint",
        "query"
    )
    def run(
            self,
            engine_url: str = None,
            database: str = None,
            username: str = None,
            password: str = None,
            api_endpoint: str = None,
            query: str = None
    ):
        """
        Task run method. Executes a query against Firebolt database.

        Args:
            - engine url (str, optional): engine url of the engine to use
            - database (str): name of the database to use
            - username (str): username used to authenticate
            - password (str): password used to authenticate.
            - api_endpoint (str): default API endpoint of firebolt
            - query (str): query to execute against database

        Raises:
            - ValueError: if a required parameter is not supplied
            - DatabaseError: if exception occurs when executing the query
        """

        if not engine_url:
            raise ValueError("An engine url must be provided")
        if not database:
            raise ValueError("A database name must be provided")
        if not username:
            raise ValueError("User name must be provided")
        if not password:
            raise ValueError("A password must be provided")
        if not api_endpoint:
            raise ValueError("An api endpoint must be provided")
        if not query:
            raise ValueError("A query string must be provided")

        # connect to database, return a connection object
        conn = Connection(engine_url, database, username, password, api_endpoint)

        # try to execute query
        try:
            with conn:
                with conn.cursor() as cursor:
                    executed = cursor.execute(query)
            conn.close()
        # pass through error, and ensure connection is closed
        except Exception as error:
            conn.close()
            raise error


class FireboltQueryGetData(Task):

    def __init__(
            self,
            engine_url: str = None,
            database: str = None,
            username: str = None,
            password: str = None,
            api_endpoint: str = None,
            query: str = None,
            **kwargs
    ):
        """
        Task for executing a query against a Firebolt database to retrieve data.

        Args:
            - engine url (str, optional): engine url of the engine to use
            - database (str): name of the database to use
            - username (str): username used to authenticate
            - password (str): password used to authenticate.
            - api_endpoint (str): default API endpoint of firebolt
            - query (str): query to execute against database
            - **kwargs (dict, optional): additional keyword arguments to pass to the Task constructor
        """

        self.engine_url = engine_url
        self.database = database
        self.username = username
        self.password = password
        self.api_endpoint = api_endpoint
        self.query = query
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "engine_url",
        "database",
        "username",
        "password",
        "api_endpoint",
        "query"
    )
    def run(
            self,
            engine_url: str = None,
            database: str = None,
            username: str = None,
            password: str = None,
            api_endpoint: str = None,
            query: str = None
    ):
        """
        Task run method. Executes a query against Firebolt database to retrieve data.

        Args:
            - engine url (str, optional): engine url of the engine to use
            - database (str): name of the database to use
            - username (str): username used to authenticate
            - password (str): password used to authenticate.
            - api_endpoint (str): default API endpoint of firebolt
            - query (str): query to execute against database

        Returns:
            - List[List]: output of cursor.fetchall()

        Raises:
            - ValueError: if a required parameter is not supplied
            - DatabaseError: if exception occurs when executing the query
        """

        if not engine_url:
            raise ValueError("An engine url must be provided")
        if not database:
            raise ValueError("A database name must be provided")
        if not username:
            raise ValueError("User name must be provided")
        if not password:
            raise ValueError("A password must be provided")
        if not api_endpoint:
            raise ValueError("An api endpoint must be provided")
        if not query:
            raise ValueError("A query string must be provided")

        # connect to database, return a connection object
        conn = Connection(engine_url, database, username, password, api_endpoint)

        # try to execute query
        try:
            with conn:
                with conn.cursor() as cursor:
                    executed_count = cursor.execute(query)
                    executed_data = cursor.fetchall()
                    print("Row count: ", executed_count)
                    print("Metadata: ", executed_data)
            conn.close()

        # pass through error, and ensure connection is closed
        except Exception as error:
            conn.close()
            raise error

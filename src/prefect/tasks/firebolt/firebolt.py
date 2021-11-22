from firebolt.db import Connection

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class FireboltConnection(Task):

    def __init__(
            self,
            engine_url: str = None,
            database: str = None,
            username: str = None,
            password: str = None,
            api_endpoint: str = None,
            **kwargs
    ):
        """
        Class for creating a connection object.

        Args:
            - engine url (str, optional): engine url of the engine to use
            - database (str): name of the database to use
            - username (str): username used to authenticate
            - password (str): password used to authenticate.
            - api_endpoint (str): default API endpoint of firebolt
            - **kwargs (dict, optional): additional keyword arguments to pass to the Task constructor
        """

        self.engine_url = engine_url
        self.database = database
        self.username = username
        self.password = password
        self.api_endpoint = api_endpoint
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "engine_url",
        "database",
        "username",
        "password",
    )
    def run(
            self,
            engine_url: str = None,
            database: str = None,
            username: str = None,
            password: str = None,
            api_endpoint: str = None,
    ):
        """
        Task for establishing a connection with a Firebolt database.

        Args:
            - engine url (str, optional): engine url of the engine to use
            - database (str): name of the database to use
            - username (str): username used to authenticate
            - password (str): password used to authenticate.
            - api_endpoint (str): default API endpoint of firebolt

        Returns:
            - Connection object containing necessary details
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

        # connect to database, return a connection object
        conn = Connection(self.engine_url, self.database, self.username, self.password, self.api_endpoint)
        return conn


class FireboltQuery(Task):

    def __init__(self,
                 conn: Connection = None,
                 query: str = None,
                 **kwargs
                 ):

        """
        Class to execute a DDL/DML query against a Firebolt database
        Args:
            - conn (Connection): Connection object to create cursor to execute the query
            - query (str): query to execute against database
            - **kwargs (dict, optional): additional keyword arguments to pass to the  Task constructor
        """

        self.conn = conn
        self.query = query
        super().__init__(**kwargs)

    @defaults_from_attrs("conn", "query")
    def run(
            self,
            conn: Connection,
            query: str,
    ):
        """
        Task run method. Executes a query against firebolt database.

        Args:
            - conn (Connection): Connection object to create cursor to execute the query
            - query (str): query to execute against database

        Raises:
            - ValueError: if a required parameter is not supplied
            - DatabaseError: if exception occurs when executing the query
        """

        if not conn:
            raise ValueError("A connection object must be provided")
        if not query:
            raise ValueError("A query string must be provided")

        # try to execute query
        try:
            cursor = conn.cursor()
            executed = cursor.execute(query)
            cursor.close()

        # pass through error, and ensure connection is closed
        except Exception as error:
            conn.close()
            raise error


class FireboltQueryGetData(Task):

    def __init__(self,
                 conn: Connection = None,
                 query: str = None,
                 **kwargs
                 ):

        """
        Class to execute a query against a Firebolt database to retrieve metadata.

        Args:
            - conn (Connection): Connection object to create cursor to execute the query
            - query (str): query to execute against database
            - **kwargs (dict, optional): additional keyword arguments to pass to the Task constructor
        """

        self.conn = conn
        self.query = query
        super().__init__(**kwargs)

    @defaults_from_attrs("conn", "query")
    def run(
            self,
            conn: Connection,
            query: str,
    ):
        """
        Task run method. Executes a query against firebolt database.

        Args:
            - conn (Connection): Connection object to create cursor to execute the query
            - query (str): query to execute against database

        Returns:
            - metadata returned from the Firebolt API for the fired query.

        Raises:
            - ValueError: if a required parameter is not supplied
            - DatabaseError: if exception occurs when executing the query
        """

        if not conn:
            raise ValueError("A connection object must be provided")
        if not query:
            raise ValueError("A query string must be provided")

        # try to execute query
        try:
            cursor = conn.cursor()
            executed_count = cursor.execute(query)
            executed_data = cursor.fetchall()
            print("Row count: ", executed_count)
            print("Metadata: ", executed_data)
            cursor.close()

        # pass through error, and ensure connection is closed
        except Exception as error:
            conn.close()
            raise error

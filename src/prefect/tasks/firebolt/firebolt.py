from firebolt_db.firebolt_connector import Connection

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class FireboltConnection(Task):

    def __init__(
            self,
            user_email: str = None,
            password: str = None,
            db_name: str = None,
            engine_name: str = None,
            port: str = None,
            **kwargs
    ):
        """
            Task for establishing a connection with a Firebolt database.

            Args:
                - user email (str): user email used to authenticate
                - password (str): password used to authenticate.
                - db name (str): name of the default database to use
                - engine_name (str, optional): name of the engine to use
                - port (str): port of the database to connect
                - **kwargs (dict, optional): additional keyword arguments to pass to the
                    Task constructor
            """

        self.user_email = user_email
        self.password = password
        self.port = port
        self.db_name = db_name
        self.engine_name = engine_name
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "user_email",
        "password",
        "port",
        "db_name",
        "engine_name",
    )
    def run(
            self,
            user_email: str = None,
            password: str = None,
            db_name: str = None,
            engine_name: str = None,
            port: str = None,
    ):
        """
            Task for establishing a connection with a Firebolt database.

            Args:
                - user email (str): user email used to authenticate
                - password (str): password used to authenticate.
                - db name (str): name of the default database to use
                - engine_name (str, optional): name of the engine to use
                - port (str): port of the database to connect
                - **kwargs (dict, optional): additional keyword arguments to pass to the
                    Task constructor
            Raises:
                - ValueError: if a required parameter is not supplied
                - DatabaseError: if exception occurs when executing the query
        """
        if not user_email:
            raise ValueError("User email must be provided")
        if not password:
            raise ValueError("A password must be provided")
        if not db_name:
            raise ValueError("A database name must be provided")

        # connect to database, open cursor
        conn = Connection(self.engine_name, self.port, self.user_email, self.password, self.db_name)
        # print(conn.access_token)
        # print(conn.engine_url)
        return conn


class FireboltQuery(Task):

    def __init__(self,
                 conn: Connection = None,
                 query: str = None,
                 **kwargs
                 ):

        """
            Task for establishing a connection with a Firebolt database.

            Args:
                - conn (Connection): Connection object to create cursor to execute the query
                - query (str): query to execute against database
                - **kwargs (dict, optional): additional keyword arguments to pass to the
                            Task constructor
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
            executed = conn.cursor().execute(query)
            print(executed)
            return executed

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
            Task for establishing a connection with a Firebolt database.

            Args:
                - conn (Connection): Connection object to create cursor to execute the query
                - query (str): query to execute against database
                - **kwargs (dict, optional): additional keyword arguments to pass to the
                            Task constructor
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
            executed = conn.cursor().execute(query).fetchall()
            print(executed)
            return executed

        # pass through error, and ensure connection is closed
        except Exception as error:
            conn.close()
            raise error

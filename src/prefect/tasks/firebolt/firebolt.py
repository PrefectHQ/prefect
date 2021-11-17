from firebolt_db.firebolt_connector import Connection

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class FireboltQuery(Task):
    """
    Task for establishing a connection with a Firebolt database.

    Args:
        - user email (str): user email used to authenticate
        - password (str): password used to authenticate.
        - db name (str): name of the default database to use
        - engine_name (str, optional): name of the engine to use
        - query (str): query to execute against database
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
            self,
            user_email: str = None,
            password: str = None,
            db_name: str = None,
            query: str = None,
            engine_name: str = None,
            port: str = None,
            **kwargs
    ):
        self.user_email = user_email
        self.password = password
        self.port = port
        self.db_name = db_name
        self.engine_name = engine_name
        self.query = query
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "user_email",
        "password",
        "port",
        "db_name",
        "engine_name",
        "query",
    )
    def run(
            self,
            user_email: str = None,
            password: str = None,
            db_name: str = None,
            query: str = None,
            engine_name: str = None,
            port: str = None,
    ):
        """
        Task run method. Executes a query against firebolt database.

        Args:
            - access token (str): access token used to authenticate
            - engine url (str, optional): url of the engine to use
            - db name (str): name of the default database to use
            - query (str): query to execute against database

        Returns:
            - Row: output of cursor.fetchall()

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
        if not query:
            raise ValueError("A query string must be provided")

        # build the connection parameter dictionary
        # we will remove `None` values next
        # connect_params = {
        #     "user_email": user_email,
        #     "password": password,
        #     "db_name": db_name,
        #     "engine_name": engine_name,
        #     "query": query,
        # }

        # filter out unset values
        # connect_params = {
        #     param: value
        #     for (param, value) in connect_params.items()
        #     if value is not None
        # }

        # connect to database, open cursor
        conn = Connection(self.engine_name, self.port, self.user_email, self.password, self.db_name)
        print(conn.access_token)
        print(conn.engine_url)

        # try to execute query
        # context manager automatically rolls back failed transactions
        try:
            executed = conn.cursor().execute(query).fetchall()
            # conn.close()
            print(executed)
            return executed

        # pass through error, and ensure connection is closed
        except Exception as error:
            conn.close()
            raise error

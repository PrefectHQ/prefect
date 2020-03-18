import pymysql.cursors

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class MySQLExecute(Task): 
    '''
    Task for executing a query against a MySQL database. 
    Args:
        - db_name (str): name of MySQL database
        - user (str): user name used to authenticate
        - password (str): password used to authenticate
        - host (str): database host address
        - port (int, optional): port used to connect to MySQL database, defaults to 5432 if not provided
        - query (str, optional): query to execute against database
        - data (tuple, optional): values to use in query, must be specified using placeholder in query string
        - commit (bool, optional): set to True to commit transaction, defaults to false
        - charset (str, optional): charset you want to use (defaults to utf8mb4)
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    '''

    def __init__(
        self,
        db_name: str,
        user: str,
        password: str,
        host: str,
        port: int = 5432,
        query: str = None,
        data: tuple = None,
        commit: bool = False,
        charset: str = 'utf8mb4', 
        **kwargs
    ):
        self.db_name = db_name
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.query = query
        self.data = data
        self.commit = commit
        self.charset = charset
        super().__init__(**kwargs)

    @defaults_from_attrs("query", "data", "commit")
    def run(self, query: str = None, data: tuple = None, commit: bool = False) -> None:
        """
        Task run method. Executes a query against MySQL database.

        Args:
            - query (str, optional): query to execute against database
            - data (tuple, optional): values to use in query, must be specified using
                placeholder in query string
            - commit (bool, optional): set to True to commit transaction, defaults to False
        Returns:
            - None
        Raises:
            - Error (see below TODO)
        """
        if not query:
            raise ValueError("A query string must be provided")

        
        conn = pymysql.connect(
            host=self.host, 
            user=self.user, 
            password=self.password,
            db=self.db_name, 
            charset=self.charset,
        )

        try:
            with conn: 
                with conn.cursor() as cursor: 
                    executed = cursor.execute(query) 
                    if commit: 
                        conm.commit()

            conn.close() 
            return executed 

        except Error as e: #TODO: have more granular error catching
            conn.close() 
            return e


class MySQLFetch(Task):
    '''
    Task for fetching results of query from MySQL database.
    
    Args:
        - db_name (str): name of MySQL database
        - user (str): user name used to authenticate
        - password (str): password used to authenticate
        - host (str): database host address
        - port (int, optional): port used to connect to MySQL database, defaults to 5432 if not provided
        - fetch (str, optional): one of "one" "many" or "all", used to determine how many results to fetch from executed query
        - fetch_count (int, optional): if fetch = 'many', determines the number of results to fetch, defaults to 10
        - query (str, optional): query to execute against database
        - data (tuple, optional): values to use in query, must be specified using placeholder is query string
        - commit (bool, optional): set to True to commit transaction, defaults to false
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    '''

    def __init__(
        self,
        db_name: str,
        user: str,
        password: str,
        host: str,
        port: int = 5432,
        fetch: str = "one",
        fetch_count: int = 10,
        query: str = None,
        data: tuple = None,
        commit: bool = False,
        **kwargs
    ):
        self.db_name = db_name
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.fetch = fetch
        self.fetch_count = fetch_count
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
    ):
        """
        Task run method. Executes a query against MySQL database and fetches results.
        Args:
            - fetch (str, optional): one of "one" "many" or "all", used to determine how many results to fetch from executed query
            - fetch_count (int, optional): if fetch = 'many', determines the number of results to fetch, defaults to 10
            - query (str, optional): query to execute against database
            - data (tuple, optional): values to use in query, must be specified using placeholder is query string
            - commit (bool, optional): set to True to commit transaction, defaults to false
        Returns:
            - records (tuple or list of tuples): records from provided query
        Raises:
            - see below TODO
        """
        if not query:
            raise ValueError("A query string must be provided")

        if fetch not in {"one", "many", "all"}:
            raise ValueError(
                "The 'fetch' parameter must be one of the following - ('one', 'many', 'all')"
            )

        conn = pymysql.connect(
            host=self.host, 
            user=self.user, 
            password=self.password,
            db=self.db_name, 
            charset=self.charset,
        )

        try: 
            with conn: 
                with conn.cursor() as cursor: 
                    executed = cursor.execute(query) 

                    if fetch == "all":
                        results = cursor.fetchall()
                    elif fetch == "many":
                        results = cursor.fetchmany(fetch_count)
                    else:
                        results = cursor.fetchone()

                    if commit: 
                        conm.commit()

            conn.close() 
            return executed 

        except Error as e: #TODO: have more granular error catching
            conn.close() 
            return e

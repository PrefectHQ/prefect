import os
from py2neo import Graph
from py2neo.errors import ClientError, ConnectionUnavailable

from prefect import Task
from prefect.engine.signals import FAIL
from prefect.utilities.tasks import defaults_from_attrs


class Neo4jRunCypherQueryTask(Task):
    """
    Task to run a Cypher query against Neo4j.
    More information about the Cypher query language, can be
    found at https://neo4j.com/developer/cypher/.
    This task uses `py2neo` under the hood.
    For more information, please visit
    https://py2neo.org/2021.1/index.html.

    Args:
        - server_uri (str, optional): The Neo4j URI to connect to.
            More information regarding the accepted forms for `server_uri`
            can be found at https://py2neo.org/2021.1/profiles.html.
            This parameter, if provided, takes precedence over
            `server_uri_env_var`.
        - user (str, optional): The user to use to connect
            to Neo4j.
            This parameter, if provided, takes precedence over
            `user_env_var`.
        - password (str, optional): The password to use to connect
            to Neo4j.
            This parameter, if provided, takes precedence over
            `password_env_var`.
        - db_name: (str, optional): The database name where the Cypher query
            will run.
            This parameter, if provided, takes precedence over
            `db_name_env_var`.
        - server_uri_env_var (str, optional): The name of the environment variable
            that contains the Neo4j server URI to connect to.
        - user_env_var (str, optional): The name of the environment variable
            that contains the user to use to connect to Neo4j.
        - password_env_var (str, optional): The name of the environment variable
            that contains the password to use to connect to Neo4j.
        - db_name_env_var (str, optional): The name of the environment variable
            that contains the database name where the Cypher query will run.
        - cypher_query (str, optional): The Cypher query to run.
            More information about the Cypher query language, can be
            found at https://neo4j.com/developer/cypher/.
        - return_result_as (str, optional): How to return the result.
            Accepted values are `raw`, `dataframe`.
            Defaults to `raw` (which will return a `list` of `dict`).
            Applies only when the query returned result is not empty.
        - **kwargs (dict, optional): Additional keyword arguments to pass to the
            Task constructor.
    """

    __DEFAULT_RETURN_RESULT_TYPE = "raw"
    __ACCEPTED_RETURN_RESULT_TYPES = [__DEFAULT_RETURN_RESULT_TYPE, "dataframe"]

    def __init__(
        self,
        server_uri: str = None,
        user: str = None,
        password: str = None,
        db_name: str = None,
        server_uri_env_var: str = None,
        user_env_var: str = None,
        password_env_var: str = None,
        db_name_env_var: str = None,
        cypher_query: str = None,
        return_result_as: str = __DEFAULT_RETURN_RESULT_TYPE,
        **kwargs,
    ):
        self.server_uri = server_uri
        self.user = user
        self.password = password
        self.db_name = db_name
        self.server_uri_env_var = server_uri_env_var
        self.user_env_var = user_env_var
        self.password_env_var = password_env_var
        self.db_name_env_var = db_name_env_var
        self.cypher_query = cypher_query
        self.return_result_as = return_result_as
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "server_uri",
        "user",
        "password",
        "db_name",
        "server_uri_env_var",
        "user_env_var",
        "password_env_var",
        "db_name_env_var",
        "cypher_query",
        "return_result_as",
    )
    def run(
        self,
        server_uri: str = None,
        user: str = None,
        password: str = None,
        db_name: str = None,
        server_uri_env_var: str = None,
        user_env_var: str = None,
        password_env_var: str = None,
        db_name_env_var: str = None,
        cypher_query: str = None,
        return_result_as: str = __DEFAULT_RETURN_RESULT_TYPE,
    ):
        """
        Task run method to run a Cypher query against Neo4j.

        Args:
            - server_uri (str, optional): The Neo4j URI to connect to.
                More information regarding the accepted forms for `server_uri`
                can be found at https://py2neo.org/2021.1/profiles.html.
                This parameter, if provided, takes precedence over
                `server_uri_env_var`.
            - user (str, optional): The user to use to connect
                to Neo4j.
                This parameter, if provided, takes precedence over
                `user_env_var`.
            - password (str, optional): The password to use to connect
                to Neo4j.
                This parameter, if provided, takes precedence over
                `password_env_var`.
            - db_name: (str, optional): The database name where the Cypher query
                will run.
                This parameter, if provided, takes precedence over
                `db_name_env_var`.
            - server_uri_env_var (str, optional): The name of the environment variable
                that contains the Neo4j server URI to connect to.
            - user_env_var (str, optional): The name of the environment variable
                that contains the user to use to connect to Neo4j.
            - password_env_var (str, optional): The name of the environment variable
                that contains the password to use to connect to Neo4j.
            - db_name_env_var (str, optional): The name of the environment variable
                that contains the database name where the Cypher query will run.
            - cypher_query (str, optional): The Cypher query to run.
                More information about the Cypher query language, can be
                found at https://neo4j.com/developer/cypher/.
            - return_result_as (str, optional): How to return the result.
                Accepted values are `raw`, `dataframe`.
                Defaults to `raw` (which will return a `list` of `dict`).
                Applies only when the query returned result is not empty.

        Returns:
            - `None` if the query result is empty.
            - The original result if `return_result_as` is `raw`.
            - A `pandas.DataFrame` if `return_result_as` is `dataframe`.

        Raises:
            - `ValueError` if both `server_uri` and `server_uri_env_var`
                are `None`.
            - `ValueError` if `server_uri` is `None` and `server_uri_env_var`
                is not found.
            - `ValueError` if both `user` and `user_env_var`
                are `None`.
            - `ValueError` if `user` is `None` and `user_env_var` is
                not found.
            - `ValueError` if both `password` and `password_env_var`
                are not found.
            - `ValueError` if `password` is `None` and `password_env_var`
                is not found.
            - `ValueError` if `db_name` is `None` and `db_name_env_var`
                is not found.
            - `ValueError` if `cypher_query` is `None`.
            - `ValueError` if `return_result_as` is not one of
                `raw`, `dataframe`.
            - `prefect.engine.signals.FAIL` if any error occurs while establishing
                the connection with Neo4j.
            - `prefect.engine.signals.FAIL` if any error occurs while running
                the Cypher query.
        """
        if not server_uri and not server_uri_env_var:
            msg = "Please provide either the `server_uri` or the `server_uri_env_var`."
            raise ValueError(msg)

        if not server_uri and server_uri_env_var not in os.environ.keys():
            msg = f"`{server_uri_env_var}` not found in environment variables."
            raise ValueError(msg)

        neo4j_uri = server_uri or os.environ[server_uri_env_var]

        if not user and not user_env_var:
            msg = "Please provide either the `user` or the `user_env_var`."
            raise ValueError(msg)

        if not user and user_env_var not in os.environ.keys():
            msg = f"`{user_env_var}` not found in environment variables."
            raise ValueError(msg)

        neo4j_user = user or os.environ[user_env_var]

        if not password and not password_env_var:
            msg = "Please provide either the `password` or the `password_env_var`."
            raise ValueError(msg)

        if not password and password_env_var not in os.environ.keys():
            msg = f"`{password_env_var}` not found in environment variables."
            raise ValueError(msg)

        neo4j_password = password or os.environ[password_env_var]

        neo4j_db_name = None
        if db_name:
            neo4j_db_name = db_name
        elif db_name_env_var and db_name_env_var not in os.environ.keys():
            msg = f"`{db_name_env_var}` not found in environment variables."
            raise ValueError(msg)
        elif db_name_env_var and db_name_env_var in os.environ.keys():
            neo4j_db_name = os.environ[db_name_env_var]

        if not cypher_query:
            raise ValueError("Please provide a value for `cypher_query`.")

        if return_result_as not in self.__ACCEPTED_RETURN_RESULT_TYPES:
            msg = f"Illegal value for `return_result_as`. Illegal value is: {return_result_as}."
            raise ValueError(msg)

        try:
            graph = Graph(
                profile=neo4j_uri, name=neo4j_db_name, auth=(neo4j_user, neo4j_password)
            )
        except ConnectionUnavailable as e:
            msg = f"Error while connecting to Neo4j. Exception: {str(e)}"
            raise FAIL(message=msg)

        try:
            r = graph.run(cypher_query)
        except ClientError as e:
            msg = f"Error while running Cypher query. Exception: {str(e)}"
            raise FAIL(message=msg)

        result = r.data()

        if not result:
            return None
        elif return_result_as == "dataframe":
            return r.to_data_frame()
        else:
            return result

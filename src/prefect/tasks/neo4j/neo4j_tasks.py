from py2neo import Graph

from prefect import Task
from prefect.engine.signals import FAIL
from prefect.utilities.tasks import defaults_from_attrs

class Neo4jRunCypherQueryTask(Task):
    """
    TODO
    """

    def __init__(
        self,
        server_url: str = None,
        user: str = None,
        password: str = None,
        server_url_env_var = "",
        user_env_var: str = "",
        password_env_var: str = "",
        cypher_query: str = None,
        parse_result_as_dataframe: bool = False,
        **kwargs
    ):
        pass

    @defaults_from_attrs(
        "server_url",
        "user",
        "password",
        "server_url_env_var",
        "password_env_var",
        "cypher_query",
        "parse_result_as_dataframe"
    )
    def run(
        self,
        server_url: str = None,
        user: str = None,
        password: str = None,
        server_url_env_var = "",
        user_env_var: str = "",
        password_env_var: str = "",
        cypher_query: str = None,
        parse_result_as_dataframe: bool = False
    ):
        pass
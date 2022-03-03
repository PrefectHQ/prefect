from transform import MQLClient

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class TrasformCreateMaterialization(Task):
    """
    TODO

    Args:
        - api_key (str, optional): Transform API Key to be used to
            connect to Transform MQL Server.
        - api_key_env_var (str, optional): The name of the environment variable
            that contains the API Key to be used to connect to Transform MQL Server.
        - mql_server_url (str, optional): The URL of the Transform MQL Server
            where to create the materialization.
        - mql_server_url_env_var (str, optional): The name of the environment variable
            that contains the URL of the Transform MQL Server where to
            create the materialization.
        - model_key_id (int, optional): The unique identifier of the Transform model
            against which the transformation will be created.
        - materialization_name (str, optional): The name of the Transform materialization
            to create.
        - start_date (str, optional): The ISO start date of the materialization.
        - end_date (str, optional): The ISO end date of the materialization.
        - output_table (str, optional): The name of the database table, in the form of
            `schema_name.table_name` where the materialization will be created.
        - force (bool, optional): Whether to force the materialization creation
            or not.
        - run_async (bool, optional): Whether to trigger the materialization creation
            in async mode or not.
    """

    def __init__(
        self,
        api_key: str = None,
        api_key_env_var: str = None,
        mql_server_url: str = None,
        mql_server_url_env_var: str = None,
        model_key_id: int = None,
        materialization_name: str = None,
        start_date: str = None,
        end_date: str = None,
        output_table: str = None,
        force: bool = False,
        run_async: bool = True,
        **kwargs
    ):
        self.api_key = api_key
        self.api_key_env_var = api_key_env_var
        self.mql_server_url = mql_server_url
        self.mql_server_url_env_var = mql_server_url_env_var
        self.model_key_id = model_key_id
        self.materialization_name = materialization_name
        self.start_date = start_date
        self.end_date = end_date
        self.output_table = output_table
        self.force = force
        self.run_async = run_async
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "api_key",
        "api_key_env_var",
        "mql_server_url",
        "mql_server_url_env_var",
        "model_key_id",
        "materialization_name",
        "start_date",
        "end_date",
        "output_table",
        "force",
        "run_async",
    )
    def run(
        self,
        api_key: str = None,
        api_key_env_var: str = None,
        mql_server_url: str = None,
        mql_server_url_env_var: str = None,
        model_key_id: int = None,
        materialization_name: str = None,
        start_date: str = None,
        end_date: str = None,
        output_table: str = None,
        force: bool = False,
        run_async: bool = True,
    ):
        """
        TODO

        Args:
            - api_key (str, optional): Transform API Key to be used to
                connect to Transform MQL Server.
            - api_key_env_var (str, optional): The name of the environment variable
                that contains the API Key to be used to connect to Transform MQL Server.
            - mql_server_url (str, optional): The URL of the Transform MQL Server
                where to create the materialization.
            - mql_server_url_env_var (str, optional): The name of the environment variable
                that contains the URL of the Transform MQL Server where to
                create the materialization.
            - model_key_id (int, optional): The unique identifier of the Transform model
                against which the transformation will be created.
            - materialization_name (str, optional): The name of the Transform materialization
                to create.
            - start_date (str, optional): The ISO start date of the materialization.
            - end_date (str, optional): The ISO end date of the materialization.
            - output_table (str, optional): The name of the database table, in the form of
                `schema_name.table_name` where the materialization will be created.
            - force (bool, optional): Whether to force the materialization creation
                or not.
            - run_async (bool, optional): Whether to trigger the materialization creation
                in async mode or not.

        Raises:
            - TODO

        Returns:
            - TODO
        """
        pass

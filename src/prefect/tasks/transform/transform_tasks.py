import os
from transform import MQLClient

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs
from prefect.engine.signals import FAIL


class TrasformCreateMaterialization(Task):
    """
    Task to create a materialization against a Transform metrics layer
    deployment.
    Please refer to [Transform official documentation](https://docs.transform.co/)
    for more information.
    This task uses [Transform official MQL Client](https://pypi.org/project/transform/)
    under the hood.

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
        - start_time (str, optional): The UTC start time of the materialization.
        - end_time (str, optional): The UTC end time of the materialization.
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
        start_time: str = None,
        end_time: str = None,
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
        self.start_time = start_time
        self.end_time = end_time
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
        "start_time",
        "end_time",
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
        start_time: str = None,
        end_time: str = None,
        output_table: str = None,
        force: bool = False,
        run_async: bool = True,
    ):
        """
        Task run method to create a materialization against a Transform metrics
        layer deployment.
        All parameters can be provided either during task initialization or directly
        in this `run` method.

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
            - start_time (str, optional): The UTC start time of the materialization.
            - end_time (str, optional): The ISO end time of the materialization.
            - output_table (str, optional): The name of the database table, in the form of
                `schema_name.table_name` where the materialization will be created.
            - force (bool, optional): Whether to force the materialization creation
                or not.
            - run_async (bool, optional): Whether to trigger the materialization creation
                in async mode or not.

        Raises:
            - `ValueError` if both `api_key` and `api_key_env_var` are missing.
            - `ValueError` if both `mql_server_url` and `mql_server_url_env_var` ar missing.
            - `ValueError` if `materialization_name` is missing.

        Returns:
            - TODO
        """
        # Raise error if both api_key and api_key_env_var are missing
        if not (api_key or api_key_env_var):
            raise ValueError()
        
        # Raise error if api_key is missing and env var is not found
        if not api_key and api_key_env_var not in os.environ.keys():
            raise ValueError()
        
        mql_api_key = api_key or os.environ[api_key_env_var]

        # Raise error if both mql_server_url and mql_server_url_env_var are missing
        if not (mql_server_url or mql_server_url_env_var):
            raise ValueError()
        
        # Raise error if mql_server_url is missing and env var is not found
        if not mql_server_url and mql_server_url_env_var not in os.environ.keys():
            raise ValueError()
        
        mql_url = mql_server_url or os.environ[mql_server_url_env_var]

        if not materialization_name:
            raise ValueError()
        
        mql = MQLClient(api_key=mql_api_key, mql_server_url=mql_url)

        if run_async:
            response = mql.create_materialization(
                materialization_name=materialization_name,
                start_time=start_time,
                end_time=end_time,
                model_key_id=model_key_id,
                output_table=output_table,
                force=force    
            )
            return response
        else:
            return mql.materialize(
                materialization_name=materialization_name,
                start_time=start_time,
                end_time=end_time,
                model_key_id=model_key_id,
                output_table=output_table,
                force=force
        )
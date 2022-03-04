import os
from transform import MQLClient
from transform.exceptions import AuthException, QueryRuntimeException, URLException

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs
from prefect.engine.signals import FAIL


class TransformCreateMaterialization(Task):
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
            or not. Defaults to `False`.
        - use_async (bool, optional): Whether to trigger the materialization creation
            in async mode or not. Defaults to `False`.
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor.
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
        use_async: bool = False,
        **kwargs,
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
        self.use_async = use_async
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
        "use_async",
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
        use_async: bool = False,
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
                or not. Defaults to `False`.
            - use_async (bool, optional): Whether to trigger the materialization creation
                in async mode or not. Defaults to `False`.

        Raises:
            - `ValueError` if both `api_key` and `api_key_env_var` are missing.
            - `ValueError` if both `mql_server_url` and `mql_server_url_env_var` ar missing.
            - `ValueError` if `materialization_name` is missing.
            - `prefect.engine.signals.FAIL` if the connection with the Transform server cannot
                be established.
            - `prefect.engine.signals.FAIL` if the materialization creation process fails.

        Returns:
            - An `MqlQueryStatusResp` object if `run_async` is `True`.
            - An `MqlMaterializeResp` object if `run_async` is `False`.

        """
        # Raise error if both api_key and api_key_env_var are missing
        if not (api_key or api_key_env_var):
            msg = "Both `api_key` and `api_key_env_var` are missing."
            raise ValueError(msg)

        # Raise error if api_key is missing and env var is not found
        if not api_key and api_key_env_var not in os.environ.keys():
            msg = "`api_key` is missing and `api_key_env_var` not found in env vars."
            raise ValueError(msg)

        mql_api_key = api_key or os.environ[api_key_env_var]

        # Raise error if both mql_server_url and mql_server_url_env_var are missing
        if not (mql_server_url or mql_server_url_env_var):
            msg = "Both `mql_server_url` and `mql_server_url_env_var` are missing."
            raise ValueError(msg)

        # Raise error if mql_server_url is missing and env var is not found
        if not mql_server_url and mql_server_url_env_var not in os.environ.keys():
            msg = "`mql_server_url` is missing and `mql_server_url_env_var` not found in env vars."
            raise ValueError(msg)

        mql_url = mql_server_url or os.environ[mql_server_url_env_var]

        if not materialization_name:
            msg = "`materialization_name` is missing."
            raise ValueError(msg)

        try:
            mql_client = MQLClient(
                api_key=mql_api_key, mql_server_url=mql_url, use_async=use_async
            )
        except (AuthException, URLException) as e:
            msg = f"Cannot connect to Transform server! Error is: {e.msg}"
            raise FAIL(message=msg)

        response = None
        if use_async:
            response = mql_client.create_materialization(
                materialization_name=materialization_name,
                start_time=start_time,
                end_time=end_time,
                model_key_id=model_key_id,
                output_table=output_table,
                force=force,
            )
            if response.is_failed:
                msg = f"Transform materialization async creation failed! Error is: {response.error}"
                raise FAIL(message=msg)
        else:
            try:
                response = mql_client.materialize(
                    materialization_name=materialization_name,
                    start_time=start_time,
                    end_time=end_time,
                    model_key_id=model_key_id,
                    output_table=output_table,
                    force=force,
                )
            except QueryRuntimeException as e:
                msg = (
                    f"Transform materialization sync creation failed! Error is: {e.msg}"
                )
                raise FAIL(message=msg)

        return response

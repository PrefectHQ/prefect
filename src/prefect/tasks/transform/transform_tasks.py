from transform import MQLClient

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class TrasformCreateMaterialization(Task):
    """
    TODO
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
        **kwargs
    ):
        """
        TODO
        """
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
        "force"
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
    ):
        """
        TODO
        """
        pass

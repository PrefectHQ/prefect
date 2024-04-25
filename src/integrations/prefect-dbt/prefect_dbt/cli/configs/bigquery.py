"""Module containing models for BigQuery configs"""
from typing import Any, Dict, Optional

from google.auth.transport.requests import Request

try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal

from pydantic import VERSION as PYDANTIC_VERSION

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import Field
else:
    from pydantic import Field

from prefect_dbt.cli.configs.base import BaseTargetConfigs, MissingExtrasRequireError

try:
    from prefect_gcp.credentials import GcpCredentials
except ModuleNotFoundError as e:
    raise MissingExtrasRequireError("BigQuery") from e


class BigQueryTargetConfigs(BaseTargetConfigs):
    """
    Target configs contain credentials and
    settings, specific to BigQuery.
    To find valid keys, head to the [BigQuery Profile](
    https://docs.getdbt.com/reference/warehouse-profiles/bigquery-profile)
    page.

    Attributes:
        credentials: The credentials to use to authenticate; if there are
            duplicate keys between credentials and TargetConfigs,
            e.g. schema, an error will be raised.

    Examples:
        Load stored BigQueryTargetConfigs.
        ```python
        from prefect_dbt.cli.configs import BigQueryTargetConfigs

        bigquery_target_configs = BigQueryTargetConfigs.load("BLOCK_NAME")
        ```

        Instantiate BigQueryTargetConfigs.
        ```python
        from prefect_dbt.cli.configs import BigQueryTargetConfigs
        from prefect_gcp.credentials import GcpCredentials

        credentials = GcpCredentials.load("BLOCK-NAME-PLACEHOLDER")
        target_configs = BigQueryTargetConfigs(
            schema="schema",  # also known as dataset
            credentials=credentials,
        )
        ```
    """

    _block_type_name = "dbt CLI BigQuery Target Configs"
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/5zE9lxfzBHjw3tnEup4wWL/9a001902ed43a84c6c96d23b24622e19/dbt-bit_tm.png?h=250"  # noqa
    _description = "dbt CLI target configs containing credentials and settings, specific to BigQuery."  # noqa
    _documentation_url = "https://prefecthq.github.io/prefect-dbt/cli/configs/bigquery/#prefect_dbt.cli.configs.bigquery.BigQueryTargetConfigs"  # noqa

    type: Literal["bigquery"] = Field(
        default="bigquery", description="The type of target."
    )
    project: Optional[str] = Field(default=None, description="The project to use.")
    credentials: GcpCredentials = Field(
        default_factory=GcpCredentials,
        description="The credentials to use to authenticate.",
    )

    def get_configs(self) -> Dict[str, Any]:
        """
        Returns the dbt configs specific to BigQuery profile.

        Returns:
            A configs JSON.
        """
        # since GcpCredentials will always define a project
        self_copy = self.copy()
        if self_copy.project is not None:
            self_copy.credentials.project = None
        all_configs_json = self._populate_configs_json(
            {}, self_copy.__fields__, model=self_copy
        )

        # decouple prefect-gcp from prefect-dbt
        # by mapping all the keys dbt gcp accepts
        # https://docs.getdbt.com/reference/warehouse-setups/bigquery-setup
        rename_keys = {
            # dbt
            "type": "type",
            "schema": "schema",
            "threads": "threads",
            # general
            "dataset": "schema",
            "method": "method",
            "project": "project",
            # service-account
            "service_account_file": "keyfile",
            # service-account json
            "service_account_info": "keyfile_json",
            # oauth secrets
            "refresh_token": "refresh_token",
            "client_id": "client_id",
            "client_secret": "client_secret",
            "token_uri": "token_uri",
            # optional
            "priority": "priority",
            "timeout_seconds": "timeout_seconds",
            "location": "location",
            "maximum_bytes_billed": "maximum_bytes_billed",
            "scopes": "scopes",
            "impersonate_service_account": "impersonate_service_account",
            "execution_project": "execution_project",
        }
        configs_json = {}
        extras = self.extras or {}
        for key in all_configs_json.keys():
            if key not in rename_keys and key not in extras:
                # skip invalid keys
                continue
            # rename key to something dbt profile expects
            dbt_key = rename_keys.get(key) or key
            configs_json[dbt_key] = all_configs_json[key]

        if "keyfile_json" in configs_json:
            configs_json["method"] = "service-account-json"
        elif "keyfile" in configs_json:
            configs_json["method"] = "service-account"
            configs_json["keyfile"] = str(configs_json["keyfile"])
        else:
            configs_json["method"] = "oauth-secrets"
            # through gcloud application-default login
            google_credentials = (
                self_copy.credentials.get_credentials_from_service_account()
            )
            if hasattr(google_credentials, "token"):
                request = Request()
                google_credentials.refresh(request)
                configs_json["token"] = google_credentials.token
            else:
                for key in ("refresh_token", "client_id", "client_secret", "token_uri"):
                    configs_json[key] = getattr(google_credentials, key)

        if "project" not in configs_json:
            raise ValueError(
                "The keyword, project, must be provided in either "
                "GcpCredentials or BigQueryTargetConfigs"
            )
        return configs_json

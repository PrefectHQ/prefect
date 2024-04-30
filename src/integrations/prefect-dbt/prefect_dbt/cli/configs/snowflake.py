"""Module containing models for Snowflake configs"""
from typing import Any, Dict, Optional

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
    from prefect_snowflake.database import SnowflakeConnector
except ModuleNotFoundError as e:
    raise MissingExtrasRequireError("Snowflake") from e


class SnowflakeTargetConfigs(BaseTargetConfigs):
    """
    Target configs contain credentials and
    settings, specific to Snowflake.
    To find valid keys, head to the [Snowflake Profile](
    https://docs.getdbt.com/reference/warehouse-profiles/snowflake-profile)
    page.

    Attributes:
        connector: The connector to use.

    Examples:
        Load stored SnowflakeTargetConfigs:
        ```python
        from prefect_dbt.cli.configs import SnowflakeTargetConfigs

        snowflake_target_configs = SnowflakeTargetConfigs.load("BLOCK_NAME")
        ```

        Instantiate SnowflakeTargetConfigs.
        ```python
        from prefect_dbt.cli.configs import SnowflakeTargetConfigs
        from prefect_snowflake.credentials import SnowflakeCredentials
        from prefect_snowflake.database import SnowflakeConnector

        credentials = SnowflakeCredentials(
            user="user",
            password="password",
            account="account.region.aws",
            role="role",
        )
        connector = SnowflakeConnector(
            schema="public",
            database="database",
            warehouse="warehouse",
            credentials=credentials,
        )
        target_configs = SnowflakeTargetConfigs(
            connector=connector,
            extras={"retry_on_database_errors": True},
        )
        ```
    """

    _block_type_name = "dbt CLI Snowflake Target Configs"
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/5zE9lxfzBHjw3tnEup4wWL/9a001902ed43a84c6c96d23b24622e19/dbt-bit_tm.png?h=250"  # noqa
    _documentation_url = "https://prefecthq.github.io/prefect-dbt/cli/configs/snowflake/#prefect_dbt.cli.configs.snowflake.SnowflakeTargetConfigs"  # noqa

    type: Literal["snowflake"] = Field(
        default="snowflake", description="The type of the target configs."
    )
    schema_: Optional[str] = Field(
        default=None,
        alias="schema",
        description="The schema to use for the target configs.",
    )
    connector: SnowflakeConnector = Field(
        default=..., description="The connector to use."
    )

    def get_configs(self) -> Dict[str, Any]:
        """
        Returns the dbt configs specific to Snowflake profile.

        Returns:
            A configs JSON.
        """
        all_configs_json = super().get_configs()

        # decouple prefect-snowflake from prefect-dbt
        # by mapping all the keys dbt snowflake accepts
        # https://docs.getdbt.com/reference/warehouse-setups/snowflake-setup
        rename_keys = {
            # dbt
            "type": "type",
            "schema": "schema",
            "threads": "threads",
            # general
            "account": "account",
            "user": "user",
            "role": "role",
            "database": "database",
            "warehouse": "warehouse",
            # user and password
            "password": "password",
            # duo mfa / sso
            "authenticator": "authenticator",
            # key pair
            "private_key_path": "private_key_path",
            "private_key_passphrase": "private_key_passphrase",
            # optional
            "client_session_keep_alive": "client_session_keep_alive",
            "query_tag": "query_tag",
            "connect_retries": "connect_retries",
            "connect_timeout": "connect_timeout",
            "retry_on_database_errors": "retry_on_database_errors",
            "retry_all": "retry_all",
        }
        configs_json = {}
        extras = self.extras or {}
        for key in all_configs_json.keys():
            if key not in rename_keys and key not in extras:
                # skip invalid keys, like fetch_size + poll_frequency_s
                continue
            # rename key to something dbt profile expects
            dbt_key = rename_keys.get(key) or key
            configs_json[dbt_key] = all_configs_json[key]
        return configs_json

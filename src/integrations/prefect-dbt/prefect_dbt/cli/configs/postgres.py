"""Module containing models for Postgres configs"""
import warnings
from typing import Any, Dict, Union

from pydantic import VERSION as PYDANTIC_VERSION

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import Field
else:
    from pydantic import Field

from typing_extensions import Literal

from prefect_dbt.cli.configs.base import BaseTargetConfigs, MissingExtrasRequireError

try:
    from prefect_sqlalchemy import DatabaseCredentials, SqlAlchemyConnector
except ModuleNotFoundError as e:
    raise MissingExtrasRequireError("Postgres") from e


class PostgresTargetConfigs(BaseTargetConfigs):
    """
    Target configs contain credentials and
    settings, specific to Postgres.
    To find valid keys, head to the [Postgres Profile](
    https://docs.getdbt.com/reference/warehouse-profiles/postgres-profile)
    page.

    Attributes:
        credentials: The credentials to use to authenticate; if there are
            duplicate keys between credentials and TargetConfigs,
            e.g. schema, an error will be raised.

    Examples:
        Load stored PostgresTargetConfigs:
        ```python
        from prefect_dbt.cli.configs import PostgresTargetConfigs

        postgres_target_configs = PostgresTargetConfigs.load("BLOCK_NAME")
        ```

        Instantiate PostgresTargetConfigs with DatabaseCredentials.
        ```python
        from prefect_dbt.cli.configs import PostgresTargetConfigs
        from prefect_sqlalchemy import DatabaseCredentials, SyncDriver

        credentials = DatabaseCredentials(
            driver=SyncDriver.POSTGRESQL_PSYCOPG2,
            username="prefect",
            password="prefect_password",
            database="postgres",
            host="host",
            port=8080
        )
        target_configs = PostgresTargetConfigs(credentials=credentials, schema="schema")
        ```
    """

    _block_type_name = "dbt CLI Postgres Target Configs"
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/5zE9lxfzBHjw3tnEup4wWL/9a001902ed43a84c6c96d23b24622e19/dbt-bit_tm.png?h=250"  # noqa
    _description = "dbt CLI target configs containing credentials and settings specific to Postgres."  # noqa
    _documentation_url = "https://prefecthq.github.io/prefect-dbt/cli/configs/postgres/#prefect_dbt.cli.configs.postgres.PostgresTargetConfigs"  # noqa

    type: Literal["postgres"] = Field(
        default="postgres", description="The type of the target."
    )
    credentials: Union[SqlAlchemyConnector, DatabaseCredentials] = Field(
        default=...,
        description=(
            "The credentials to use to authenticate; if there are duplicate keys "
            "between credentials and TargetConfigs, e.g. schema, "
            "an error will be raised."
        ),
    )  # noqa

    def get_configs(self) -> Dict[str, Any]:
        """
        Returns the dbt configs specific to Postgres profile.

        Returns:
            A configs JSON.
        """
        if isinstance(self.credentials, DatabaseCredentials):
            warnings.warn(
                "Using DatabaseCredentials is deprecated and will be removed "
                "on May 7th, 2023, use SqlAlchemyConnector instead.",
                DeprecationWarning,
            )
        all_configs_json = super().get_configs()

        rename_keys = {
            # dbt
            "type": "type",
            "schema": "schema",
            "threads": "threads",
            # general
            "host": "host",
            "username": "user",
            "password": "password",
            "port": "port",
            "database": "dbname",
            # optional
            "keepalives_idle": "keepalives_idle",
            "connect_timeout": "connect_timeout",
            "retries": "retries",
            "search_path": "search_path",
            "role": "role",
            "sslmode": "sslmode",
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
        port = configs_json.get("port")
        if port is not None:
            configs_json["port"] = int(port)
        return configs_json

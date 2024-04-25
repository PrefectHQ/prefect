"""Module containing credentials for interacting with dbt CLI"""

from typing import Any, Dict, Optional, Union

from pydantic import VERSION as PYDANTIC_VERSION

from prefect.blocks.core import Block

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import Field
else:
    from pydantic import Field

from prefect_dbt.cli.configs import GlobalConfigs, TargetConfigs

try:
    from prefect_dbt.cli.configs.bigquery import BigQueryTargetConfigs
except ImportError:
    BigQueryTargetConfigs = None

try:
    from prefect_dbt.cli.configs.snowflake import SnowflakeTargetConfigs
except ImportError:
    SnowflakeTargetConfigs = None

try:
    from prefect_dbt.cli.configs.postgres import PostgresTargetConfigs
except ImportError:
    PostgresTargetConfigs = None


class DbtCliProfile(Block):
    """
    Profile for use across dbt CLI tasks and flows.

    Attributes:
        name (str): Profile name used for populating profiles.yml.
        target (str): The default target your dbt project will use.
        target_configs (TargetConfigs): Target configs contain credentials and
            settings, specific to the warehouse you're connecting to.
            To find valid keys, head to the [Available adapters](
            https://docs.getdbt.com/docs/available-adapters) page and
            click the desired adapter's "Profile Setup" hyperlink.
        global_configs (GlobalConfigs): Global configs control
            things like the visual output of logs, the manner
            in which dbt parses your project, and what to do when
            dbt finds a version mismatch or a failing model.
            Valid keys can be found [here](
            https://docs.getdbt.com/reference/global-configs).

    Examples:
        Load stored dbt CLI profile:
        ```python
        from prefect_dbt.cli import DbtCliProfile
        dbt_cli_profile = DbtCliProfile.load("BLOCK_NAME").get_profile()
        ```

        Get a dbt Snowflake profile from DbtCliProfile by using SnowflakeTargetConfigs:
        ```python
        from prefect_dbt.cli import DbtCliProfile
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
            connector=connector
        )
        dbt_cli_profile = DbtCliProfile(
            name="jaffle_shop",
            target="dev",
            target_configs=target_configs,
        )
        profile = dbt_cli_profile.get_profile()
        ```

        Get a dbt Redshift profile from DbtCliProfile by using generic TargetConfigs:
        ```python
        from prefect_dbt.cli import DbtCliProfile
        from prefect_dbt.cli.configs import GlobalConfigs, TargetConfigs

        target_configs_extras = dict(
            host="hostname.region.redshift.amazonaws.com",
            user="username",
            password="password1",
            port=5439,
            dbname="analytics",
        )
        target_configs = TargetConfigs(
            type="redshift",
            schema="schema",
            threads=4,
            extras=target_configs_extras
        )
        dbt_cli_profile = DbtCliProfile(
            name="jaffle_shop",
            target="dev",
            target_configs=target_configs,
        )
        profile = dbt_cli_profile.get_profile()
        ```
    """

    _block_type_name = "dbt CLI Profile"
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/5zE9lxfzBHjw3tnEup4wWL/9a001902ed43a84c6c96d23b24622e19/dbt-bit_tm.png?h=250"  # noqa
    _documentation_url = "https://prefecthq.github.io/prefect-dbt/cli/credentials/#prefect_dbt.cli.credentials.DbtCliProfile"  # noqa

    name: str = Field(
        default=..., description="Profile name used for populating profiles.yml."
    )
    target: str = Field(
        default=..., description="The default target your dbt project will use."
    )
    target_configs: Union[
        SnowflakeTargetConfigs,
        BigQueryTargetConfigs,
        PostgresTargetConfigs,
        TargetConfigs,
    ] = Field(
        default=...,
        description=(
            "Target configs contain credentials and settings, specific to the "
            "warehouse you're connecting to."
        ),
    )
    global_configs: Optional[GlobalConfigs] = Field(
        default=None,
        description=(
            "Global configs control things like the visual output of logs, the manner "
            "in which dbt parses your project, and what to do when dbt finds a version "
            "mismatch or a failing model."
        ),
    )

    def get_profile(self) -> Dict[str, Any]:
        """
        Returns the dbt profile, likely used for writing to profiles.yml.

        Returns:
            A JSON compatible dictionary with the expected format of profiles.yml.
        """
        profile = {
            "config": self.global_configs.get_configs() if self.global_configs else {},
            self.name: {
                "target": self.target,
                "outputs": {self.target: self.target_configs.get_configs()},
            },
        }
        return profile

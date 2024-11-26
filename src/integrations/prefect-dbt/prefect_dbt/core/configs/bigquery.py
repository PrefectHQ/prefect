"""Module containing models for BigQuery configs"""

from typing import Any, Dict, Optional

try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal


from pydantic import Field

from prefect.blocks.core import SecretDict
from prefect_dbt.core.configs.base import BaseTargetConfigs, MissingExtrasRequireError
from prefect_dbt.utils import load_profiles_yml, slugify_schema

try:
    from google.auth.transport.requests import Request
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
        from prefect_dbt.core.configs import BigQueryTargetConfigs

        bigquery_target_configs = BigQueryTargetConfigs.load("BLOCK_NAME")
        ```

        Instantiate BigQueryTargetConfigs.
        ```python
        from prefect_dbt.core.configs import BigQueryTargetConfigs
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
    _documentation_url = "https://docs.prefect.io/integrations/prefect-dbt"  # noqa

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
            {}, self_copy.model_fields, model=self_copy
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

    @classmethod
    def create_from_profile(
        cls,
        profiles_dir: str,
        profile_name: str,
        output_name: Optional[str] = None,
        save_credentials: bool = False,
    ) -> list["BigQueryTargetConfigs"]:
        """Create BigQueryTargetConfigs instances from a dbt profile.
        Will create and save nested GcpCredentials blocks if the connection
        method is `service-account` or `service-account-json` and `save_credentials`
        is `True`.

        Args:
            profiles_dir: Path to the directory containing profiles.yml
            profile_name: Name of the profile to use

        Returns:
            A BigQueryTargetConfigs instance configured from the profile

        Raises:
            ValueError: If the profile is not found or is not a BigQuery profile
        """
        profiles = load_profiles_yml(profiles_dir)
        profile_data = profiles.get(profile_name)

        if not profile_data:
            raise ValueError(f"Profile {profile_name} not found in profiles.yml")

        target = profile_data.get("target")
        if not target:
            raise ValueError(f"No default target found in profile {profile_name}")

        outputs = profile_data.get("outputs", {})
        if not outputs:
            raise ValueError(f"Outputs not found in profile {profile_name}")

        configs = []
        for name, target_config in outputs.items():
            if output_name and output_name != name:
                continue

            if target_config.get("type") != "bigquery":
                continue

            schema = target_config.get("dataset", target_config.get("schema"))

            if target_config.get("method") == "service-account":
                credentials = GcpCredentials(
                    service_account_file=target_config.get("keyfile"),
                    project=target_config.get("project"),
                )

            elif target_config.get("method") == "service-account-json":
                credentials = GcpCredentials(
                    service_account_info=SecretDict(target_config.get("keyfile_json")),
                    project=target_config.get("project"),
                )

            else:
                credentials = GcpCredentials()

            if save_credentials:
                credentials.save(
                    name=f"dbt-gcp-credentials-{slugify_schema(schema)}", overwrite=True
                )
                print(
                    f"Saved GCP Credentials block: dbt-gcp-credentials-{slugify_schema(schema)}"
                )

            config = cls(
                type=target_config.get("type"),
                schema=schema,
                threads=target_config.get("threads", 4),
                project=target_config.get("project"),
                credentials=credentials,
            )
            configs.append(config)

        return configs

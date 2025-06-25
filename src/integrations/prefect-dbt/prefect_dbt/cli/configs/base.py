"""Module containing models for base configs"""

import abc
from pathlib import Path
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel, Field, model_validator
from typing_extensions import Self

from prefect.blocks.core import Block
from prefect_dbt.core.settings import PrefectDbtSettings


class DbtConfigs(Block, abc.ABC):
    """
    Abstract class for other dbt Configs.

    Attributes:
        extras: Extra target configs' keywords, not yet exposed
            in prefect-dbt, but available in dbt; if there are
            duplicate keys between extras and TargetConfigs,
            an error will be raised.
    """

    extras: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Extra target configs' keywords, not yet exposed in prefect-dbt, "
            "but available in dbt."
        ),
    )
    allow_field_overrides: bool = Field(
        default=False,
        description=(
            "If enabled, fields from dbt target configs will override "
            "fields provided in extras and credentials."
        ),
    )
    _documentation_url = "https://docs.prefect.io/integrations/prefect-dbt"  # noqa

    def _populate_configs_json(
        self,
        configs_json: dict[str, Any],
        fields: dict[str, Any],
        model: Optional[BaseModel] = None,
    ) -> dict[str, Any]:
        """
        Recursively populate configs_json.
        """
        # if allow_field_overrides is True keys from TargetConfigs take precedence
        override_configs_json: dict[str, Any] = {}

        for field_name, field in fields.items():
            if model is not None:
                # get actual value from model
                field_value = getattr(model, field_name, None)
                # override the name with alias so dbt parser can recognize the keyword;
                # e.g. schema_ -> schema, returns the original name if no alias is set
                if field.alias:
                    field_name = field.alias
            else:
                field_value = field

            if field_value is None or field_name == "allow_field_overrides":
                # do not add to configs json if no value or default is set
                continue

            if isinstance(field_value, BaseModel):
                configs_json = self._populate_configs_json(
                    configs_json, field_value.model_fields, model=field_value
                )
            elif field_name == "extras":
                configs_json = self._populate_configs_json(
                    configs_json,
                    field_value,
                )
                override_configs_json.update(configs_json)
            else:
                if field_name in configs_json.keys() and not self.allow_field_overrides:
                    raise ValueError(
                        f"The keyword, {field_name}, has already been provided in "
                        f"TargetConfigs; remove duplicated keywords to continue"
                    )
                if hasattr(field_value, "get_secret_value"):
                    field_value = field_value.get_secret_value()
                elif isinstance(field_value, Path):
                    field_value = str(field_value)
                configs_json[field_name] = field_value

                if self.allow_field_overrides and model is self or model is None:
                    override_configs_json[field_name] = field_value

        configs_json.update(override_configs_json)
        return configs_json

    def get_configs(self) -> dict[str, Any]:
        """
        Returns the dbt configs, likely used eventually for writing to profiles.yml.

        Returns:
            A configs JSON.
        """
        return self._populate_configs_json({}, type(self).model_fields, model=self)


class BaseTargetConfigs(DbtConfigs, abc.ABC):
    type: str = Field(default=..., description="The name of the database warehouse.")
    schema_: str = Field(
        alias="schema",
        description=(
            "The schema that dbt will build objects into; "
            "in BigQuery, a schema is actually a dataset."
        ),
    )
    threads: int = Field(
        default=4,
        description=(
            "The number of threads representing the max number "
            "of paths through the graph dbt may work on at once."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def handle_target_configs(cls, v: Any) -> Any:
        """Handle target configs field aliasing during validation"""
        if isinstance(v, dict):
            if "schema_" in v:
                v["schema"] = v.pop("schema_")
            # Handle nested blocks
            for value in v.values():
                if isinstance(value, dict) and "schema_" in value:
                    value["schema"] = value.pop("schema_")
        return v


class TargetConfigs(BaseTargetConfigs):
    """
    Target configs contain credentials and
    settings, specific to the warehouse you're connecting to.
    To find valid keys, head to the [Available adapters](
    https://docs.getdbt.com/docs/available-adapters) page and
    click the desired adapter's "Profile Setup" hyperlink.

    Attributes:
        type: The name of the database warehouse.
        schema: The schema that dbt will build objects into;
            in BigQuery, a schema is actually a dataset.
        threads: The number of threads representing the max number
            of paths through the graph dbt may work on at once.

    Examples:
        Load stored TargetConfigs:
        ```python
        from prefect_dbt.cli.configs import TargetConfigs

        dbt_cli_target_configs = TargetConfigs.load("BLOCK_NAME")
        ```
    """

    _block_type_name = "dbt CLI Target Configs"
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/5zE9lxfzBHjw3tnEup4wWL/9a001902ed43a84c6c96d23b24622e19/dbt-bit_tm.png?h=250"  # noqa
    _documentation_url = "https://docs.prefect.io/integrations/prefect-dbt"  # noqa

    @classmethod
    def from_profiles_yml(
        cls: Type[Self],
        profile_name: Optional[str] = None,
        target_name: Optional[str] = None,
        profiles_dir: Optional[str] = None,
        allow_field_overrides: bool = False,
    ) -> "TargetConfigs":
        """
        Create a TargetConfigs instance from a dbt profiles.yml file.

        Args:
            profile_name: Name of the profile to use from profiles.yml.
                If None, uses the first profile.
            target_name: Name of the target to use from the profile.
                If None, uses the default target in the selected profile.
            profiles_dir: Path to the directory containing profiles.yml.
                If None, uses the default profiles directory.
            allow_field_overrides: If enabled, fields from dbt target configs
                will override fields provided in extras and credentials.

        Returns:
            A TargetConfigs instance populated from the profiles.yml target.

        Raises:
            ValueError: If profiles.yml is not found or if profile/target is invalid
        """
        if profiles_dir:
            profiles = PrefectDbtSettings(
                profiles_dir=Path(profiles_dir)
            ).load_profiles_yml()
        else:
            profiles = PrefectDbtSettings().load_profiles_yml()

        # If no profile specified, use first non-config one
        if profile_name is None:
            for name in profiles:
                if name != "config":
                    profile_name = name
                    break
        elif profile_name not in profiles:
            raise ValueError(f"Profile {profile_name} not found in profiles.yml")

        profile = profiles[profile_name]
        if "outputs" not in profile:
            raise ValueError(f"No outputs found in profile {profile_name}")

        outputs = profile["outputs"]

        # If no target specified, use default target
        if target_name is None:
            target_name = profile["target"]
        elif target_name not in outputs:
            raise ValueError(
                f"Target {target_name} not found in profile {profile_name}"
            )

        target_config = outputs[target_name]

        type = target_config.pop("type")
        schema = None
        possible_keys = ["schema", "path", "dataset", "database"]
        for key in possible_keys:
            if key in target_config:
                schema = target_config.pop(key)
                break

        if schema is None:
            raise ValueError(f"No schema found. Expected one of: {possible_keys}")
        threads = target_config.pop("threads", 4)
        return cls(
            type=type,
            schema=schema,
            threads=threads,
            extras=target_config or None,
            allow_field_overrides=allow_field_overrides,
        )


class GlobalConfigs(DbtConfigs):
    """
    Global configs control things like the visual output
    of logs, the manner in which dbt parses your project,
    and what to do when dbt finds a version mismatch
    or a failing model. Docs can be found [here](
    https://docs.getdbt.com/reference/global-configs).

    Attributes:
        send_anonymous_usage_stats: Whether usage stats are sent to dbt.
        use_colors: Colorize the output it prints in your terminal.
        partial_parse: When partial parsing is enabled, dbt will use an
            stored internal manifest to determine which files have been changed
            (if any) since it last parsed the project.
        printer_width: Length of characters before starting a new line.
        write_json: Determines whether dbt writes JSON artifacts to
            the target/ directory.
        warn_error: Whether to convert dbt warnings into errors.
        log_format: The LOG_FORMAT config specifies how dbt's logs should
            be formatted. If the value of this config is json, dbt will
            output fully structured logs in JSON format.
        debug: Whether to redirect dbt's debug logs to standard out.
        version_check: Whether to raise an error if a project's version
            is used with an incompatible dbt version.
        fail_fast: Make dbt exit immediately if a single resource fails to build.
        use_experimental_parser: Opt into the latest experimental version
            of the static parser.
        static_parser: Whether to use the [static parser](
            https://docs.getdbt.com/reference/parsing#static-parser).

    Examples:
        Load stored GlobalConfigs:
        ```python
        from prefect_dbt.cli.configs import GlobalConfigs

        dbt_cli_global_configs = GlobalConfigs.load("BLOCK_NAME")
        ```
    """

    _block_type_name = "dbt CLI Global Configs"
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/5zE9lxfzBHjw3tnEup4wWL/9a001902ed43a84c6c96d23b24622e19/dbt-bit_tm.png?h=250"  # noqa
    _documentation_url = "https://docs.prefect.io/integrations/prefect-dbt"  # noqa

    send_anonymous_usage_stats: Optional[bool] = Field(
        default=None,
        description="Whether usage stats are sent to dbt.",
    )
    use_colors: Optional[bool] = Field(
        default=None,
        description="Colorize the output it prints in your terminal.",
    )
    partial_parse: Optional[bool] = Field(
        default=None,
        description=(
            "When partial parsing is enabled, dbt will use an "
            "stored internal manifest to determine which files have been changed "
            "(if any) since it last parsed the project."
        ),
    )
    printer_width: Optional[int] = Field(
        default=None,
        description="Length of characters before starting a new line.",
    )
    write_json: Optional[bool] = Field(
        default=None,
        description=(
            "Determines whether dbt writes JSON artifacts to the target/ directory."
        ),
    )
    warn_error: Optional[bool] = Field(
        default=None,
        description="Whether to convert dbt warnings into errors.",
    )
    log_format: Optional[str] = Field(
        default=None,
        description=(
            "The LOG_FORMAT config specifies how dbt's logs should "
            "be formatted. If the value of this config is json, dbt will "
            "output fully structured logs in JSON format."
        ),
    )
    debug: Optional[bool] = Field(
        default=None,
        description="Whether to redirect dbt's debug logs to standard out.",
    )
    version_check: Optional[bool] = Field(
        default=None,
        description=(
            "Whether to raise an error if a project's version "
            "is used with an incompatible dbt version."
        ),
    )
    fail_fast: Optional[bool] = Field(
        default=None,
        description=("Make dbt exit immediately if a single resource fails to build."),
    )
    use_experimental_parser: Optional[bool] = Field(
        default=None,
        description=("Opt into the latest experimental version of the static parser."),
    )
    static_parser: Optional[bool] = Field(
        default=None,
        description=(
            "Whether to use the [static parser](https://docs.getdbt.com/reference/parsing#static-parser)."  # noqa
        ),
    )


class MissingExtrasRequireError(ImportError):
    def __init__(self, service, *args, **kwargs):
        msg = (
            f"To use {service.title()}TargetConfigs, "
            f'execute `pip install "prefect-dbt[{service.lower()}]"`'
        )
        super().__init__(msg, *args, **kwargs)

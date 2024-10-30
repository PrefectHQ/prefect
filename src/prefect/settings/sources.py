import os
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type

import toml
from pydantic import AliasChoices
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
)
from pydantic_settings.sources import ConfigFileSourceMixin

from prefect.settings.constants import DEFAULT_PREFECT_HOME, DEFAULT_PROFILES_PATH


class EnvFilterSettingsSource(EnvSettingsSource):
    """
    Custom pydantic settings source to filter out specific environment variables.

    All validation aliases are loaded from environment variables by default. We use
    `AliasPath` to maintain the ability set fields via model initialization, but those
    shouldn't be loaded from environment variables. This loader allows use to say which
    environment variables should be ignored.
    """

    def __init__(
        self,
        settings_cls: type[BaseSettings],
        case_sensitive: Optional[bool] = None,
        env_prefix: Optional[str] = None,
        env_nested_delimiter: Optional[str] = None,
        env_ignore_empty: Optional[bool] = None,
        env_parse_none_str: Optional[str] = None,
        env_parse_enums: Optional[bool] = None,
        env_filter: Optional[List[str]] = None,
    ) -> None:
        super().__init__(
            settings_cls,
            case_sensitive,
            env_prefix,
            env_nested_delimiter,
            env_ignore_empty,
            env_parse_none_str,
            env_parse_enums,
        )
        if env_filter:
            if isinstance(self.env_vars, dict):
                for key in env_filter:
                    self.env_vars.pop(key, None)
            else:
                self.env_vars = {
                    key: value
                    for key, value in self.env_vars.items()  # type: ignore
                    if key.lower() not in env_filter
                }


class ProfileSettingsTomlLoader(PydanticBaseSettingsSource):
    """
    Custom pydantic settings source to load profile settings from a toml file.

    See https://docs.pydantic.dev/latest/concepts/pydantic_settings/#customise-settings-sources
    """

    def __init__(self, settings_cls: Type[BaseSettings]):
        super().__init__(settings_cls)
        self.settings_cls = settings_cls
        self.profiles_path = _get_profiles_path()
        self.profile_settings = self._load_profile_settings()

    def _load_profile_settings(self) -> Dict[str, Any]:
        """Helper method to load the profile settings from the profiles.toml file"""

        if not self.profiles_path.exists():
            return {}

        try:
            all_profile_data = toml.load(self.profiles_path)
        except toml.TomlDecodeError:
            warnings.warn(
                f"Failed to load profiles from {self.profiles_path}. Please ensure the file is valid TOML."
            )
            return {}

        if (
            sys.argv[0].endswith("/prefect")
            and len(sys.argv) >= 3
            and sys.argv[1] == "--profile"
        ):
            active_profile = sys.argv[2]

        else:
            active_profile = os.environ.get("PREFECT_PROFILE") or all_profile_data.get(
                "active"
            )

        profiles_data = all_profile_data.get("profiles", {})

        if not active_profile or active_profile not in profiles_data:
            return {}
        return profiles_data[active_profile]

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> Tuple[Any, str, bool]:
        """Concrete implementation to get the field value from the profile settings"""
        if field.validation_alias:
            if isinstance(field.validation_alias, str):
                value = self.profile_settings.get(field.validation_alias.upper())
                if value is not None:
                    return value, field_name, self.field_is_complex(field)
            elif isinstance(field.validation_alias, AliasChoices):
                for alias in field.validation_alias.choices:
                    if not isinstance(alias, str):
                        continue
                    value = self.profile_settings.get(alias.upper())
                    if value is not None:
                        return value, field_name, self.field_is_complex(field)

        value = self.profile_settings.get(
            f"{self.config.get('env_prefix','')}{field_name.upper()}"
        )
        return value, field_name, self.field_is_complex(field)

    def __call__(self) -> Dict[str, Any]:
        """Called by pydantic to get the settings from our custom source"""
        if _is_test_mode():
            return {}
        profile_settings: Dict[str, Any] = {}
        for field_name, field in self.settings_cls.model_fields.items():
            value, key, is_complex = self.get_field_value(field, field_name)
            if value is not None:
                prepared_value = self.prepare_field_value(
                    field_name, field, value, is_complex
                )
                profile_settings[key] = prepared_value
        return profile_settings


DEFAULT_PREFECT_TOML_PATH = Path("prefect.toml")


class TomlConfigSettingsSourceBase(PydanticBaseSettingsSource, ConfigFileSourceMixin):
    def __init__(self, settings_cls: Type[BaseSettings]):
        super().__init__(settings_cls)
        self.settings_cls = settings_cls
        self.toml_data = {}

    def _read_file(self, path: Path) -> Dict[str, Any]:
        return toml.load(path)

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> Tuple[Any, str, bool]:
        """Concrete implementation to get the field value from toml data"""
        value = self.toml_data.get(field_name)
        if isinstance(value, dict):
            # if the value is a dict, it is likely a nested settings object and a nested
            # source will handle it
            value = None
        return value, field_name, self.field_is_complex(field)

    def __call__(self) -> Dict[str, Any]:
        """Called by pydantic to get the settings from our custom source"""
        toml_setings: Dict[str, Any] = {}
        for field_name, field in self.settings_cls.model_fields.items():
            value, key, is_complex = self.get_field_value(field, field_name)
            if value is not None:
                prepared_value = self.prepare_field_value(
                    field_name, field, value, is_complex
                )
                toml_setings[key] = prepared_value
        return toml_setings


class PrefectTomlConfigSettingsSource(TomlConfigSettingsSourceBase):
    """Custom pydantic settings source to load settings from a prefect.toml file"""

    def __init__(
        self,
        settings_cls: Type[BaseSettings],
    ):
        super().__init__(settings_cls)
        self.toml_file_path = settings_cls.model_config.get(
            "toml_file", DEFAULT_PREFECT_TOML_PATH
        )
        self.toml_data = self._read_files(self.toml_file_path)
        self.toml_table_header = settings_cls.model_config.get(
            "prefect_toml_table_header", tuple()
        )
        for key in self.toml_table_header:
            self.toml_data = self.toml_data.get(key, {})


class PyprojectTomlConfigSettingsSource(TomlConfigSettingsSourceBase):
    """Custom pydantic settings source to load settings from a pyproject.toml file"""

    def __init__(
        self,
        settings_cls: Type[BaseSettings],
    ):
        super().__init__(settings_cls)
        self.toml_file_path = Path("pyproject.toml")
        self.toml_data = self._read_files(self.toml_file_path)
        self.toml_table_header = settings_cls.model_config.get(
            "pyproject_toml_table_header", ("tool", "prefect")
        )
        for key in self.toml_table_header:
            self.toml_data = self.toml_data.get(key, {})


def _is_test_mode() -> bool:
    """Check if the current process is in test mode."""
    return bool(
        os.getenv("PREFECT_TEST_MODE")
        or os.getenv("PREFECT_UNIT_TEST_MODE")
        or os.getenv("PREFECT_TESTING_UNIT_TEST_MODE")
        or os.getenv("PREFECT_TESTING_TEST_MODE")
    )


def _get_profiles_path() -> Path:
    """Helper to get the profiles path"""

    if _is_test_mode():
        return DEFAULT_PROFILES_PATH
    if env_path := os.getenv("PREFECT_PROFILES_PATH"):
        return Path(env_path)
    if not (DEFAULT_PREFECT_HOME / "profiles.toml").exists():
        return DEFAULT_PROFILES_PATH
    return DEFAULT_PREFECT_HOME / "profiles.toml"

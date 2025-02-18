import os
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Type

import dotenv
import toml
from cachetools import TTLCache
from pydantic import AliasChoices
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
)
from pydantic_settings.sources import (
    ENV_FILE_SENTINEL,
    ConfigFileSourceMixin,
    DotenvType,
)

from prefect.settings.constants import DEFAULT_PREFECT_HOME, DEFAULT_PROFILES_PATH
from prefect.utilities.collections import get_from_dict

_file_cache: TTLCache[str, dict[str, Any]] = TTLCache(maxsize=100, ttl=60)


def _read_toml_file(path: Path) -> dict[str, Any]:
    """use ttl cache to cache toml files"""
    modified_time = path.stat().st_mtime
    cache_key = f"toml_file:{path}:{modified_time}"
    if value := _file_cache.get(cache_key):
        return value
    data = toml.load(path)  # type: ignore
    _file_cache[cache_key] = data
    return data


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
        self.env_vars: Mapping[str, str | None]
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


class FilteredDotEnvSettingsSource(DotEnvSettingsSource):
    def __init__(
        self,
        settings_cls: type[BaseSettings],
        env_file: Optional[DotenvType] = ENV_FILE_SENTINEL,
        env_file_encoding: Optional[str] = None,
        case_sensitive: Optional[bool] = None,
        env_prefix: Optional[str] = None,
        env_nested_delimiter: Optional[str] = None,
        env_ignore_empty: Optional[bool] = None,
        env_parse_none_str: Optional[str] = None,
        env_parse_enums: Optional[bool] = None,
        env_blacklist: Optional[List[str]] = None,
    ) -> None:
        super().__init__(
            settings_cls,
            env_file,
            env_file_encoding,
            case_sensitive,
            env_prefix,
            env_nested_delimiter,
            env_ignore_empty,
            env_parse_none_str,
            env_parse_enums,
        )
        self.env_blacklist = env_blacklist
        if self.env_blacklist:
            if isinstance(self.env_vars, dict):
                for key in self.env_blacklist:
                    self.env_vars.pop(key, None)
            else:
                self.env_vars: dict[str, str | None] = {
                    key: value
                    for key, value in self.env_vars.items()  # type: ignore
                    if key.lower() not in env_blacklist
                }


class ProfileSettingsTomlLoader(PydanticBaseSettingsSource):
    """
    Custom pydantic settings source to load profile settings from a toml file.

    See https://docs.pydantic.dev/latest/concepts/pydantic_settings/#customise-settings-sources
    """

    def __init__(self, settings_cls: Type[BaseSettings]):
        super().__init__(settings_cls)
        self.settings_cls = settings_cls
        self.profiles_path: Path = _get_profiles_path()
        self.profile_settings: dict[str, Any] = self._load_profile_settings()

    def _load_profile_settings(self) -> Dict[str, Any]:
        """Helper method to load the profile settings from the profiles.toml file"""
        if not self.profiles_path.exists():
            return self._get_default_profile()

        try:
            all_profile_data = _read_toml_file(self.profiles_path)
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
            return self._get_default_profile()
        return profiles_data[active_profile]

    def _get_default_profile(self) -> Dict[str, Any]:
        """Helper method to get the default profile"""
        default_profile_data = _read_toml_file(DEFAULT_PROFILES_PATH)
        default_profile = default_profile_data.get("active", "ephemeral")
        assert isinstance(default_profile, str)
        return default_profile_data.get("profiles", {}).get(default_profile, {})

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> Tuple[Any, str, bool]:
        """Concrete implementation to get the field value from the profile settings"""
        if field.validation_alias:
            # Use validation alias as the key to ensure profile value does not
            # higher priority sources. Lower priority sources that use the
            # field name can override higher priority sources that use the
            # validation alias as seen in https://github.com/PrefectHQ/prefect/issues/15981
            if isinstance(field.validation_alias, str):
                value = self.profile_settings.get(field.validation_alias.upper())
                if value is not None:
                    return value, field.validation_alias, self.field_is_complex(field)
            elif isinstance(field.validation_alias, AliasChoices):
                value = None
                lowest_priority_alias = next(
                    choice
                    for choice in reversed(field.validation_alias.choices)
                    if isinstance(choice, str)
                )
                for alias in field.validation_alias.choices:
                    if not isinstance(alias, str):
                        continue
                    value = self.profile_settings.get(alias.upper())
                    if value is not None:
                        return (
                            value,
                            lowest_priority_alias,
                            self.field_is_complex(field),
                        )

        name = f"{self.config.get('env_prefix', '')}{field_name.upper()}"
        value = self.profile_settings.get(name)
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
        self.toml_data: dict[str, Any] = {}

    def _read_file(self, path: Path) -> dict[str, Any]:
        return _read_toml_file(path)

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        """Concrete implementation to get the field value from toml data"""
        value = self.toml_data.get(field_name)
        if isinstance(value, dict):
            # if the value is a dict, it is likely a nested settings object and a nested
            # source will handle it
            value = None
        name = field_name
        # Use validation alias as the key to ensure profile value does not
        # higher priority sources. Lower priority sources that use the
        # field name can override higher priority sources that use the
        # validation alias as seen in https://github.com/PrefectHQ/prefect/issues/15981
        if value is not None:
            if field.validation_alias and isinstance(field.validation_alias, str):
                name = field.validation_alias
            elif field.validation_alias and isinstance(
                field.validation_alias, AliasChoices
            ):
                for alias in reversed(field.validation_alias.choices):
                    if isinstance(alias, str):
                        name = alias
                        break
        return value, name, self.field_is_complex(field)

    def __call__(self) -> dict[str, Any]:
        """Called by pydantic to get the settings from our custom source"""
        toml_setings: dict[str, Any] = {}
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
        self.toml_file_path: Path | str | Sequence[Path | str] | None = (
            settings_cls.model_config.get("toml_file", DEFAULT_PREFECT_TOML_PATH)
        )
        self.toml_data: dict[str, Any] = self._read_files(self.toml_file_path)
        self.toml_table_header: tuple[str, ...] = settings_cls.model_config.get(
            "prefect_toml_table_header", tuple()
        )
        for key in self.toml_table_header:
            self.toml_data: dict[str, Any] = self.toml_data.get(key, {})


class PyprojectTomlConfigSettingsSource(TomlConfigSettingsSourceBase):
    """Custom pydantic settings source to load settings from a pyproject.toml file"""

    def __init__(
        self,
        settings_cls: Type[BaseSettings],
    ):
        super().__init__(settings_cls)
        self.toml_file_path: Path = Path("pyproject.toml")
        self.toml_data: dict[str, Any] = self._read_files(self.toml_file_path)
        self.toml_table_header: tuple[str, ...] = settings_cls.model_config.get(
            "pyproject_toml_table_header", ("tool", "prefect")
        )
        for key in self.toml_table_header:
            self.toml_data: dict[str, Any] = self.toml_data.get(key, {})


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
    if dotenv_path := dotenv.dotenv_values(".env").get("PREFECT_PROFILES_PATH"):
        return Path(dotenv_path)
    if toml_path := _get_profiles_path_from_toml("prefect.toml", ["profiles_path"]):
        return Path(toml_path)
    if pyproject_path := _get_profiles_path_from_toml(
        "pyproject.toml", ["tool", "prefect", "profiles_path"]
    ):
        return Path(pyproject_path)

    if os.environ.get("PREFECT_HOME"):
        return Path(os.environ["PREFECT_HOME"]) / "profiles.toml"

    if not (DEFAULT_PREFECT_HOME / "profiles.toml").exists():
        return DEFAULT_PROFILES_PATH
    return DEFAULT_PREFECT_HOME / "profiles.toml"


def _get_profiles_path_from_toml(path: str, keys: List[str]) -> Optional[str]:
    """Helper to get the profiles path from a toml file."""

    try:
        toml_data = _read_toml_file(Path(path))
    except FileNotFoundError:
        return None

    return get_from_dict(toml_data, keys)

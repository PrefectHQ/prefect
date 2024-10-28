import inspect
import os
from functools import cache
from typing import Any, Dict, Optional, Set, Type, get_args

from pydantic import AliasChoices
from pydantic_settings import BaseSettings
from typing_extensions import Self

from prefect.settings.base import PrefectBaseSettings
from prefect.settings.constants import _SECRET_TYPES
from prefect.settings.context import get_current_settings
from prefect.settings.models.root import Settings


class Setting:
    """Mimics the old Setting object for compatibility with existing code."""

    def __init__(
        self, name: str, default: Any, type_: Any, accessor: Optional[str] = None
    ):
        self._name = name
        self._default = default
        self._type = type_
        if accessor is None:
            self.accessor = _env_var_to_accessor(name)
        else:
            self.accessor = accessor

    @property
    def name(self):
        return self._name

    @property
    def is_secret(self):
        if self._type in _SECRET_TYPES:
            return True
        for secret_type in _SECRET_TYPES:
            if secret_type in get_args(self._type):
                return True
        return False

    def default(self):
        return self._default

    def value(self: Self) -> Any:
        if (
            self.name == "PREFECT_TEST_SETTING"
            or self.name == "PREFECT_TESTING_TEST_SETTING"
        ):
            if (
                "PREFECT_TEST_MODE" in os.environ
                or "PREFECT_TESTING_TEST_MODE" in os.environ
            ):
                return get_current_settings().testing.test_setting
            else:
                return None

        return self.value_from(get_current_settings())

    def value_from(self: Self, settings: "Settings") -> Any:
        path = self.accessor.split(".")
        current_value = settings
        for key in path:
            current_value = getattr(current_value, key, None)
        if isinstance(current_value, _SECRET_TYPES):
            return current_value.get_secret_value()
        return current_value

    def __bool__(self) -> bool:
        return bool(self.value())

    def __str__(self) -> str:
        return str(self.value())

    def __repr__(self) -> str:
        return f"<{self.name}: {self._type!r}>"

    def __eq__(self, __o: object) -> bool:
        return __o.__eq__(self.value())

    def __hash__(self) -> int:
        return hash((type(self), self.name))


def _env_var_to_accessor(env_var: str) -> str:
    """
    Convert an environment variable name to a settings accessor.
    """
    if (field := _get_settings_fields(Settings).get(env_var)) is not None:
        return field.accessor
    return env_var.replace("PREFECT_", "").lower()


@cache
def _get_valid_setting_names(cls: type[BaseSettings]) -> Set[str]:
    """
    A set of valid setting names, e.g. "PREFECT_API_URL" or "PREFECT_API_KEY".
    """
    settings_fields = set()
    for field_name, field in cls.model_fields.items():
        if inspect.isclass(field.annotation) and issubclass(
            field.annotation, PrefectBaseSettings
        ):
            settings_fields.update(_get_valid_setting_names(field.annotation))
        else:
            if field.validation_alias and isinstance(
                field.validation_alias, AliasChoices
            ):
                for alias in field.validation_alias.choices:
                    if not isinstance(alias, str):
                        continue
                    settings_fields.add(alias.upper())
            else:
                settings_fields.add(
                    f"{cls.model_config.get('env_prefix')}{field_name.upper()}"
                )
    return settings_fields


@cache
def _get_settings_fields(
    settings: Type[BaseSettings], accessor_prefix: Optional[str] = None
) -> Dict[str, "Setting"]:
    """Get the settings fields for the settings object"""
    settings_fields: Dict[str, Setting] = {}
    for field_name, field in settings.model_fields.items():
        if inspect.isclass(field.annotation) and issubclass(
            field.annotation, PrefectBaseSettings
        ):
            accessor = (
                field_name
                if accessor_prefix is None
                else f"{accessor_prefix}.{field_name}"
            )
            settings_fields.update(_get_settings_fields(field.annotation, accessor))
        else:
            accessor = (
                field_name
                if accessor_prefix is None
                else f"{accessor_prefix}.{field_name}"
            )
            if field.validation_alias and isinstance(
                field.validation_alias, AliasChoices
            ):
                for alias in field.validation_alias.choices:
                    if not isinstance(alias, str):
                        continue
                    setting = Setting(
                        name=alias.upper(),
                        default=field.default,
                        type_=field.annotation,
                        accessor=accessor,
                    )
                    settings_fields[setting.name] = setting
                    settings_fields[setting.accessor] = setting
            else:
                setting = Setting(
                    name=f"{settings.model_config.get('env_prefix')}{field_name.upper()}",
                    default=field.default,
                    type_=field.annotation,
                    accessor=accessor,
                )
                settings_fields[setting.name] = setting
                settings_fields[setting.accessor] = setting

    return settings_fields

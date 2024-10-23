"""
Prefect settings are defined using `BaseSettings` from `pydantic_settings`. `BaseSettings` can load setting values
from system environment variables and each additionally specified `env_file`.

The recommended user-facing way to access Prefect settings at this time is to import specific setting objects directly,
like `from prefect.settings import PREFECT_API_URL; print(PREFECT_API_URL.value())`.

Importantly, we replace the `callback` mechanism for updating settings with an "after" model_validator that updates dependent settings.
After https://github.com/pydantic/pydantic/issues/9789 is resolved, we will be able to define context-aware defaults
for settings, at which point we will not need to use the "after" model_validator.
"""

from prefect.settings.legacy import (
    Setting,
    _get_settings_fields,
    _get_valid_setting_names,
)
from prefect.settings.models.root import Settings

from prefect.settings.profiles import (
    Profile,
    ProfilesCollection,
    load_current_profile,
    update_current_profile,
    load_profile,
    save_profiles,
    load_profiles,
)
from prefect.settings.context import get_current_settings, temporary_settings
from prefect.settings.constants import DEFAULT_PROFILES_PATH

############################################################################
# Allow traditional env var access


def __getattr__(name: str) -> Setting:
    if name in _get_valid_setting_names(Settings):
        return _get_settings_fields(Settings)[name]
    raise AttributeError(f"{name} is not a Prefect setting.")


__all__ = [  # noqa: F822
    "Profile",
    "ProfilesCollection",
    "Setting",
    "Settings",
    "load_current_profile",
    "update_current_profile",
    "load_profile",
    "save_profiles",
    "load_profiles",
    "get_current_settings",
    "temporary_settings",
    "DEFAULT_PROFILES_PATH",
    # add public settings here for auto-completion
    "PREFECT_API_KEY",  # type: ignore
    "PREFECT_API_URL",  # type: ignore
    "PREFECT_UI_URL",  # type: ignore
]

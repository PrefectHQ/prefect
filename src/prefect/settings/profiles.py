from __future__ import annotations

import warnings
from pathlib import Path
from typing import (
    Annotated,
    Any,
    ClassVar,
    Iterable,
    Iterator,
    Optional,
)

import toml
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
)

from prefect.exceptions import ProfileSettingsValidationError
from prefect.settings.constants import DEFAULT_PROFILES_PATH
from prefect.settings.context import get_current_settings
from prefect.settings.legacy import Setting, _get_settings_fields
from prefect.settings.models.root import Settings
from prefect.utilities.collections import set_in_dict


def _cast_settings(
    settings: dict[str | Setting, Any] | Any,
) -> dict[Setting, Any]:
    """For backwards compatibility, allow either Settings objects as keys or string references to settings."""
    if not isinstance(settings, dict):
        raise ValueError("Settings must be a dictionary.")
    casted_settings = {}
    for k, value in settings.items():
        try:
            if isinstance(k, str):
                setting = _get_settings_fields(Settings)[k]
            else:
                setting = k
            casted_settings[setting] = value
        except KeyError as e:
            warnings.warn(f"Setting {e} is not recognized")
            continue
    return casted_settings


############################################################################
# Profiles


class Profile(BaseModel):
    """A user profile containing settings."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="ignore", arbitrary_types_allowed=True
    )

    name: str
    settings: Annotated[dict[Setting, Any], BeforeValidator(_cast_settings)] = Field(
        default_factory=dict
    )
    source: Optional[Path] = None

    def to_environment_variables(self) -> dict[str, str]:
        """Convert the profile settings to a dictionary of environment variables."""
        return {
            setting.name: str(value)
            for setting, value in self.settings.items()
            if value is not None
        }

    def validate_settings(self) -> None:
        """
        Validate all settings in this profile by creating a partial Settings object
        with the nested structure properly constructed using accessor paths.
        """
        if not self.settings:
            return

        nested_settings: dict[str, Any] = {}

        for setting, value in self.settings.items():
            set_in_dict(nested_settings, setting.accessor, value)

        try:
            Settings.model_validate(nested_settings)
        except ValidationError as e:
            errors: list[tuple[Setting, ValidationError]] = []

            for error in e.errors():
                error_path = ".".join(str(loc) for loc in error["loc"])

                for setting in self.settings.keys():
                    if setting.accessor == error_path:
                        errors.append(
                            (
                                setting,
                                ValidationError.from_exception_data(
                                    "ValidationError", [error]
                                ),
                            )
                        )
                        break

            if errors:
                raise ProfileSettingsValidationError(errors)


class ProfilesCollection:
    """ "
    A utility class for working with a collection of profiles.

    Profiles in the collection must have unique names.

    The collection may store the name of the active profile.
    """

    def __init__(self, profiles: Iterable[Profile], active: str | None = None) -> None:
        self.profiles_by_name: dict[str, Profile] = {
            profile.name: profile for profile in profiles
        }
        self.active_name = active

    @property
    def names(self) -> set[str]:
        """
        Return a set of profile names in this collection.
        """
        return set(self.profiles_by_name.keys())

    @property
    def active_profile(self) -> Profile | None:
        """
        Retrieve the active profile in this collection.
        """
        if self.active_name is None:
            return None
        return self[self.active_name]

    def set_active(self, name: str | None, check: bool = True) -> None:
        """
        Set the active profile name in the collection.

        A null value may be passed to indicate that this collection does not determine
        the active profile.
        """
        if check and name is not None and name not in self.names:
            raise ValueError(f"Unknown profile name {name!r}.")
        self.active_name = name

    def update_profile(
        self,
        name: str,
        settings: dict[Setting, Any],
        source: Path | None = None,
    ) -> Profile:
        """
        Add a profile to the collection or update the existing on if the name is already
        present in this collection.

        If updating an existing profile, the settings will be merged. Settings can
        be dropped from the existing profile by setting them to `None` in the new
        profile.

        Returns the new profile object.
        """
        existing = self.profiles_by_name.get(name)

        # Convert the input to a `Profile` to cast settings to the correct type
        profile = Profile(name=name, settings=settings, source=source)

        if existing:
            new_settings = {**existing.settings, **profile.settings}

            # Drop null keys to restore to default
            for key, value in tuple(new_settings.items()):
                if value is None:
                    new_settings.pop(key)

            new_profile = Profile(
                name=profile.name,
                settings=new_settings,
                source=source or profile.source,
            )
        else:
            new_profile = profile

        self.profiles_by_name[new_profile.name] = new_profile

        return new_profile

    def add_profile(self, profile: Profile) -> None:
        """
        Add a profile to the collection.

        If the profile name already exists, an exception will be raised.
        """
        if profile.name in self.profiles_by_name:
            raise ValueError(
                f"Profile name {profile.name!r} already exists in collection."
            )

        self.profiles_by_name[profile.name] = profile

    def remove_profile(self, name: str) -> None:
        """
        Remove a profile from the collection.
        """
        self.profiles_by_name.pop(name)

    def without_profile_source(self, path: Path | None) -> "ProfilesCollection":
        """
        Remove profiles that were loaded from a given path.

        Returns a new collection.
        """
        return ProfilesCollection(
            [
                profile
                for profile in self.profiles_by_name.values()
                if profile.source != path
            ],
            active=self.active_name,
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to a dictionary suitable for writing to disk.
        """
        return {
            "active": self.active_name,
            "profiles": {
                profile.name: profile.to_environment_variables()
                for profile in self.profiles_by_name.values()
            },
        }

    def __getitem__(self, name: str) -> Profile:
        return self.profiles_by_name[name]

    def __iter__(self) -> Iterator[str]:
        return self.profiles_by_name.__iter__()

    def items(self) -> list[tuple[str, Profile]]:
        return list(self.profiles_by_name.items())

    def __eq__(self, __o: object) -> bool:
        if not isinstance(__o, ProfilesCollection):
            return False

        return (
            self.profiles_by_name == __o.profiles_by_name
            and self.active_name == __o.active_name
        )

    def __repr__(self) -> str:
        return (
            f"ProfilesCollection(profiles={list(self.profiles_by_name.values())!r},"
            f" active={self.active_name!r})>"
        )


def _read_profiles_from(path: Path) -> ProfilesCollection:
    """
    Read profiles from a path into a new `ProfilesCollection`.

    Profiles are expected to be written in TOML with the following schema:
        ```
        active = <name: Optional[str]>

        [profiles.<name: str>]
        <SETTING: str> = <value: Any>
        ```
    """
    contents = toml.loads(path.read_text())
    active_profile = contents.get("active")
    raw_profiles = contents.get("profiles", {})

    profiles = []
    for name, settings in raw_profiles.items():
        profiles.append(Profile(name=name, settings=settings, source=path))

    return ProfilesCollection(profiles, active=active_profile)


def _write_profiles_to(path: Path, profiles: ProfilesCollection) -> None:
    """
    Write profiles in the given collection to a path as TOML.

    Any existing data not present in the given `profiles` will be deleted.
    """
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(mode=0o600)
    path.write_text(toml.dumps(profiles.to_dict()))


def load_profiles(include_defaults: bool = True) -> ProfilesCollection:
    """
    Load profiles from the current profile path. Optionally include profiles from the
    default profile path.
    """
    current_settings = get_current_settings()
    default_profiles = _read_profiles_from(DEFAULT_PROFILES_PATH)

    if current_settings.profiles_path is None:
        raise RuntimeError(
            "No profiles path set; please ensure `PREFECT_PROFILES_PATH` is set."
        )

    if not include_defaults:
        if not current_settings.profiles_path.exists():
            return ProfilesCollection([])
        return _read_profiles_from(current_settings.profiles_path)

    user_profiles_path = current_settings.profiles_path
    profiles = default_profiles
    if user_profiles_path.exists():
        user_profiles = _read_profiles_from(user_profiles_path)

        # Merge all of the user profiles with the defaults
        for name in user_profiles:
            if not (source := user_profiles[name].source):
                raise ValueError(f"Profile {name!r} has no source.")
            profiles.update_profile(
                name,
                settings=user_profiles[name].settings,
                source=source,
            )

        if user_profiles.active_name:
            profiles.set_active(user_profiles.active_name, check=False)

    return profiles


def load_current_profile() -> Profile:
    """
    Load the current profile from the default and current profile paths.

    This will _not_ include settings from the current settings context. Only settings
    that have been persisted to the profiles file will be saved.
    """
    import prefect.context

    profiles = load_profiles()
    context = prefect.context.get_settings_context()

    if context:
        profiles.set_active(context.profile.name)

    return profiles.active_profile


def save_profiles(profiles: ProfilesCollection) -> None:
    """
    Writes all non-default profiles to the current profiles path.
    """
    profiles_path = get_current_settings().profiles_path
    assert profiles_path is not None, "Profiles path is not set."
    profiles = profiles.without_profile_source(DEFAULT_PROFILES_PATH)
    return _write_profiles_to(profiles_path, profiles)


def load_profile(name: str) -> Profile:
    """
    Load a single profile by name.
    """
    profiles = load_profiles()
    try:
        return profiles[name]
    except KeyError:
        raise ValueError(f"Profile {name!r} not found.")


def update_current_profile(
    settings: dict[str | Setting, Any],
) -> Profile:
    """
    Update the persisted data for the profile currently in-use.

    If the profile does not exist in the profiles file, it will be created.

    Given settings will be merged with the existing settings as described in
    `ProfilesCollection.update_profile`.

    Returns:
        The new profile.
    """
    import prefect.context

    current_profile = prefect.context.get_settings_context().profile

    if not current_profile:
        from prefect.exceptions import MissingProfileError

        raise MissingProfileError("No profile is currently in use.")

    profiles = load_profiles()

    # Ensure the current profile's settings are present
    profiles.update_profile(current_profile.name, current_profile.settings)
    # Then merge the new settings in
    new_profile = profiles.update_profile(
        current_profile.name, _cast_settings(settings)
    )

    new_profile.validate_settings()

    save_profiles(profiles)

    return profiles[current_profile.name]

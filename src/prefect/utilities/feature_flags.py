"""
Support for feature flags that enable experimental behavior in Prefect.

For more guidance, read the [Feature Flags](/contributing/feature_flags/) documentation.
"""
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional

import yaml
from flipper import Condition, FeatureFlagClient, MemoryFeatureFlagStore
from flipper.bucketing.base import AbstractBucketer
from flipper.flag import FeatureFlag
from pydantic import BaseModel, Field, ValidationError

from prefect import settings
from prefect.logging import get_logger
from prefect.settings import PREFECT_FEATURE_FLAGGING_SETTINGS_PATH

# This path will be used if `PREFECT_FEATURE_FLAGGING_SETTINGS_PATH` is null.
from prefect.utilities.importtools import from_qualified_name

logger = get_logger("feature_flags")

DEFAULT_FEATURE_FLAGGING_SETTINGS_PATH = Path(__file__).parent / "feature_flags.yml"
DEFAULT_FEATURE_FLAG_FACTORY = (
    "prefect.utilities.feature_flags.get_default_feature_flagger"
)

_flagger: Optional["FeatureFlagger"] = None
_config: Optional["FeatureFlaggingConfigSchema"] = None


class FeatureFlagSchema(BaseModel):
    is_enabled: bool


class FeatureFlaggingConfigSchema(BaseModel):
    version: int
    flagger_factory: Optional[str] = Field(DEFAULT_FEATURE_FLAG_FACTORY)
    flags: Optional[Dict[str, FeatureFlagSchema]]


class FeatureFlagger(FeatureFlagClient):
    def create(
        self,
        flag_name: str,
        is_enabled: bool = False,
        client_data: Optional[dict] = None,
        bucketer: Optional[AbstractBucketer] = None,
        conditions: Optional[Iterable[Condition]] = None,
    ) -> Optional[FeatureFlag]:
        """
        Create a feature flag if a flag matching the given name does not
        already exist.

        Args:
            flag_name: The name of the feature flag.
            is_enabled: the initial enabled/disabled state of the flag if
                        this function creates it
            client_data: arbitrary data that we should store with the flag
            bucketer: an optional "bucketer" from the `flipper` module, e.g.
                      `PercentageBucketer`, to use when determining if the
                      flag is enabled
            conditions: an optional iterable of `Condition` instances from the
                        `flipper` module against which we will check input data
                        to determine if a flag is enabled

        Returns:
            `FeatureFlag` or None: Returns a created or existing flag or None
                                   if feature flagging is disabled.
        """

        if not settings.PREFECT_FEATURE_FLAGGING_ENABLED.value():
            return

        # If the flag exists in the feature flag store, we'll consider the
        # enabled state, bucketer, and conditions currently saved in the
        # feature flag store as canonical.
        if super().exists(flag_name):
            return super().get(flag_name)

        flag = super().create(flag_name, is_enabled=is_enabled, client_data=client_data)

        if bucketer:
            flag.set_bucketer(bucketer)

        if conditions:
            flag.set_conditions(conditions)

        return flag

    def exists(self, flag_name: str):
        """
        Check if a feature flag exists.

        This function always returns False if the setting
        `PREFECT_CLOUD_ENABLE_FEATURE_FLAGGING` is false.

        Args:
            flag_name: the name of the feature flag

        Returns:
            bool: whether the flag exists
        """
        if not settings.PREFECT_FEATURE_FLAGGING_ENABLED.value():
            return False

        return super().exists(flag_name)

    def is_enabled(
        self, flag_name: str, default=False, **conditions: Optional[Any]
    ) -> bool:
        """
        Check if a feature flag is enabled.

        This function always returns False if the setting
        `PREFECT_CLOUD_ENABLE_FEATURE_FLAGGING` is false.

        NOTE: If `flag_is_enabled()` is called for a feature that has
        conditions, but the caller does not give any conditions, the
        current state of the flag is returned.

        Args:
            flag_name: the name of the feature flag
            default: the default return value to use if no feature flag with
                     the given name exists. Defaults to False.
            conditions: keyword arguments, e.g. `is_admin=True`, to check
                        against any Conditions on the flag

        Returns:
            bool: whether the flag is enabled
        """
        if not settings.PREFECT_FEATURE_FLAGGING_ENABLED.value():
            return False

        return super().is_enabled(flag_name, default=default, **conditions)

    def get(self, flag_name: str) -> Optional[FeatureFlag]:
        """
        Get a feature flag by name.

        This function always returns None if the setting
        `PREFECT_CLOUD_ENABLE_FEATURE_FLAGGING` is false.

        Args:
            flag_name: the name of the feature flag

        Returns:
            FeatureFlag: the feature flag
        """

        if not settings.PREFECT_FEATURE_FLAGGING_ENABLED.value():
            return

        return super().get(flag_name)

    def all(self, batch_size: int = 10) -> Iterator[FeatureFlag]:
        """
        List all feature flags.

        This function always returns an empty list if the setting
        `PREFECT_CLOUD_ENABLE_FEATURE_FLAGGING` is false.

        Args:
            batch_size: batch size of flags to retrieve at a time
            offset: the item number (zero-based) within the results to start
                    pagination

        Returns:
            List[FeatureFlag]: list of all feature flags in the store
        """
        if not settings.PREFECT_FEATURE_FLAGGING_ENABLED.value():
            return []

        flags = []
        offset = 0

        while True:
            batch = list(self.list(limit=batch_size, offset=offset))

            if not batch:
                break

            flags.extend(batch)
            offset += batch_size

        return flags


def get_default_feature_flagger() -> FeatureFlagger:
    """
    Return the default feature flagger.

    The default feature flagger uses an in-memory flag store.

    Once the feature flag
    """
    global _flagger

    if _flagger:
        return _flagger

    with threading.Lock():
        _flagger = FeatureFlagger(MemoryFeatureFlagStore())

    return _flagger


def _make_simple_validation_errors(errors: List[Dict[Any, Any]]):
    """Create a simplified list of Pydantic validation errors."""
    _errors = []
    for error in errors:
        config_field = error["loc"][0]
        message = error["msg"]
        _errors += [f"{config_field!r}: {message}"]
    return _errors


def get_flagging_config() -> FeatureFlaggingConfigSchema:
    """
    Return the feature flagging configuration.

    If the configuration has not been loaded, read the contents of the feature
    flagging configuration file and parse it from YAML into a Python dictionary.

    Once the configuration is parsed, this function will return the same
    configuration dictionary every time it's called.
    """
    global _config

    if _config:
        return _config

    path = (
        PREFECT_FEATURE_FLAGGING_SETTINGS_PATH.value()
        if PREFECT_FEATURE_FLAGGING_SETTINGS_PATH.value().exists()
        else DEFAULT_FEATURE_FLAGGING_SETTINGS_PATH
    )

    parsed_config = yaml.safe_load(path.read_text())
    error_prefix = "Could not parse feature flag configuration file"

    if not parsed_config:
        raise RuntimeError(f"{error_prefix}: the file is empty")
    elif not isinstance(parsed_config, dict):
        raise RuntimeError(f"{error_prefix}: the file does not contain any fields")

    try:
        config = FeatureFlaggingConfigSchema.parse_obj(parsed_config)
    except ValidationError as exc:
        errors = _make_simple_validation_errors(exc.errors())
        raise RuntimeError(f"{error_prefix}: {', '.join(errors)}")

    with threading.Lock():
        _config = config

    return _config


def get_flagger() -> FeatureFlagger:
    """
    Return a feature flagger.

    If the flagger hasn't been initialized, use the function specified in the
    "flagger_factory" attribute in the feature flags configuration file to
    create a new flagger instance and return that.

    Once a flagger is initialized, this function will return the same instance
    every time it's called.
    """
    global _flagger

    if _flagger:
        return _flagger

    config = get_flagging_config()
    flagger_factory = from_qualified_name(config.flagger_factory)
    flagger = flagger_factory()

    with threading.Lock():
        _flagger = flagger

    return flagger


def setup_feature_flags():
    """
    Loads feature flagging configuration from a path.

    Users can override the configuration file by setting
    `PREFECT_FEATURE_FLAGGING_SETTINGS_PATH`, which should point to a YAML
    file. The format of the file should look like this:

    ```
    # The version of the configuration file format.
    version: 1

    # The function Prefect should call to get the `FeatureFlagger` instance
    # to use for flagging, in dotted notation (package.module.function).
    flagger_factory: my_package.my_module.my_function

    # Feature flags that the application should know about. Prefect will use
    # the key you specify here as the flag's name. Flags can have one supported
    # attribute currently, which is: `is_enabled`. This should either true or
    # false, depending on what state the flag should be in by default.
    flags:
      very-cool-feature:
        is_enabled: false
    ```
    """
    flagger = get_flagger()
    config = get_flagging_config()

    if config.flags:
        for flag, flag_settings in config.flags.items():
            flagger.create(flag, is_enabled=flag_settings.is_enabled)

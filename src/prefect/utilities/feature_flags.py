"""
Support for feature flags enabling experimental behavior in Prefect.

For more guidance, read the [Feature Flags](/contributing/feature_flags/) documentation.
"""
import threading
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

import yaml
from flipper import Condition, FeatureFlagClient, MemoryFeatureFlagStore
from flipper.bucketing.base import AbstractBucketer
from flipper.flag import FeatureFlag

from prefect import settings
from prefect.settings import PREFECT_FEATURE_FLAGGING_SETTINGS_PATH

# This path will be used if `PREFECT_FEATURE_FLAGGING_SETTINGS_PATH` is null.
from prefect.utilities.importtools import from_qualified_name

DEFAULT_FEATURE_FLAGGING_SETTINGS_PATH = Path(__file__).parent / "feature_flags.yml"

_in_memory_store: Optional[MemoryFeatureFlagStore] = None
_flagger: Optional["FeatureFlagger"] = None
_config: Optional[dict] = None


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
            `FeatureFlag` or None: Returns a created or existing flag
                                           or None if feature flagging is
                                           disabled.
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
    global _in_memory_store

    if not _in_memory_store:
        with threading.Lock():
            _in_memory_store = MemoryFeatureFlagStore()

    set_flagger(FeatureFlagger(_in_memory_store))

    return _flagger


def set_flagger(flagger: FeatureFlagger):
    global _flagger

    with threading.Lock():
        _flagger = flagger


def get_flagging_config():
    global _config

    if _config:
        return _config

    path = (
        PREFECT_FEATURE_FLAGGING_SETTINGS_PATH.value()
        if PREFECT_FEATURE_FLAGGING_SETTINGS_PATH.value().exists()
        else DEFAULT_FEATURE_FLAGGING_SETTINGS_PATH
    )

    _config = yaml.safe_load(path.read_text())
    return _config


def get_flagger() -> FeatureFlagger:
    global _flagger

    if _flagger:
        return _flagger

    config = get_flagging_config()
    qualified_flagger_factory = config["flagger_factory"]

    flagger_factory = from_qualified_name(qualified_flagger_factory)
    flagger = flagger_factory()

    set_flagger(flagger)
    return flagger


def setup_feature_flags():
    """
    Loads logging configuration from a path allowing override from the environment
    """
    flagger = get_flagger()
    config = get_flagging_config()

    if config["flags"]:
        for flag, flag_settings in config["flags"].items():
            flagger.create(flag, is_enabled=flag_settings["is_enabled"])

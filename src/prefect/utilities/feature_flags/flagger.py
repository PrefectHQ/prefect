"""
This module contains feature flagging utilities.

For more guidance, read the [Feature Flags](/contributing/feature_flags/) documentation.
"""
from typing import Any, Iterable, Iterator, Optional

from flipper import Condition, FeatureFlagClient
from flipper.bucketing.base import AbstractBucketer
from flipper.flag import FeatureFlag

from prefect import settings


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


# Feature flags currently in use go here.
#
# Flags should follow the naming pattern of {ENABLE/DISABLE}_{FEATURE_NAME}.
# The UI consumes some of these via `/api/flags` so that features can
# simultaneously be toggled on and off between the API and the UI.
#
# For example, to create a new feature flag called "enable-cool_feature",
# you would add a variable that contains the flag and call
# `create_if_missing()` like so:
#
# ENABLE_COOL_FEATURE = "very-cool-feature"
# create_if_missing(ENABLE_COOL_FEATURE)

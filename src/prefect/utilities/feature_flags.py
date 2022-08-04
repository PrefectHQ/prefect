"""
This module contains code related to feature flagging.

For more guidance, read docs/feature_flags.md.
"""
import functools
from typing import Any, Iterable, Optional, List

from flipper import (
    Condition,
    FeatureFlagClient,
    MemoryFeatureFlagStore
)
from flipper.bucketing.base import AbstractBucketer
from flipper.flag import FeatureFlag

from prefect import settings


@functools.cache
def get_features_client() -> FeatureFlagClient:
    store = MemoryFeatureFlagStore()
    return FeatureFlagClient(store)


def create_if_missing(
    flag_name: str,
    is_enabled: bool = False,
    client_data: Optional[dict] = None,
    bucketer: Optional[AbstractBucketer] = None,
    conditions: Optional[Iterable[Condition]] = None,
    client: FeatureFlagClient = None
) -> Optional[FeatureFlag]:
    """
    Create a feature flag if a flag matching the given name does not
    already exist.

    Args:
        flag_name: the name of the feature flag
        is_enabled: the initial enabled/disabled state of the flag if
                    this function creates it
        client_data: arbitrary data that we should store with the flag
        bucketer: an optional bucketer from the flipper.bucketing module, e.g.
                  PercentageBucketer, to use when determining if the flag
                  is enabled
        conditions: an optional iterable of Conditions against which we will
                    check input data to determine if a flag is enabled
        client: The FeatureFlagClient instance to use. Defaults to a client
                configured to look at an in-memory feature store.

    Returns:
        FeatureFlag or None: Returns the new FeatureFlag if one did not
                             exist with this name already or None if the
                             flag already existed.
    """
    if not settings.PREFECT_FEATURE_FLAGGING_ENABLED.value():
        return

    if not client:
        client = get_features_client()

    # If the feature flag exists, we'll consider the state of the flag
    # in the feature flag store as canonical.
    if client.get(flag_name).exists():
        return

    flag = client.create(flag_name, is_enabled=is_enabled, client_data=client_data)

    if bucketer:
        flag.set_bucketer(bucketer)

    if conditions:
        flag.set_conditions(conditions)

    return flag


def flag_is_enabled(flag_name: str, default=False, client: FeatureFlagClient = None, **conditions: Optional[Any]):
    """
    Check if a feature flag is enabled.

    This function always returns False if the setting
    PREFECT_CLOUD_ENABLE_FEATURE_FLAGGING is false.

    NOTE: If `flag_is_enabled()` is called for a feature that has conditions,
    but the caller does not give any conditions, the current state of the flag
    is returned.

    Args:
        flag_name: the name of the feature flag
        default: the default return value to use if no feature flag with
                 the given name exists. Defaults to False.
        client: The FeatureFlagClient instance to use. Defaults to a client
                configured to look at an in-memory feature store.
        conditions: keyword arguments, e.g. is_admin=True, to check
                    against any Conditions on the flag

    Returns:
        bool: whether the flag is enabled
    """
    if not settings.PREFECT_FEATURE_FLAGGING_ENABLED.value():
        return False

    if not client:
        client = get_features_client()

    return client.is_enabled(flag_name, default=default, **conditions)


def list_feature_flags(batch_size: int = 10, client: FeatureFlagClient = None) -> List[FeatureFlag]:
    """
    List all feature flags.

    This function always returns an empty list if the setting
    PREFECT_CLOUD_ENABLE_FEATURE_FLAGGING is false.

    Args:
        batch_size: batch size of flags to retrieve at a time
        client: The FeatureFlagClient instance to use. Defaults to a client
                configured to look at an in-memory feature store.

    Returns:
        list[FeatureFlag]: list of all feature flags
    """
    if not settings.PREFECT_FEATURE_FLAGGING_ENABLED.value():
        return []

    if not client:
        client = get_features_client()

    flags = []
    offset = 0

    while True:
        batch = list(client.list(limit=batch_size, offset=offset))

        if not batch:
            break

        flags.extend(batch)
        offset += batch_size

    return flags


# Current in-use feature flags go here.
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
# create_if_missing(ENABLE_MY_NEW_FLAG)

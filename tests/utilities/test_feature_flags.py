import pytest
from flipper import Condition, FeatureFlagClient

from prefect.settings import PREFECT_FEATURE_FLAGGING_ENABLED, temporary_settings
from prefect.utilities.feature_flags import (
    create_if_missing,
    flag_is_enabled,
    get_features_client,
    list_feature_flags,
)


@pytest.fixture()
def features() -> FeatureFlagClient:
    """A feature flag client fixture for working with feature flags in the test suite"""
    return get_features_client()


@pytest.fixture(autouse=True)
def delete_test_flags(features: FeatureFlagClient):
    for flag in features.list():
        features.destroy(flag.name)


def test_creates_missing_flag(
    features: FeatureFlagClient,
):
    name = "test"

    assert features.exists(name) is False

    with temporary_settings({PREFECT_FEATURE_FLAGGING_ENABLED: "true"}):
        flag = create_if_missing(name)
        assert flag.name == name
        assert features.exists(name) is True


def test_create_ignores_existing_flag():
    with temporary_settings({PREFECT_FEATURE_FLAGGING_ENABLED: "true"}):
        # Create a disabled flag.
        flag = create_if_missing("test")
        assert flag.name == "test"

        # Try to create the same flag, but enabled -- this should return a
        # FeatureFlag instance that reports it is disabled.
        flag = create_if_missing("test")
        assert flag.is_enabled() is False


def test_create_disabled_flag():
    with temporary_settings({PREFECT_FEATURE_FLAGGING_ENABLED: "true"}):
        flag = create_if_missing("test", is_enabled=False)
        assert flag.name == "test"
        assert flag_is_enabled("test") is False


def test_create_enabled_flag():
    with temporary_settings({PREFECT_FEATURE_FLAGGING_ENABLED: "true"}):
        flag = create_if_missing("test", is_enabled=True)
        assert flag.name == "test"
        assert flag_is_enabled("test") is True


def test_flag_conditions():
    with temporary_settings({PREFECT_FEATURE_FLAGGING_ENABLED: "true"}):
        flag = create_if_missing(
            "test", is_enabled=True, conditions=[Condition(is_admin=True)]
        )
        assert flag.name == "test"

        # Flag is disabled without the necessary condition
        assert flag_is_enabled("test", is_admin=False) is False

        # Flag is enabled with the necessary condition
        assert flag_is_enabled("test", is_admin=True) is True

        # Flag is enabled if no conditions are passed in.
        assert flag_is_enabled("test") is True


def test_list_feature_flags():
    # returns an empty list if the setting is not enabled
    flags = list_feature_flags()
    assert flags == []

    with temporary_settings({PREFECT_FEATURE_FLAGGING_ENABLED: "true"}):
        flag_names = [create_if_missing(f"flag-{i}").name for i in range(5)]

        listed_flags = list_feature_flags()

        assert set(flag_names) == {flag.name for flag in listed_flags}

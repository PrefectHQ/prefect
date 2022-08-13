from typing import Generator

import pytest
from flipper import Condition
from flipper.bucketing import Percentage, PercentageBucketer
from flipper.contrib.memory import MemoryFeatureFlagStore

from prefect.settings import PREFECT_FEATURE_FLAGGING_ENABLED, temporary_settings
from prefect.utilities.feature_flags import FeatureFlagger


@pytest.fixture
def features() -> Generator[FeatureFlagger, None, None]:
    """
    A feature flagger whose flag store exists only for the duration of
    a test run.

    NOTE: Using this fixture in a text activates feature flagging globally
          for the duration of the test.
    """
    yield FeatureFlagger(MemoryFeatureFlagStore())


@pytest.fixture
def enable_flagging(features):
    with temporary_settings({PREFECT_FEATURE_FLAGGING_ENABLED: "true"}):
        yield features


@pytest.fixture
def disable_flagging(features):
    with temporary_settings({PREFECT_FEATURE_FLAGGING_ENABLED: "false"}):
        yield features


@pytest.mark.usefixtures("disable_flagging")
class TestFeatureFlaggingDisabled:
    def test_create(self, features):
        assert features.create("test", is_enabled=True) is None

    def test_exists(self, features):
        features.create("test", is_enabled=True)
        assert features.exists("test") is False

    def test_is_enabled(self, features):
        features.create("test", is_enabled=True)
        assert features.is_enabled("test") is False

    def test_get(self, features):
        features.create("test", is_enabled=True)
        assert features.get("test") is None

    def test_all(self, features):
        flags = features.all()
        assert flags == []


@pytest.mark.usefixtures("enable_flagging")
class TestFeatureFlaggingEnabled:
    def test_create_missing_flag(self, features):
        name = "test"
        assert features.exists(name) is False

        flag = features.create(name)
        assert flag
        assert flag.name == name
        assert features.exists(name) is True

    def test_create_does_not_overwrite_existing_flag_state(self, features):
        # Create a disabled flag.
        flag = features.create("test", is_enabled=False)
        assert flag
        assert flag.name == "test"
        assert flag.is_enabled() is False

        # Try to create the same flag, but enabled. This should return a flag
        # that reports it is disabled because the current state of the existing
        # flag (disabled) is honored.
        flag = features.create("test", is_enabled=True)
        assert flag
        assert flag.is_enabled() is False

    def test_create_disabled_flag(self, features):
        flag = features.create("test", is_enabled=False)
        assert flag
        assert flag.name == "test"
        assert features.is_enabled("test", client=features) is False

    def test_create_enabled_flag(self, features):
        flag = features.create("test", is_enabled=True)
        assert flag
        assert flag.name == "test"
        assert features.is_enabled("test") is True

    def test_flag_conditions(self, features):
        """
        NOTE: The upstream library tests this behavior, but verifying it
              here gives useful information about how to use conditions.
        """
        flag = features.create(
            "test", is_enabled=True, conditions=[Condition(is_admin=True)]
        )
        assert flag
        assert flag.name == "test"

        # Flag is disabled without the necessary condition
        assert features.is_enabled("test", is_admin=False) is False

        # Flag is enabled with the necessary condition
        assert features.is_enabled("test", is_admin=True) is True

        # Flag is enabled if no conditions are passed in.
        assert features.is_enabled("test") is True

    def test_flag_bucketer(self, features):
        """
        Like conditions, bucket behavior is tested by the upstream library.
        Unlike conditions, buckets work without any interaction with the
        caller, so we have less of a need for usage examples. We'll only
        make sure we assigned the bucket correctly.
        """
        flag = features.create(
            "test", is_enabled=True, bucketer=PercentageBucketer(Percentage(0.5))
        )
        assert flag

        assert flag.get_meta()["bucketer"] == {
            "percentage": {"type": "Percentage", "value": 0.5},
            "type": "PercentageBucketer",
        }

    def test_all_features(self, features):
        flags = {features.create(f"flag-{i}") for i in range(5)}
        flag_names = {flag.name for flag in flags if flag}
        assert len(flag_names) == 5

        all_flags = features.all()
        assert {flag.name for flag in all_flags} == flag_names

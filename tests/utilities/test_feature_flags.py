import sys
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Generator

import pytest
from flipper import Condition
from flipper.bucketing import Percentage, PercentageBucketer
from flipper.contrib.memory import MemoryFeatureFlagStore

from prefect.settings import (
    PREFECT_FEATURE_FLAGGING_ENABLED,
    PREFECT_FEATURE_FLAGGING_SETTINGS_PATH,
    temporary_settings,
)
from prefect.utilities import feature_flags
from prefect.utilities.feature_flags import FeatureFlagger


@pytest.fixture
def features(enable_flagging) -> Generator[FeatureFlagger, None, None]:
    """
    A feature flagger whose flag store exists only for the duration of
    a test run.

    NOTE: Using this fixture in a text activates feature flagging globally
          for the duration of the test.
    """
    yield FeatureFlagger(MemoryFeatureFlagStore())


@pytest.fixture
def enable_flagging():
    with temporary_settings({PREFECT_FEATURE_FLAGGING_ENABLED: "true"}):
        yield


@pytest.fixture
def disable_flagging():
    with temporary_settings({PREFECT_FEATURE_FLAGGING_ENABLED: "false"}):
        yield


@pytest.mark.usefixtures("features", "disable_flagging")
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


@pytest.mark.usefixtures("features", "enable_flagging")
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


class CustomFeatureFlagger(FeatureFlagger):
    pass


def flagger_test_factory():
    return CustomFeatureFlagger(MemoryFeatureFlagStore())


custom_feature_flag_yaml = b"""
version: 1

flagger_factory: tests.utilities.test_feature_flags.flagger_test_factory

flags:
  my-enabled-flag:
    is_enabled: true
    my-disabled-flag:
    is_enabled: false
"""

invalid_feature_flag_yaml = b"""
not_yaml
"""


@pytest.mark.usefixtures("enable_flagging")
class TestFeatureFlaggingLoading:
    def test_loads_yaml_from_file_in_setting(self, features):
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))

        with NamedTemporaryFile() as f:
            f.write(custom_feature_flag_yaml)
            f.seek(0)

            with temporary_settings({PREFECT_FEATURE_FLAGGING_SETTINGS_PATH: f.name}):
                feature_flags._config = None
                feature_flags._flagger = None
                flagger = feature_flags.get_flagger()
                assert isinstance(flagger, CustomFeatureFlagger)

    def test_invalid_yaml_file(self, features):
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))

        with NamedTemporaryFile() as f:
            f.write(invalid_feature_flag_yaml)
            f.seek(0)

            with temporary_settings({PREFECT_FEATURE_FLAGGING_SETTINGS_PATH: f.name}):
                feature_flags._config = None
                feature_flags._flagger = None

                with pytest.raises(RuntimeError) as e:
                    feature_flags.get_flagger()

                assert (
                    "Could not parse feature flag configuration "
                    "file: the file does not contain any fields" in str(e)
                )

    def test_empty_yaml_file(self, features):
        with NamedTemporaryFile() as f:
            f.write(b"")
            f.seek(0)

            with temporary_settings({PREFECT_FEATURE_FLAGGING_SETTINGS_PATH: f.name}):
                feature_flags._config = None
                feature_flags._flagger = None

                with pytest.raises(RuntimeError) as e:
                    feature_flags.get_flagger()

                assert (
                    "Could not parse feature flag configuration file: the file is empty"
                    in str(e)
                )

    def test_get_feature_flagger_returns_same_flagger(self, features):
        feature_flags._flagger = None
        flagger = feature_flags.get_flagger()
        assert flagger == feature_flags.get_flagger()

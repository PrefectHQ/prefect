import os
import textwrap

import pytest

import prefect.settings
from prefect.settings import (
    DEFAULT_PROFILES,
    LoggingSettings,
    Settings,
    load_profile,
    load_profiles,
    write_profiles,
)
from prefect.utilities.testing import temporary_settings


def test_settings():
    assert prefect.settings.from_env().test_mode is True


def test_temporary_settings():
    assert prefect.settings.from_env().test_mode is True
    with temporary_settings(PREFECT_TEST_MODE=False) as new_settings:
        assert new_settings.test_mode is False, "Yields the new settings"
        assert prefect.settings.from_env().test_mode is False, "Loads from env"
        assert prefect.settings.from_context().test_mode is False, "Loads from context"

    assert prefect.settings.from_env().test_mode is True, "Restores old setting"
    assert prefect.settings.from_context().test_mode is True, "Restores old profile"


def test_temporary_settings_restores_on_error():
    assert prefect.settings.from_env().test_mode is True

    with pytest.raises(ValueError):
        with temporary_settings(PREFECT_TEST_MODE=False):
            raise ValueError()

    assert os.environ["PREFECT_TEST_MODE"] == "1", "Restores os environ."
    assert prefect.settings.from_env().test_mode is True, "Restores old setting"
    assert prefect.settings.from_context().test_mode is True, "Restores old profile"


def test_refresh_settings():
    assert prefect.settings.from_env().test_mode is True

    os.environ["PREFECT_TEST_MODE"] = "0"
    new_settings = Settings()
    assert new_settings.test_mode is False


def test_nested_settings():
    assert prefect.settings.from_env().orion.database.echo is False

    os.environ["PREFECT_ORION_DATABASE_ECHO"] = "1"
    new_settings = Settings()
    assert new_settings.orion.database.echo is True


@pytest.mark.parametrize(
    "value,expected",
    [
        ("foo", ["foo"]),
        ("foo,bar", ["foo", "bar"]),
        ("foo, bar, foobar ", ["foo", "bar", "foobar"]),
    ],
)
def test_extra_loggers(value, expected):
    settings = LoggingSettings(extra_loggers=value)
    assert settings.get_extra_loggers() == expected


class TestProfiles:
    @pytest.fixture(autouse=True)
    def temporary_profiles_path(self, tmp_path):
        path = tmp_path / "profiles.toml"
        with temporary_settings(PREFECT_PROFILES_PATH=path):
            yield path

    def test_load_profiles_no_profiles_file(self):
        assert load_profiles() == DEFAULT_PROFILES

    def test_load_profiles_missing_default(self, temporary_profiles_path):
        temporary_profiles_path.write_text(
            textwrap.dedent(
                """
                [foo]
                test = "bar"
                """
            )
        )
        assert load_profiles() == {**DEFAULT_PROFILES, "foo": {"test": "bar"}}

    def test_load_profiles_with_default(self, temporary_profiles_path):
        temporary_profiles_path.write_text(
            textwrap.dedent(
                """
                [default]
                test = "foo"

                [foo]
                test = "bar"
                """
            )
        )
        assert load_profiles() == {"default": {"test": "foo"}, "foo": {"test": "bar"}}

    def test_write_profiles_includes_default(self, temporary_profiles_path):
        write_profiles({})
        assert (
            temporary_profiles_path.read_text()
            == textwrap.dedent(
                """
                [default]
                """
            ).lstrip()
        )

    def test_write_profiles_allows_default_override(self, temporary_profiles_path):
        write_profiles({"default": {"test": "foo"}})
        assert (
            temporary_profiles_path.read_text()
            == textwrap.dedent(
                """
                [default]
                test = "foo"
                """
            ).lstrip()
        )

    def test_write_profiles_additional_profiles(self, temporary_profiles_path):
        write_profiles({"foo": {"test": "bar"}, "foobar": {"test": 1}})
        assert (
            temporary_profiles_path.read_text()
            == textwrap.dedent(
                """
                [default]

                [foo]
                test = "bar"

                [foobar]
                test = 1
                """
            ).lstrip()
        )

    def test_load_profile_default(self):
        assert load_profile("default") == {}

    def test_load_profile_missing(self):
        with pytest.raises(ValueError, match="Profile 'foo' not found."):
            load_profile("foo")

    def test_load_profile(self, temporary_profiles_path):
        temporary_profiles_path.write_text(
            textwrap.dedent(
                """
                [foo]
                test = "bar"
                number = 1
                """
            )
        )
        assert load_profile("foo") == {"test": "bar", "number": "1"}

    def test_load_profile_casts_nested_data_to_strings(self, temporary_profiles_path):
        # Not a suggested pattern, but not banned yet
        temporary_profiles_path.write_text(
            textwrap.dedent(
                """
                [foo]
                test = "bar"
                [foo.nested]
                test = "okay"
                """
            )
        )
        assert load_profile("foo") == {"test": "bar", "nested": "{'test': 'okay'}"}

import os
import textwrap
from pathlib import Path

import pytest

import prefect.context
import prefect.settings
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_URL,
    PREFECT_DEBUG_MODE,
    PREFECT_HOME,
    PREFECT_LOGGING_EXTRA_LOGGERS,
    PREFECT_LOGGING_LEVEL,
    PREFECT_ORION_API_HOST,
    PREFECT_ORION_API_PORT,
    PREFECT_ORION_DATABASE_ECHO,
    PREFECT_ORION_UI_API_URL,
    PREFECT_PROFILES_PATH,
    PREFECT_TEST_MODE,
    Profile,
    ProfilesCollection,
    Settings,
    get_current_settings,
    load_profile,
    load_profiles,
    save_profiles,
    temporary_settings,
    update_profile,
)


class TestSetting_UI_API_URL:
    def test_ui_api_url_from_api_url(self):
        with temporary_settings({PREFECT_API_URL: "http://test/api"}):
            assert PREFECT_ORION_UI_API_URL.value() == "http://test/api"

    def test_ui_api_url_from_orion_host_and_port(self):
        with temporary_settings(
            {PREFECT_ORION_API_HOST: "test", PREFECT_ORION_API_PORT: "1111"}
        ):
            assert PREFECT_ORION_UI_API_URL.value() == "http://test:1111/api"

    def test_ui_api_url_from_defaults(self):
        assert PREFECT_ORION_UI_API_URL.value() == "http://127.0.0.1:4200/api"


def test_get_value_root_setting():
    with temporary_settings(
        updates={PREFECT_API_URL: "test"}
    ):  # Set a value so its not null
        value = prefect.settings.PREFECT_API_URL.value()
        value_of = get_current_settings().value_of(PREFECT_API_URL)
        value_from = PREFECT_API_URL.value_from(get_current_settings())
        assert value == value_of == value_from == "test"


def test_get_value_nested_setting():
    value = prefect.settings.PREFECT_LOGGING_LEVEL.value()
    value_of = get_current_settings().value_of(PREFECT_LOGGING_LEVEL)
    value_from = PREFECT_LOGGING_LEVEL.value_from(get_current_settings())
    assert value == value_of == value_from


def test_settings():
    assert PREFECT_TEST_MODE.value() is True


def test_settings_copy_with_update_does_not_mark_unset_as_set():
    settings = get_current_settings()
    set_keys = set(settings.dict(exclude_unset=True).keys())
    new_settings = settings.copy_with_update()
    new_set_keys = set(new_settings.dict(exclude_unset=True).keys())
    assert new_set_keys == set_keys

    new_settings = settings.copy_with_update(updates={PREFECT_API_KEY: "TEST"})
    new_set_keys = set(new_settings.dict(exclude_unset=True).keys())
    # Only the API key setting should be set
    assert new_set_keys - set_keys == {"PREFECT_API_KEY"}


def test_temporary_settings_does_not_mark_unset_as_set():
    settings = get_current_settings()
    set_keys = set(settings.dict(exclude_unset=True).keys())
    with temporary_settings() as new_settings:
        pass
    new_set_keys = set(new_settings.dict(exclude_unset=True).keys())
    assert new_set_keys == set_keys


def test_settings_copy_with_update():
    settings = get_current_settings()
    assert settings.value_of(PREFECT_TEST_MODE) is True

    with temporary_settings(restore_defaults={PREFECT_API_KEY}):
        new_settings = settings.copy_with_update(
            updates={PREFECT_LOGGING_LEVEL: "ERROR"},
            set_defaults={PREFECT_TEST_MODE: False, PREFECT_API_KEY: "TEST"},
        )
        assert (
            new_settings.value_of(PREFECT_TEST_MODE) is True
        ), "Not changed, existing value was not default"
        assert (
            new_settings.value_of(PREFECT_API_KEY) == "TEST"
        ), "Changed, existing value was default"
        assert new_settings.value_of(PREFECT_LOGGING_LEVEL) == "ERROR"


def test_settings_in_truthy_statements_use_value():
    if PREFECT_TEST_MODE:
        assert True, "Treated as truth"
    else:
        assert False, "Not treated as truth"

    with temporary_settings(updates={PREFECT_TEST_MODE: False}):
        if not PREFECT_TEST_MODE:
            assert True, "Treated as truth"
        else:
            assert False, "Not treated as truth"

    # Test with a non-boolean setting

    if PREFECT_LOGGING_LEVEL:
        assert True, "Treated as truth"
    else:
        assert False, "Not treated as truth"

    with temporary_settings(updates={PREFECT_LOGGING_LEVEL: ""}):
        if not PREFECT_LOGGING_LEVEL:
            assert True, "Treated as truth"
        else:
            assert False, "Not treated as truth"


def test_temporary_settings():
    assert PREFECT_TEST_MODE.value() is True
    with temporary_settings(updates={PREFECT_TEST_MODE: False}) as new_settings:
        assert (
            PREFECT_TEST_MODE.value_from(new_settings) is False
        ), "Yields the new settings"
        assert PREFECT_TEST_MODE.value() is False

    assert PREFECT_TEST_MODE.value() is True


def test_temporary_settings_can_restore_to_defaults_values():
    assert PREFECT_TEST_MODE.value() is True
    with temporary_settings(updates={PREFECT_LOGGING_LEVEL: "ERROR"}):
        with temporary_settings(restore_defaults={PREFECT_LOGGING_LEVEL}):
            assert PREFECT_LOGGING_LEVEL.value() == PREFECT_LOGGING_LEVEL.field.default


def test_temporary_settings_restores_on_error():
    assert PREFECT_TEST_MODE.value() is True

    with pytest.raises(ValueError):
        with temporary_settings(updates={PREFECT_TEST_MODE: False}):
            raise ValueError()

    assert os.environ["PREFECT_TEST_MODE"] == "1", "Does not alter os environ."
    assert PREFECT_TEST_MODE.value() is True


def test_refresh_settings(monkeypatch):
    assert PREFECT_TEST_MODE.value() is True

    monkeypatch.setenv("PREFECT_TEST_MODE", "0")
    new_settings = Settings()
    assert PREFECT_TEST_MODE.value_from(new_settings) is False


def test_nested_settings(monkeypatch):
    assert PREFECT_ORION_DATABASE_ECHO.value() is False

    monkeypatch.setenv("PREFECT_ORION_DATABASE_ECHO", "1")
    new_settings = Settings()
    assert PREFECT_ORION_DATABASE_ECHO.value_from(new_settings) is True


@pytest.mark.parametrize(
    "value,expected",
    [
        ("foo", ["foo"]),
        ("foo,bar", ["foo", "bar"]),
        ("foo, bar, foobar ", ["foo", "bar", "foobar"]),
    ],
)
def test_extra_loggers(value, expected):
    settings = Settings(PREFECT_LOGGING_EXTRA_LOGGERS=value)
    assert PREFECT_LOGGING_EXTRA_LOGGERS.value_from(settings) == expected


def test_prefect_home_expands_tilde_in_path():
    settings = Settings(PREFECT_HOME="~/test")
    assert PREFECT_HOME.value_from(settings) == Path("~/test").expanduser()


class TestProfiles:
    @pytest.fixture(autouse=True)
    def temporary_profiles_path(self, tmp_path):
        path = tmp_path / "profiles.toml"
        with temporary_settings(updates={PREFECT_PROFILES_PATH: path}):
            yield path

    def test_load_profiles_no_profiles_file(self):
        assert load_profiles()

    def test_load_profiles_missing_default(self, temporary_profiles_path):
        temporary_profiles_path.write_text(
            textwrap.dedent(
                """
                [profiles.foo]
                PREFECT_API_KEY = "bar"
                """
            )
        )
        assert load_profiles()["foo"].settings == {PREFECT_API_KEY: "bar"}
        assert isinstance(load_profiles()["default"].settings, dict)

    def test_load_profiles_with_default(self, temporary_profiles_path):
        temporary_profiles_path.write_text(
            textwrap.dedent(
                """
                [profiles.default]
                PREFECT_API_KEY = "foo"

                [profiles.bar]
                PREFECT_API_KEY = "bar"
                """
            )
        )
        assert load_profiles() == ProfilesCollection(
            profiles=[
                Profile(
                    name="default",
                    settings={PREFECT_API_KEY: "foo"},
                    source=temporary_profiles_path,
                ),
                Profile(
                    name="bar",
                    settings={PREFECT_API_KEY: "bar"},
                    source=temporary_profiles_path,
                ),
            ],
            active="default",
        )

    def test_write_profiles_does_not_include_default(self, temporary_profiles_path):
        """
        Including the default has a tendency to bake in settings the user may not want, and
        can prevent them from gaining new defaults.
        """
        save_profiles(ProfilesCollection(active=None, profiles=[]))
        assert "profiles.default" not in temporary_profiles_path.read_text()

    def test_write_profiles_additional_profiles(self, temporary_profiles_path):
        save_profiles(
            ProfilesCollection(
                profiles=[
                    Profile(
                        name="foo",
                        settings={PREFECT_API_KEY: 1},
                        source=temporary_profiles_path,
                    ),
                    Profile(
                        name="bar",
                        settings={PREFECT_API_KEY: 2},
                        source=temporary_profiles_path,
                    ),
                ],
                active=None,
            )
        )
        assert (
            temporary_profiles_path.read_text()
            == textwrap.dedent(
                """
                [profiles.foo]
                PREFECT_API_KEY = 1

                [profiles.bar]
                PREFECT_API_KEY = 2
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
                [profiles.foo]
                PREFECT_API_KEY = "bar"
                PREFECT_DEBUG_MODE = 1
                """
            )
        )
        assert load_profile("foo") == {
            PREFECT_API_KEY: "bar",
            PREFECT_DEBUG_MODE: 1,
        }

    def test_load_profile_does_not_allow_nested_data(self, temporary_profiles_path):
        temporary_profiles_path.write_text(
            textwrap.dedent(
                """
                [profiles.foo]
                PREFECT_API_KEY = "bar"

                [profiles.foo.nested]
                """
            )
        )
        with pytest.raises(ValueError, match="Unknown setting.*'nested'"):
            load_profile("foo")

    def test_load_profile_with_invalid_key(self, temporary_profiles_path):
        temporary_profiles_path.write_text(
            textwrap.dedent(
                """
                [profiles.foo]
                test = "unknown-key"
                """
            )
        )
        with pytest.raises(ValueError, match="Unknown setting.*'test'"):
            load_profile("foo")

    def test_update_profile_adds_key(self, temporary_profiles_path):
        update_profile(name="test", PREFECT_API_URL="hello")
        assert load_profile("test") == {PREFECT_API_URL: "hello"}

    def test_update_profile_updates_key(self, temporary_profiles_path):
        update_profile(name="test", PREFECT_API_URL="hello")
        assert load_profile("test") == {PREFECT_API_URL: "hello"}
        update_profile(name="test", PREFECT_API_URL="goodbye")
        assert load_profile("test") == {PREFECT_API_URL: "goodbye"}

    def test_update_profile_removes_key(self, temporary_profiles_path):
        update_profile(name="test", PREFECT_API_URL="hello")
        assert load_profile("test") == {PREFECT_API_URL: "hello"}
        update_profile(name="test", PREFECT_API_URL=None)
        assert load_profile("test") == {}

    def test_update_profile_mixed_add_and_update(self, temporary_profiles_path):
        update_profile(name="test", PREFECT_API_URL="hello")
        assert load_profile("test") == {PREFECT_API_URL: "hello"}
        update_profile(
            name="test", PREFECT_API_URL="goodbye", PREFECT_LOGGING_LEVEL="DEBUG"
        )
        assert load_profile("test") == {
            PREFECT_API_URL: "goodbye",
            PREFECT_LOGGING_LEVEL: "DEBUG",
        }

    def test_update_profile_retains_existing_keys(self, temporary_profiles_path):
        update_profile(name="test", PREFECT_API_URL="hello")
        assert load_profile("test") == {PREFECT_API_URL: "hello"}
        update_profile(name="test", PREFECT_LOGGING_LEVEL="DEBUG")
        assert load_profile("test") == {
            PREFECT_API_URL: "hello",
            PREFECT_LOGGING_LEVEL: "DEBUG",
        }

    def test_update_profile_uses_current_profile_name(self, temporary_profiles_path):
        with prefect.context.ProfileContext(
            name="test", settings=get_current_settings()
        ):
            update_profile(PREFECT_API_URL="hello")

        assert load_profile("test") == {PREFECT_API_URL: "hello"}

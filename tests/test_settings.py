import copy
import os
import textwrap
from pathlib import Path

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    import pydantic.v1 as pydantic
else:
    import pydantic

import pytest

import prefect.context
import prefect.settings
from prefect.settings import (
    DEFAULT_PROFILES_PATH,
    PREFECT_API_DATABASE_CONNECTION_URL,
    PREFECT_API_DATABASE_PASSWORD,
    PREFECT_API_KEY,
    PREFECT_API_URL,
    PREFECT_CLIENT_RETRY_EXTRA_CODES,
    PREFECT_CLOUD_API_URL,
    PREFECT_CLOUD_UI_URL,
    PREFECT_CLOUD_URL,
    PREFECT_DEBUG_MODE,
    PREFECT_HOME,
    PREFECT_LOGGING_EXTRA_LOGGERS,
    PREFECT_LOGGING_LEVEL,
    PREFECT_LOGGING_SERVER_LEVEL,
    PREFECT_PROFILES_PATH,
    PREFECT_SERVER_API_HOST,
    PREFECT_SERVER_API_PORT,
    PREFECT_TEST_MODE,
    PREFECT_TEST_SETTING,
    PREFECT_UI_API_URL,
    PREFECT_UI_URL,
    REMOVED_EXPERIMENTAL_FLAGS,
    SETTING_VARIABLES,
    Profile,
    ProfilesCollection,
    Setting,
    Settings,
    get_current_settings,
    load_profile,
    load_profiles,
    save_profiles,
    temporary_settings,
)
from prefect.utilities.names import obfuscate


class TestSettingClass:
    def test_setting_equality_with_value(self):
        with temporary_settings({PREFECT_TEST_SETTING: "foo"}):
            assert PREFECT_TEST_SETTING == "foo"
            assert PREFECT_TEST_SETTING != "bar"

    def test_setting_equality_with_self(self):
        assert PREFECT_TEST_SETTING == PREFECT_TEST_SETTING

    def test_setting_equality_with_other_setting(self):
        assert PREFECT_TEST_SETTING != PREFECT_TEST_MODE

    def test_setting_hash_is_consistent(self):
        assert hash(PREFECT_TEST_SETTING) == hash(PREFECT_TEST_SETTING)

    def test_setting_hash_is_unique(self):
        assert hash(PREFECT_TEST_SETTING) != hash(PREFECT_LOGGING_LEVEL)

    def test_setting_hash_consistent_on_value_change(self):
        original = hash(PREFECT_TEST_SETTING)
        with temporary_settings({PREFECT_TEST_SETTING: "foo"}):
            assert hash(PREFECT_TEST_SETTING) == original

    def test_setting_hash_is_consistent_after_deepcopy(self):
        assert hash(PREFECT_TEST_SETTING) == hash(copy.deepcopy(PREFECT_TEST_SETTING))

    def test_deprecated_setting(self, monkeypatch):
        monkeypatch.setattr(PREFECT_TEST_SETTING, "deprecated", True)
        monkeypatch.setattr(PREFECT_TEST_SETTING, "deprecated_start_date", "Jan 2023")
        monkeypatch.setattr(PREFECT_TEST_SETTING, "deprecated_help", "test help")

        with pytest.warns(
            DeprecationWarning,
            match=(
                "Setting 'PREFECT_TEST_SETTING' has been deprecated. It will not be"
                " available after Jul 2023. test help"
            ),
        ):
            PREFECT_TEST_SETTING.value()

    def test_deprecated_setting_without_start_date_fails_at_init(self):
        with pytest.raises(
            ValueError, match="A start date is required if an end date is not provided."
        ):
            Setting(bool, deprecated=True)

    def test_deprecated_setting_when(self, monkeypatch):
        monkeypatch.setattr(PREFECT_TEST_SETTING, "deprecated", True)
        monkeypatch.setattr(PREFECT_TEST_SETTING, "deprecated_start_date", "Jan 2023")
        monkeypatch.setattr(
            PREFECT_TEST_SETTING, "deprecated_when", lambda x: x == "foo"
        )
        monkeypatch.setattr(
            PREFECT_TEST_SETTING, "deprecated_when_message", "the value is foo"
        )

        # Does not warn
        PREFECT_TEST_SETTING.value()

        with temporary_settings({PREFECT_TEST_SETTING: "foo"}):
            with pytest.warns(
                DeprecationWarning,
                match=(
                    "Setting 'PREFECT_TEST_SETTING' has been deprecated when the value"
                    " is foo. It will not be available after Jul 2023."
                ),
            ):
                PREFECT_TEST_SETTING.value()

    def test_deprecated_setting_does_not_raise_when_callbacks_bypassed(
        self, monkeypatch
    ):
        # i.e. for internal access to a deprecated setting
        monkeypatch.setattr(PREFECT_TEST_SETTING, "deprecated", True)
        monkeypatch.setattr(PREFECT_TEST_SETTING, "deprecated_start_date", "Jan 2023")

        # Does not warn
        PREFECT_TEST_SETTING.value(bypass_callback=True)


class TestSettingsClass:
    def test_settings_copy_with_update_does_not_mark_unset_as_set(self):
        settings = get_current_settings()
        set_keys = set(settings.dict(exclude_unset=True).keys())
        new_settings = settings.copy_with_update()
        new_set_keys = set(new_settings.dict(exclude_unset=True).keys())
        assert new_set_keys == set_keys

        new_settings = settings.copy_with_update(updates={PREFECT_API_KEY: "TEST"})
        new_set_keys = set(new_settings.dict(exclude_unset=True).keys())
        # Only the API key setting should be set
        assert new_set_keys - set_keys == {"PREFECT_API_KEY"}

    def test_settings_copy_with_update(self):
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

    def test_settings_loads_environment_variables_at_instantiation(self, monkeypatch):
        assert PREFECT_TEST_MODE.value() is True

        monkeypatch.setenv("PREFECT_TEST_MODE", "0")
        new_settings = Settings()
        assert PREFECT_TEST_MODE.value_from(new_settings) is False

    def test_settings_to_environment_includes_all_settings_with_non_null_values(self):
        settings = Settings()
        assert set(settings.to_environment_variables().keys()) == {
            key for key in SETTING_VARIABLES if getattr(settings, key) is not None
        }

    def test_settings_to_environment_casts_to_strings(self):
        assert (
            Settings(PREFECT_SERVER_API_PORT=3000).to_environment_variables()[
                "PREFECT_SERVER_API_PORT"
            ]
            == "3000"
        )

    def test_settings_to_environment_respects_includes(self):
        include = [PREFECT_SERVER_API_PORT]

        assert Settings(PREFECT_SERVER_API_PORT=3000).to_environment_variables(
            include=include
        ) == {"PREFECT_SERVER_API_PORT": "3000"}

        assert include == [PREFECT_SERVER_API_PORT], "Passed list should not be mutated"

    def test_settings_to_environment_exclude_unset_empty_if_none_set(self, monkeypatch):
        for key in SETTING_VARIABLES:
            monkeypatch.delenv(key, raising=False)

        assert Settings().to_environment_variables(exclude_unset=True) == {}

    def test_settings_to_environment_exclude_unset_only_includes_set(self, monkeypatch):
        for key in SETTING_VARIABLES:
            monkeypatch.delenv(key, raising=False)

        assert Settings(
            PREFECT_DEBUG_MODE=True, PREFECT_API_KEY="Hello"
        ).to_environment_variables(exclude_unset=True) == {
            "PREFECT_DEBUG_MODE": "True",
            "PREFECT_API_KEY": "Hello",
        }

    def test_settings_to_environment_exclude_unset_only_includes_set_even_if_included(
        self, monkeypatch
    ):
        for key in SETTING_VARIABLES:
            monkeypatch.delenv(key, raising=False)

        include = [PREFECT_HOME, PREFECT_DEBUG_MODE, PREFECT_API_KEY]

        assert Settings(
            PREFECT_DEBUG_MODE=True, PREFECT_API_KEY="Hello"
        ).to_environment_variables(exclude_unset=True, include=include) == {
            "PREFECT_DEBUG_MODE": "True",
            "PREFECT_API_KEY": "Hello",
        }

        assert include == [
            PREFECT_HOME,
            PREFECT_DEBUG_MODE,
            PREFECT_API_KEY,
        ], "Passed list should not be mutated"

    @pytest.mark.parametrize("exclude_unset", [True, False])
    def test_settings_to_environment_roundtrip(self, exclude_unset, monkeypatch):
        settings = Settings()
        variables = settings.to_environment_variables(exclude_unset=exclude_unset)
        for key, value in variables.items():
            monkeypatch.setenv(key, value)
        new_settings = Settings()
        assert settings.dict() == new_settings.dict()

    def test_settings_to_environment_does_not_use_value_callback(self):
        settings = Settings(PREFECT_UI_API_URL=None)
        # This would be cast to a non-null value if the value callback was used when
        # generating the environment variables
        assert "PREFECT_UI_API_URL" not in settings.to_environment_variables()

    def test_settings_hash_key(self):
        settings = Settings(PREFECT_TEST_MODE=True)
        diff_settings = Settings(PREFECT_TEST_MODE=False)

        assert settings.hash_key() == settings.hash_key()

        assert settings.hash_key() != diff_settings.hash_key()

    @pytest.mark.parametrize(
        "log_level_setting",
        [
            PREFECT_LOGGING_LEVEL,
            PREFECT_LOGGING_SERVER_LEVEL,
        ],
    )
    def test_settings_validates_log_levels(self, log_level_setting):
        with pytest.raises(pydantic.ValidationError, match="Unknown level"):
            Settings(**{log_level_setting.name: "FOOBAR"})

    @pytest.mark.parametrize(
        "log_level_setting",
        [
            PREFECT_LOGGING_LEVEL,
            PREFECT_LOGGING_SERVER_LEVEL,
        ],
    )
    def test_settings_uppercases_log_levels(self, log_level_setting):
        with temporary_settings({log_level_setting: "debug"}):
            assert log_level_setting.value() == "DEBUG"

    def test_equality_of_new_instances(self):
        assert Settings() == Settings()

    def test_equality_after_deep_copy(self):
        settings = Settings()
        assert copy.deepcopy(settings) == settings

    def test_equality_with_different_values(self):
        settings = Settings()
        assert (
            settings.copy_with_update(updates={PREFECT_TEST_SETTING: "foo"}) != settings
        )

    def test_with_obfuscated_secrets(self):
        settings = get_current_settings()
        original = settings.copy()
        obfuscated = settings.with_obfuscated_secrets()
        assert settings == original
        assert original != obfuscated
        for setting in SETTING_VARIABLES.values():
            if setting.deprecated:
                continue

            if setting.is_secret:
                assert obfuscated.value_of(setting) == obfuscate(
                    original.value_of(setting)
                )
            else:
                assert obfuscated.value_of(setting) == original.value_of(setting)


class TestSettingAccess:
    def test_get_value_root_setting(self):
        with temporary_settings(
            updates={PREFECT_API_URL: "test"}
        ):  # Set a value so its not null
            value = prefect.settings.PREFECT_API_URL.value()
            value_of = get_current_settings().value_of(PREFECT_API_URL)
            value_from = PREFECT_API_URL.value_from(get_current_settings())
            assert value == value_of == value_from == "test"

    def test_get_value_nested_setting(self):
        value = prefect.settings.PREFECT_LOGGING_LEVEL.value()
        value_of = get_current_settings().value_of(PREFECT_LOGGING_LEVEL)
        value_from = PREFECT_LOGGING_LEVEL.value_from(get_current_settings())
        assert value == value_of == value_from

    def test_test_mode_access(self):
        assert PREFECT_TEST_MODE.value() is True

    def test_settings_in_truthy_statements_use_value(self):
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

        if PREFECT_SERVER_API_HOST:
            assert True, "Treated as truth"
        else:
            assert False, "Not treated as truth"

        with temporary_settings(updates={PREFECT_SERVER_API_HOST: ""}):
            if not PREFECT_SERVER_API_HOST:
                assert True, "Treated as truth"
            else:
                assert False, "Not treated as truth"

    def test_ui_api_url_from_defaults(self):
        assert PREFECT_UI_API_URL.value() == "/api"

    def test_database_connection_url_templates_password(self):
        with temporary_settings(
            {
                PREFECT_API_DATABASE_CONNECTION_URL: (
                    "${PREFECT_API_DATABASE_PASSWORD}/test"
                ),
                PREFECT_API_DATABASE_PASSWORD: "password",
            }
        ):
            assert PREFECT_API_DATABASE_CONNECTION_URL.value() == "password/test"

    def test_database_connection_url_templates_null_password(self):
        # Not exactly beautiful behavior here, but I think it's clear.
        # In the future, we may want to consider raising if attempting to template
        # a null value.
        with temporary_settings(
            {
                PREFECT_API_DATABASE_CONNECTION_URL: (
                    "${PREFECT_API_DATABASE_PASSWORD}/test"
                )
            }
        ):
            assert PREFECT_API_DATABASE_CONNECTION_URL.value() == "None/test"

    def test_warning_if_database_password_set_without_template_string(self):
        with pytest.warns(
            UserWarning,
            match=(
                "PREFECT_API_DATABASE_PASSWORD is set but not included in the "
                "PREFECT_API_DATABASE_CONNECTION_URL. "
                "The provided password will be ignored."
            ),
        ):
            with temporary_settings(
                {
                    PREFECT_API_DATABASE_CONNECTION_URL: "test",
                    PREFECT_API_DATABASE_PASSWORD: "password",
                }
            ):
                pass

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("foo", ["foo"]),
            ("foo,bar", ["foo", "bar"]),
            ("foo, bar, foobar ", ["foo", "bar", "foobar"]),
        ],
    )
    def test_extra_loggers(self, value, expected):
        settings = Settings(PREFECT_LOGGING_EXTRA_LOGGERS=value)
        assert PREFECT_LOGGING_EXTRA_LOGGERS.value_from(settings) == expected

    def test_prefect_home_expands_tilde_in_path(self):
        settings = Settings(PREFECT_HOME="~/test")
        assert PREFECT_HOME.value_from(settings) == Path("~/test").expanduser()

    def test_prefect_cloud_url_deprecated_on_set(self):
        with temporary_settings({PREFECT_CLOUD_URL: "test"}):
            with pytest.raises(
                DeprecationWarning,
                match=(
                    "`PREFECT_CLOUD_URL` is set and will be used instead of"
                    " `PREFECT_CLOUD_API_URL`"
                ),
            ):
                PREFECT_CLOUD_API_URL.value()

    def test_prefect_cloud_url_deprecated_on_access(self):
        with pytest.raises(
            DeprecationWarning,
            match=(
                "Setting 'PREFECT_CLOUD_URL' has been deprecated. "
                "It will not be available after Jun 2023. "
                "Use `PREFECT_CLOUD_API_URL` instead."
            ),
        ):
            PREFECT_CLOUD_URL.value()

    @pytest.mark.parametrize(
        "api_url,ui_url",
        [
            (None, None),
            (
                "https://api.prefect.cloud/api/accounts/ACCOUNT/workspaces/WORKSPACE",
                "https://app.prefect.cloud/account/ACCOUNT/workspace/WORKSPACE",
            ),
            ("http://my-orion/api", "http://my-orion"),
            ("https://api.foo.bar", "https://api.foo.bar"),
        ],
    )
    def test_ui_url_inferred_from_api_url(self, api_url, ui_url):
        with temporary_settings({PREFECT_API_URL: api_url}):
            assert PREFECT_UI_URL.value() == ui_url

    def test_ui_url_set_directly(self):
        with temporary_settings({PREFECT_UI_URL: "test"}):
            assert PREFECT_UI_URL.value() == "test"

    @pytest.mark.parametrize(
        "api_url,ui_url",
        [
            (
                "https://api.prefect.cloud/api",
                "https://app.prefect.cloud",
            ),
            ("http://my-cloud/api", "http://my-cloud"),
            ("https://api.foo.bar", "https://api.foo.bar"),
        ],
    )
    def test_cloud_ui_url_inferred_from_cloud_api_url(self, api_url, ui_url):
        with temporary_settings({PREFECT_CLOUD_API_URL: api_url}):
            assert PREFECT_CLOUD_UI_URL.value() == ui_url

    def test_cloud_ui_url_set_directly(self):
        with temporary_settings({PREFECT_CLOUD_UI_URL: "test"}):
            assert PREFECT_CLOUD_UI_URL.value() == "test"

    @pytest.mark.parametrize(
        "extra_codes,expected",
        [
            ("", set()),
            ("400", {400}),
            ("400,400,400", {400}),
            ("400,500", {400, 500}),
            ("400, 401, 402", {400, 401, 402}),
        ],
    )
    def test_client_retry_extra_codes(self, extra_codes, expected):
        with temporary_settings({PREFECT_CLIENT_RETRY_EXTRA_CODES: extra_codes}):
            assert PREFECT_CLIENT_RETRY_EXTRA_CODES.value() == expected

    @pytest.mark.parametrize(
        "extra_codes",
        [
            "foo",
            "-1",
            "0",
            "10",
            "400,foo",
            "400,500,foo",
        ],
    )
    def test_client_retry_extra_codes_invalid(self, extra_codes):
        with pytest.raises(ValueError):
            with temporary_settings({PREFECT_CLIENT_RETRY_EXTRA_CODES: extra_codes}):
                PREFECT_CLIENT_RETRY_EXTRA_CODES.value()


class TestDatabaseSettings:
    def test_database_connection_url_templates_password(self):
        with temporary_settings(
            {
                PREFECT_API_DATABASE_CONNECTION_URL: (
                    "${PREFECT_API_DATABASE_PASSWORD}/test"
                ),
                PREFECT_API_DATABASE_PASSWORD: "password",
            }
        ):
            assert PREFECT_API_DATABASE_CONNECTION_URL.value() == "password/test"

    def test_database_connection_url_templates_null_password(self):
        # Not exactly beautiful behavior here, but I think it's clear.
        # In the future, we may want to consider raising if attempting to template
        # a null value.
        with temporary_settings(
            {
                PREFECT_API_DATABASE_CONNECTION_URL: (
                    "${PREFECT_API_DATABASE_PASSWORD}/test"
                )
            }
        ):
            assert PREFECT_API_DATABASE_CONNECTION_URL.value() == "None/test"

    def test_warning_if_database_password_set_without_template_string(self):
        with pytest.warns(
            UserWarning,
            match=(
                "PREFECT_API_DATABASE_PASSWORD is set but not included in the "
                "PREFECT_API_DATABASE_CONNECTION_URL. "
                "The provided password will be ignored."
            ),
        ):
            with temporary_settings(
                {
                    PREFECT_API_DATABASE_CONNECTION_URL: "test",
                    PREFECT_API_DATABASE_PASSWORD: "password",
                }
            ):
                pass

    def test_connection_string_with_dollar_sign(self):
        """
        Regression test for https://github.com/PrefectHQ/prefect/issues/11067.

        This test ensures that passwords with dollar signs do not cause issues when
        templating the connection string.
        """
        with temporary_settings(
            {
                PREFECT_API_DATABASE_CONNECTION_URL: (
                    "postgresql+asyncpg://"
                    "the-user:the-$password@"
                    "the-database-server.example.com:5432"
                    "/the-database"
                ),
            }
        ):
            assert PREFECT_API_DATABASE_CONNECTION_URL.value() == (
                "postgresql+asyncpg://"
                "the-user:the-$password@"
                "the-database-server.example.com:5432"
                "/the-database"
            )


class TestTemporarySettings:
    def test_temporary_settings(self):
        assert PREFECT_TEST_MODE.value() is True
        with temporary_settings(updates={PREFECT_TEST_MODE: False}) as new_settings:
            assert (
                PREFECT_TEST_MODE.value_from(new_settings) is False
            ), "Yields the new settings"
            assert PREFECT_TEST_MODE.value() is False

        assert PREFECT_TEST_MODE.value() is True

    def test_temporary_settings_does_not_mark_unset_as_set(self):
        settings = get_current_settings()
        set_keys = set(settings.dict(exclude_unset=True).keys())
        with temporary_settings() as new_settings:
            pass
        new_set_keys = set(new_settings.dict(exclude_unset=True).keys())
        assert new_set_keys == set_keys

    def test_temporary_settings_can_restore_to_defaults_values(self):
        with temporary_settings(updates={PREFECT_TEST_SETTING: "FOO"}):
            with temporary_settings(restore_defaults={PREFECT_TEST_SETTING}):
                assert (
                    PREFECT_TEST_SETTING.value() == PREFECT_TEST_SETTING.field.default
                )

    def test_temporary_settings_restores_on_error(self):
        assert PREFECT_TEST_MODE.value() is True

        with pytest.raises(ValueError):
            with temporary_settings(updates={PREFECT_TEST_MODE: False}):
                raise ValueError()

        assert os.environ["PREFECT_TEST_MODE"] == "1", "Does not alter os environ."
        assert PREFECT_TEST_MODE.value() is True


class TestLoadProfiles:
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

    def test_load_profiles_only_active_key(self, temporary_profiles_path):
        temporary_profiles_path.write_text(
            textwrap.dedent(
                """
                active = "default"
                """
            )
        )
        assert load_profiles().active_name == "default"
        assert isinstance(load_profiles()["default"].settings, dict)

    def test_load_profiles_empty_file(self, temporary_profiles_path):
        temporary_profiles_path.touch()
        assert load_profiles().active_name == "default"
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

    def test_load_profile_default(self):
        assert load_profile("default") == Profile(
            name="default", settings={}, source=DEFAULT_PROFILES_PATH
        )

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
        assert load_profile("foo") == Profile(
            name="foo",
            settings={
                PREFECT_API_KEY: "bar",
                PREFECT_DEBUG_MODE: 1,
            },
            source=temporary_profiles_path,
        )

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

    @pytest.mark.parametrize("removed_flag", sorted(REMOVED_EXPERIMENTAL_FLAGS))
    def test_removed_experimental_flags(self, temporary_profiles_path, removed_flag):
        assert removed_flag in REMOVED_EXPERIMENTAL_FLAGS

        temporary_profiles_path.write_text(
            textwrap.dedent(
                f"""
                [profiles.foo]
                {removed_flag} = "False"
                """
            )
        )

        with pytest.warns(
            UserWarning,
            match=(
                f"Experimental flag '{removed_flag}' "
                "has been removed, please update your 'foo' profile."
            ),
        ):
            load_profile("foo")


class TestSaveProfiles:
    @pytest.fixture(autouse=True)
    def temporary_profiles_path(self, tmp_path):
        path = tmp_path / "profiles.toml"
        with temporary_settings(updates={PREFECT_PROFILES_PATH: path}):
            yield path

    def test_save_profiles_does_not_include_default(self, temporary_profiles_path):
        """
        Including the default has a tendency to bake in settings the user may not want, and
        can prevent them from gaining new defaults.
        """
        save_profiles(ProfilesCollection(active=None, profiles=[]))
        assert "profiles.default" not in temporary_profiles_path.read_text()

    def test_save_profiles_additional_profiles(self, temporary_profiles_path):
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


class TestProfile:
    def test_init_casts_names_to_setting_types(self):
        profile = Profile(name="test", settings={"PREFECT_DEBUG_MODE": 1})
        assert profile.settings == {PREFECT_DEBUG_MODE: 1}

    def test_validate_settings(self):
        profile = Profile(name="test", settings={PREFECT_SERVER_API_PORT: "foo"})
        with pytest.raises(pydantic.ValidationError):
            profile.validate_settings()

    def test_validate_settings_ignores_environment_variables(self, monkeypatch):
        """
        If using `context.use_profile` to validate settings, environment variables may
        override the setting and hide validation errors
        """
        monkeypatch.setenv("PREFECT_SERVER_API_PORT", "1234")
        profile = Profile(name="test", settings={PREFECT_SERVER_API_PORT: "foo"})
        with pytest.raises(pydantic.ValidationError):
            profile.validate_settings()


class TestProfilesCollection:
    def test_init_stores_single_profile(self):
        profile = Profile(name="test", settings={})
        profiles = ProfilesCollection(profiles=[profile])
        assert profiles.profiles_by_name == {"test": profile}
        assert profiles.active_name is None

    def test_init_stores_multiple_profile(self):
        foo = Profile(name="foo", settings={})
        bar = Profile(name="bar", settings={})
        profiles = ProfilesCollection(profiles=[foo, bar])
        assert profiles.profiles_by_name == {"foo": foo, "bar": bar}
        assert profiles.active_name is None

    def test_init_sets_active_name(self):
        foo = Profile(name="foo", settings={})
        bar = Profile(name="bar", settings={})
        profiles = ProfilesCollection(profiles=[foo, bar], active="foo")
        assert profiles.active_name == "foo"

    def test_init_sets_active_name_even_if_not_present(self):
        foo = Profile(name="foo", settings={})
        bar = Profile(name="bar", settings={})
        profiles = ProfilesCollection(profiles=[foo, bar], active="foobar")
        assert profiles.active_name == "foobar"

    def test_getitem_retrieves_profiles(self):
        foo = Profile(name="foo", settings={})
        bar = Profile(name="bar", settings={})
        profiles = ProfilesCollection(profiles=[foo, bar])
        assert profiles["foo"] is foo
        assert profiles["bar"] is bar

    def test_getitem_with_invalid_key(self):
        foo = Profile(name="foo", settings={})
        bar = Profile(name="bar", settings={})
        profiles = ProfilesCollection(profiles=[foo, bar])
        with pytest.raises(KeyError):
            profiles["test"]

    def test_iter_retrieves_profile_names(self):
        foo = Profile(name="foo", settings={})
        bar = Profile(name="bar", settings={})
        profiles = ProfilesCollection(profiles=[foo, bar])
        assert tuple(sorted(profiles)) == ("bar", "foo")

    def test_names_property(self):
        foo = Profile(name="foo", settings={})
        bar = Profile(name="bar", settings={})
        profiles = ProfilesCollection(profiles=[foo, bar], active="foo")
        assert profiles.names == {"foo", "bar"}

    def test_active_profile_property(self):
        foo = Profile(name="foo", settings={})
        bar = Profile(name="bar", settings={})
        profiles = ProfilesCollection(profiles=[foo, bar], active="foo")
        assert profiles.active_profile == foo

    def test_active_profile_property_null_active(self):
        foo = Profile(name="foo", settings={})
        bar = Profile(name="bar", settings={})
        profiles = ProfilesCollection(profiles=[foo, bar], active=None)
        assert profiles.active_profile is None

    def test_active_profile_property_missing_active(self):
        foo = Profile(name="foo", settings={})
        bar = Profile(name="bar", settings={})
        profiles = ProfilesCollection(profiles=[foo, bar], active="foobar")
        with pytest.raises(KeyError):
            profiles.active_profile

    def test_set_active_profile(self):
        foo = Profile(name="foo", settings={})
        bar = Profile(name="bar", settings={})
        profiles = ProfilesCollection(profiles=[foo, bar], active=None)
        assert profiles.set_active("foo") is None
        assert profiles.active_name == "foo"
        assert profiles.active_profile is foo

    def test_set_active_profile_with_missing_name(self):
        foo = Profile(name="foo", settings={})
        bar = Profile(name="bar", settings={})
        profiles = ProfilesCollection(profiles=[foo, bar], active=None)
        with pytest.raises(ValueError, match="Unknown profile name"):
            profiles.set_active("foobar")

    def test_set_active_profile_with_null_name(self):
        foo = Profile(name="foo", settings={})
        bar = Profile(name="bar", settings={})
        profiles = ProfilesCollection(profiles=[foo, bar], active=None)
        assert profiles.set_active(None) is None
        assert profiles.active_name is None
        assert profiles.active_profile is None

    def test_add_profile(self):
        foo = Profile(name="foo", settings={})
        bar = Profile(name="bar", settings={})
        profiles = ProfilesCollection(profiles=[foo], active=None)
        assert "bar" not in profiles.names
        profiles.add_profile(bar)
        assert "bar" in profiles.names
        assert profiles["bar"] is bar

    def test_add_profile_already_exists(self):
        foo = Profile(name="foo", settings={})
        bar = Profile(name="bar", settings={})
        profiles = ProfilesCollection(profiles=[foo, bar], active=None)
        with pytest.raises(ValueError, match="already exists in collection"):
            profiles.add_profile(bar)

    def test_remove_profiles(self):
        foo = Profile(name="foo", settings={})
        bar = Profile(name="bar", settings={})
        profiles = ProfilesCollection(profiles=[foo, bar], active=None)
        assert "bar" in profiles
        profiles.remove_profile("bar")
        assert "bar" not in profiles

    def test_remove_profile_does_not_exist(self):
        foo = Profile(name="foo", settings={})
        Profile(name="bar", settings={})
        profiles = ProfilesCollection(profiles=[foo], active=None)
        assert "bar" not in profiles.names
        with pytest.raises(KeyError):
            profiles.remove_profile("bar")

    def test_update_profile_adds_key(self):
        profiles = ProfilesCollection(profiles=[Profile(name="test", settings={})])
        profiles.update_profile(name="test", settings={PREFECT_API_URL: "hello"})
        assert profiles["test"].settings == {PREFECT_API_URL: "hello"}

    def test_update_profile_updates_key(self):
        profiles = ProfilesCollection(profiles=[Profile(name="test", settings={})])
        profiles.update_profile(name="test", settings={PREFECT_API_URL: "hello"})
        assert profiles["test"].settings == {PREFECT_API_URL: "hello"}
        profiles.update_profile(name="test", settings={PREFECT_API_URL: "goodbye"})
        assert profiles["test"].settings == {PREFECT_API_URL: "goodbye"}

    def test_update_profile_removes_key(self):
        profiles = ProfilesCollection(profiles=[Profile(name="test", settings={})])
        profiles.update_profile(name="test", settings={PREFECT_API_URL: "hello"})
        assert profiles["test"].settings == {PREFECT_API_URL: "hello"}
        profiles.update_profile(name="test", settings={PREFECT_API_URL: None})
        assert profiles["test"].settings == {}

    def test_update_profile_mixed_add_and_update(self):
        profiles = ProfilesCollection(profiles=[Profile(name="test", settings={})])
        profiles.update_profile(name="test", settings={PREFECT_API_URL: "hello"})
        assert profiles["test"].settings == {PREFECT_API_URL: "hello"}
        profiles.update_profile(
            name="test",
            settings={PREFECT_API_URL: "goodbye", PREFECT_LOGGING_LEVEL: "DEBUG"},
        )
        assert profiles["test"].settings == {
            PREFECT_API_URL: "goodbye",
            PREFECT_LOGGING_LEVEL: "DEBUG",
        }

    def test_update_profile_retains_existing_keys(self):
        profiles = ProfilesCollection(profiles=[Profile(name="test", settings={})])
        profiles.update_profile(name="test", settings={PREFECT_API_URL: "hello"})
        assert profiles["test"].settings == {PREFECT_API_URL: "hello"}
        profiles.update_profile(name="test", settings={PREFECT_LOGGING_LEVEL: "DEBUG"})
        assert profiles["test"].settings == {
            PREFECT_API_URL: "hello",
            PREFECT_LOGGING_LEVEL: "DEBUG",
        }

    def test_without_profile_source(self):
        foo = Profile(name="foo", settings={}, source=Path("/foo"))
        bar = Profile(name="bar", settings={}, source=Path("/bar"))
        profiles = ProfilesCollection(profiles=[foo, bar], active=None)
        new_profiles = profiles.without_profile_source(Path("/foo"))
        assert new_profiles.names == {"bar"}
        assert profiles.names == {"foo", "bar"}, "Original object not mutated"

    def test_without_profile_source_retains_nulls(self):
        foo = Profile(name="foo", settings={}, source=Path("/foo"))
        bar = Profile(name="bar", settings={}, source=None)
        profiles = ProfilesCollection(profiles=[foo, bar], active=None)
        new_profiles = profiles.without_profile_source(Path("/foo"))
        assert new_profiles.names == {"bar"}
        assert profiles.names == {"foo", "bar"}, "Original object not mutated"

    def test_without_profile_source_handles_null_input(self):
        foo = Profile(name="foo", settings={}, source=Path("/foo"))
        bar = Profile(name="bar", settings={}, source=None)
        profiles = ProfilesCollection(profiles=[foo, bar], active=None)
        new_profiles = profiles.without_profile_source(None)
        assert new_profiles.names == {"foo"}
        assert profiles.names == {"foo", "bar"}, "Original object not mutated"

    def test_equality(self):
        foo = Profile(name="foo", settings={}, source=Path("/foo"))
        bar = Profile(name="bar", settings={}, source=Path("/bar"))

        assert ProfilesCollection(profiles=[foo, bar]) == ProfilesCollection(
            profiles=[foo, bar]
        ), "Same definition should be equal"

        assert ProfilesCollection(
            profiles=[foo, bar], active=None
        ) == ProfilesCollection(
            profiles=[foo, bar]
        ), "Explicit and implicit null active should be equal"

        assert ProfilesCollection(
            profiles=[foo, bar], active="foo"
        ) != ProfilesCollection(
            profiles=[foo, bar]
        ), "One null active should be inequal"

        assert ProfilesCollection(
            profiles=[foo, bar], active="foo"
        ) != ProfilesCollection(
            profiles=[foo, bar], active="bar"
        ), "Different active should be inequal"

        assert ProfilesCollection(profiles=[foo, bar]) == ProfilesCollection(
            profiles=[
                Profile(name="foo", settings={}, source=Path("/foo")),
                Profile(name="bar", settings={}, source=Path("/bar")),
            ]
        ), "Comparison of profiles should use equality not identity"

        assert ProfilesCollection(profiles=[foo, bar]) != ProfilesCollection(
            profiles=[foo]
        ), "Missing profile should be inequal"

        assert ProfilesCollection(profiles=[foo, bar]) != ProfilesCollection(
            profiles=[
                foo,
                Profile(
                    name="bar", settings={PREFECT_API_KEY: "test"}, source=Path("/bar")
                ),
            ]
        ), "Changed profile settings should be inequal"

        assert ProfilesCollection(profiles=[foo, bar]) != ProfilesCollection(
            profiles=[
                foo,
                Profile(name="bar", settings={}, source=Path("/new-path")),
            ]
        ), "Changed profile source should be inequal"

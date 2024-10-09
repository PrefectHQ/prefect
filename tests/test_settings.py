import copy
import os
import textwrap
import warnings
from pathlib import Path

import pydantic
import pytest
from sqlalchemy import make_url

import prefect.context
import prefect.settings
from prefect.exceptions import ProfileSettingsValidationError
from prefect.settings import (
    DEFAULT_PROFILES_PATH,
    PREFECT_API_DATABASE_CONNECTION_URL,
    PREFECT_API_DATABASE_DRIVER,
    PREFECT_API_DATABASE_HOST,
    PREFECT_API_DATABASE_NAME,
    PREFECT_API_DATABASE_PASSWORD,
    PREFECT_API_DATABASE_PORT,
    PREFECT_API_DATABASE_USER,
    PREFECT_API_KEY,
    PREFECT_API_URL,
    PREFECT_CLIENT_RETRY_EXTRA_CODES,
    PREFECT_CLOUD_API_URL,
    PREFECT_CLOUD_UI_URL,
    PREFECT_DEBUG_MODE,
    PREFECT_HOME,
    PREFECT_LOGGING_EXTRA_LOGGERS,
    PREFECT_LOGGING_LEVEL,
    PREFECT_LOGGING_SERVER_LEVEL,
    PREFECT_PROFILES_PATH,
    PREFECT_SERVER_ALLOW_EPHEMERAL_MODE,
    PREFECT_SERVER_API_HOST,
    PREFECT_SERVER_API_PORT,
    PREFECT_TEST_MODE,
    PREFECT_TEST_SETTING,
    PREFECT_UI_URL,
    PREFECT_UNIT_TEST_MODE,
    SETTING_VARIABLES,
    Profile,
    ProfilesCollection,
    Settings,
    get_current_settings,
    load_profile,
    load_profiles,
    save_profiles,
    temporary_settings,
)


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


class TestSettingsClass:
    def test_settings_copy_with_update_does_not_mark_unset_as_set(self):
        settings = get_current_settings()
        set_keys = set(settings.model_dump(exclude_unset=True).keys())
        new_settings = settings.copy_with_update()
        new_set_keys = set(new_settings.model_dump(exclude_unset=True).keys())
        assert new_set_keys == set_keys

        new_settings = settings.copy_with_update(updates={PREFECT_API_KEY: "TEST"})
        new_set_keys = set(new_settings.model_dump(exclude_unset=True).keys())
        # Only the API key setting should be set
        assert new_set_keys - set_keys == {"api_key"}

    def test_settings_copy_with_update(self):
        settings = get_current_settings()
        assert settings.unit_test_mode is True

        with temporary_settings(restore_defaults={PREFECT_API_KEY}):
            new_settings = settings.copy_with_update(
                updates={PREFECT_CLIENT_RETRY_EXTRA_CODES: "400,500"},
                set_defaults={PREFECT_UNIT_TEST_MODE: False, PREFECT_API_KEY: "TEST"},
            )
            assert (
                new_settings.unit_test_mode is True
            ), "Not changed, existing value was not default"
            assert (
                new_settings.api_key is not None
                and new_settings.api_key.get_secret_value() == "TEST"
            ), "Changed, existing value was default"
            assert new_settings.client_retry_extra_codes == {400, 500}

    def test_settings_loads_environment_variables_at_instantiation(self, monkeypatch):
        assert PREFECT_TEST_MODE.value() is True

        monkeypatch.setenv("PREFECT_TEST_MODE", "0")
        new_settings = Settings()
        assert PREFECT_TEST_MODE.value_from(new_settings) is False

    def test_settings_to_environment_includes_all_settings_with_non_null_values(self):
        settings = Settings()
        assert set(settings.to_environment_variables().keys()) == {
            f"PREFECT_{key.upper()}"
            for key in settings.model_dump(exclude_none=True).keys()
        }

    def test_settings_to_environment_casts_to_strings(self):
        assert (
            Settings(server_api_port=3000).to_environment_variables()[
                "PREFECT_SERVER_API_PORT"
            ]
            == "3000"
        )

    def test_settings_to_environment_respects_includes(self):
        include = [PREFECT_SERVER_API_PORT]

        assert Settings(server_api_port=3000).to_environment_variables(
            include=include
        ) == {"PREFECT_SERVER_API_PORT": "3000"}

        assert include == [PREFECT_SERVER_API_PORT], "Passed list should not be mutated"

    def test_settings_to_environment_exclude_unset_empty_if_none_set(self, monkeypatch):
        for key in SETTING_VARIABLES:
            if not key.startswith("PREFECT_") or key == "PREFECT_TEST_MODE":
                continue
            monkeypatch.delenv(key, raising=False)

        assert Settings().to_environment_variables(
            exclude_unset=True,
        ) == {
            "PREFECT_TEST_MODE": "True",
        }

    def test_settings_to_environment_exclude_unset_only_includes_set(self, monkeypatch):
        for key in SETTING_VARIABLES:
            if key == "PREFECT_TEST_MODE":
                continue
            monkeypatch.delenv(key, raising=False)

        assert Settings(debug_mode=True, api_key="Hello").to_environment_variables(
            exclude_unset=True,
        ) == {
            "PREFECT_TEST_MODE": "True",
            "PREFECT_DEBUG_MODE": "True",
            "PREFECT_API_KEY": "Hello",
        }

    def test_settings_to_environment_exclude_unset_only_includes_set_even_if_included(
        self, monkeypatch
    ):
        for key in SETTING_VARIABLES:
            monkeypatch.delenv(key, raising=False)

        include = [PREFECT_HOME, PREFECT_DEBUG_MODE, PREFECT_API_KEY]

        assert Settings(debug_mode=True, api_key="Hello").to_environment_variables(
            exclude_unset=True, include=include
        ) == {
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
        assert settings.model_dump() == new_settings.model_dump()

    def test_settings_hash_key(self):
        settings = Settings(test_mode=True)
        diff_settings = Settings(test_mode=False)

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
        with pytest.raises(
            pydantic.ValidationError,
            match="should be 'DEBUG', 'INFO', 'WARNING', 'ERROR' or 'CRITICAL'",
        ):
            Settings(**{log_level_setting.field_name: "FOOBAR"})

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

    def test_include_secrets(self):
        settings = Settings(api_key=pydantic.SecretStr("test"))

        assert settings.model_dump().get("api_key") == pydantic.SecretStr("test")
        assert settings.model_dump(mode="json").get("api_key") == "**********"
        assert (
            settings.model_dump(context={"include_secrets": True}).get("api_key")
            == "test"
        )

    def test_loads_when_profile_path_does_not_exist(self, monkeypatch):
        monkeypatch.setenv("PREFECT_PROFILES_PATH", str(Path.home() / "nonexistent"))
        monkeypatch.delenv("PREFECT_TEST_MODE", raising=False)
        monkeypatch.delenv("PREFECT_UNIT_TEST_MODE", raising=False)
        assert Settings().test_setting == "FOO"

    def test_loads_when_profile_path_is_not_a_toml_file(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PREFECT_PROFILES_PATH", str(tmp_path / "profiles.toml"))
        monkeypatch.delenv("PREFECT_TEST_MODE", raising=False)
        monkeypatch.delenv("PREFECT_UNIT_TEST_MODE", raising=False)

        with open(tmp_path / "profiles.toml", "w") as f:
            f.write("Ceci n'est pas un fichier toml")

        with pytest.warns(UserWarning, match="Failed to load profiles from"):
            assert Settings().test_setting == "FOO"


class TestSettingAccess:
    def test_get_value_root_setting(self):
        with temporary_settings(
            updates={PREFECT_API_URL: "test"}
        ):  # Set a value so its not null
            assert PREFECT_API_URL.value() == "test"
            assert get_current_settings().api_url == "test"

    def test_get_value_nested_setting(self):
        value = prefect.settings.PREFECT_LOGGING_LEVEL.value()
        value_of = get_current_settings().logging_level
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

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("foo", ["foo"]),
            ("foo,bar", ["foo", "bar"]),
            ("foo, bar, foobar ", ["foo", "bar", "foobar"]),
        ],
    )
    def test_extra_loggers(self, value, expected):
        settings = Settings(logging_extra_loggers=value)
        assert PREFECT_LOGGING_EXTRA_LOGGERS.value_from(settings) == expected

    def test_prefect_home_expands_tilde_in_path(self):
        settings = Settings(home="~/test")
        assert PREFECT_HOME.value_from(settings) == Path("~/test").expanduser()

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
            # We'll infer that app. and api. subdomains go together for prefect domains
            (
                "https://api.prefect.cloud/api",
                "https://app.prefect.cloud",
            ),
            (
                "https://api.theoretical.prefect.bonkers/api",
                "https://app.theoretical.prefect.bonkers",
            ),
            (
                "https://api.prefect.banooners/api",
                "https://app.prefect.banooners",
            ),
            # We'll leave URLs with non-prefect TLDs alone
            (
                "https://api.theoretical.prefect.customer.com/api",
                "https://api.theoretical.prefect.customer.com",
            ),
            # Some day, some day...
            (
                "https://api.prefect/api",
                "https://api.prefect",
            ),
            # We'll leave all other URLs alone
            ("http://prefect/api", "http://prefect"),
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

    def test_deprecated_ENV_VAR_attribute_access(self):
        settings = Settings()
        value = None
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            value = settings.PREFECT_TEST_MODE

            assert len(w) == 1
            assert issubclass(w[-1].category, DeprecationWarning)
            assert (
                "Accessing `Settings().PREFECT_TEST_MODE` is deprecated. Use `Settings().test_mode` instead."
                in str(w[-1].message)
            )

        assert value == settings.test_mode


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

    def test_database_connection_url_raises_on_null_password(self):
        # Not exactly beautiful behavior here, but I think it's clear.
        # In the future, we may want to consider raising if attempting to template
        # a null value.
        with pytest.raises(ValueError, match="database password is None"):
            with temporary_settings(
                {
                    PREFECT_API_DATABASE_CONNECTION_URL: (
                        "${PREFECT_API_DATABASE_PASSWORD}/test"
                    )
                }
            ):
                pass

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

    def test_postgres_database_settings_may_be_set_individually(self):
        with temporary_settings(
            {
                PREFECT_API_DATABASE_CONNECTION_URL: None,
                PREFECT_API_DATABASE_DRIVER: "postgresql+asyncpg",
                PREFECT_API_DATABASE_HOST: "the-database-server.example.com",
                PREFECT_API_DATABASE_PORT: 15432,
                PREFECT_API_DATABASE_USER: "the-user",
                PREFECT_API_DATABASE_NAME: "the-database",
                PREFECT_API_DATABASE_PASSWORD: "the-password",
            }
        ):
            url = make_url(PREFECT_API_DATABASE_CONNECTION_URL.value())
            assert url.drivername == "postgresql+asyncpg"
            assert url.host == "the-database-server.example.com"
            assert url.port == 15432
            assert url.username == "the-user"
            assert url.database == "the-database"
            assert url.password == "the-password"

    def test_postgres_password_is_quoted(self):
        with temporary_settings(
            {
                PREFECT_API_DATABASE_CONNECTION_URL: None,
                PREFECT_API_DATABASE_DRIVER: "postgresql+asyncpg",
                PREFECT_API_DATABASE_HOST: "the-database-server.example.com",
                PREFECT_API_DATABASE_PORT: 15432,
                PREFECT_API_DATABASE_USER: "the-user",
                PREFECT_API_DATABASE_NAME: "the-database",
                PREFECT_API_DATABASE_PASSWORD: "the-password:has:funky!@stuff",
            }
        ):
            url = make_url(PREFECT_API_DATABASE_CONNECTION_URL.value())
            assert url.drivername == "postgresql+asyncpg"
            assert url.host == "the-database-server.example.com"
            assert url.port == 15432
            assert url.username == "the-user"
            assert url.database == "the-database"
            assert url.password == "the-password:has:funky!@stuff"

    def test_postgres_database_settings_defaults_port(self):
        with temporary_settings(
            {
                PREFECT_API_DATABASE_CONNECTION_URL: None,
                PREFECT_API_DATABASE_DRIVER: "postgresql+asyncpg",
                PREFECT_API_DATABASE_HOST: "the-database-server.example.com",
                PREFECT_API_DATABASE_USER: "the-user",
                PREFECT_API_DATABASE_NAME: "the-database",
                PREFECT_API_DATABASE_PASSWORD: "the-password",
            }
        ):
            url = make_url(PREFECT_API_DATABASE_CONNECTION_URL.value())
            assert url.drivername == "postgresql+asyncpg"
            assert url.host == "the-database-server.example.com"
            assert url.port == 5432
            assert url.username == "the-user"
            assert url.database == "the-database"
            assert url.password == "the-password"

    def test_sqlite_database_settings_may_be_set_individually(self):
        with temporary_settings(
            {
                PREFECT_API_DATABASE_CONNECTION_URL: None,
                PREFECT_API_DATABASE_DRIVER: "sqlite+aiosqlite",
                PREFECT_API_DATABASE_NAME: "/the/database/file/path.db",
            }
        ):
            url = make_url(PREFECT_API_DATABASE_CONNECTION_URL.value())
            assert url.drivername == "sqlite+aiosqlite"
            assert url.database == "/the/database/file/path.db"

    def test_sqlite_database_driver_uses_default_path(self):
        with temporary_settings(
            {
                PREFECT_API_DATABASE_CONNECTION_URL: None,
                PREFECT_API_DATABASE_DRIVER: "sqlite+aiosqlite",
            }
        ):
            url = make_url(PREFECT_API_DATABASE_CONNECTION_URL.value())
            assert url.drivername == "sqlite+aiosqlite"
            assert url.database == f"{PREFECT_HOME.value()}/prefect.db"

    def test_unknown_driver_raises(self):
        with pytest.raises(pydantic.ValidationError, match="literal_error"):
            with temporary_settings(
                {
                    PREFECT_API_DATABASE_CONNECTION_URL: None,
                    PREFECT_API_DATABASE_DRIVER: "wat",
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
                PREFECT_API_DATABASE_USER: "the-user",
            }
        ):
            url = make_url(PREFECT_API_DATABASE_CONNECTION_URL.value())
            assert url.drivername == "postgresql+asyncpg"
            assert url.host == "the-database-server.example.com"
            assert url.port == 5432
            assert url.username == "the-user"
            assert url.database == "the-database"
            assert url.password == "the-$password"


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
        set_keys = set(settings.model_dump(exclude_unset=True).keys())
        with temporary_settings() as new_settings:
            pass
        new_set_keys = set(new_settings.model_dump(exclude_unset=True).keys())
        assert new_set_keys == set_keys

    def test_temporary_settings_can_restore_to_defaults_values(self):
        with temporary_settings(updates={PREFECT_API_DATABASE_PORT: 9001}):
            assert PREFECT_API_DATABASE_PORT.value() == 9001
            with temporary_settings(restore_defaults={PREFECT_API_DATABASE_PORT}):
                assert (
                    PREFECT_API_DATABASE_PORT.value()
                    == PREFECT_API_DATABASE_PORT.default()
                )

    def test_temporary_settings_restores_on_error(self):
        assert PREFECT_TEST_MODE.value() is True

        with pytest.raises(ValueError):
            with temporary_settings(updates={PREFECT_TEST_MODE: False}):
                raise ValueError()

        assert os.environ["PREFECT_TEST_MODE"] == "1", "Does not alter os environ."
        assert PREFECT_TEST_MODE.value() is True


class TestSettingsSources:
    @pytest.fixture
    def temporary_env_file(self):
        original_env_content = None
        env_file = Path(".env")

        if env_file.exists():
            original_env_content = env_file.read_text()

        def _create_temp_env(content):
            env_file.write_text(content)

        yield _create_temp_env

        if env_file.exists():
            env_file.unlink()

        if original_env_content is not None:
            env_file.write_text(original_env_content)

    def test_env_source(self, temporary_env_file):
        temporary_env_file("PREFECT_CLIENT_RETRY_EXTRA_CODES=420,500")

        assert Settings().client_retry_extra_codes == {420, 500}

        os.unlink(".env")

        assert Settings().client_retry_extra_codes == set()

    def test_resolution_order(self, temporary_env_file, monkeypatch, tmp_path):
        profiles_path = tmp_path / "profiles.toml"

        monkeypatch.delenv("PREFECT_TEST_MODE", raising=False)
        monkeypatch.delenv("PREFECT_UNIT_TEST_MODE", raising=False)
        monkeypatch.setenv("PREFECT_PROFILES_PATH", str(profiles_path))

        profiles_path.write_text(
            textwrap.dedent(
                """
                active = "foo"

                [profiles.foo]
                PREFECT_CLIENT_RETRY_EXTRA_CODES = "420,500"
                """
            )
        )

        assert Settings().client_retry_extra_codes == {420, 500}

        temporary_env_file("PREFECT_CLIENT_RETRY_EXTRA_CODES=429,500")

        assert Settings().client_retry_extra_codes == {429, 500}

        os.unlink(".env")

        assert Settings().client_retry_extra_codes == {420, 500}

        monkeypatch.setenv("PREFECT_TEST_MODE", "1")
        monkeypatch.setenv("PREFECT_UNIT_TEST_MODE", "1")
        monkeypatch.delenv("PREFECT_PROFILES_PATH", raising=True)

        assert Settings().client_retry_extra_codes == set()


class TestLoadProfiles:
    @pytest.fixture(autouse=True)
    def temporary_profiles_path(self, tmp_path):
        path = tmp_path / "profiles.toml"
        with temporary_settings(updates={PREFECT_PROFILES_PATH: path}):
            yield path

    def test_load_profiles_no_profiles_file(self):
        assert load_profiles()

    def test_load_profiles_missing_ephemeral(self, temporary_profiles_path):
        temporary_profiles_path.write_text(
            textwrap.dedent(
                """
                [profiles.foo]
                PREFECT_API_KEY = "bar"
                """
            )
        )
        assert load_profiles()["foo"].settings == {PREFECT_API_KEY: "bar"}
        assert isinstance(load_profiles()["ephemeral"].settings, dict)

    def test_load_profiles_only_active_key(self, temporary_profiles_path):
        temporary_profiles_path.write_text(
            textwrap.dedent(
                """
                active = "ephemeral"
                """
            )
        )
        assert load_profiles().active_name == "ephemeral"
        assert isinstance(load_profiles()["ephemeral"].settings, dict)

    def test_load_profiles_empty_file(self, temporary_profiles_path):
        temporary_profiles_path.touch()
        assert load_profiles().active_name == "ephemeral"
        assert isinstance(load_profiles()["ephemeral"].settings, dict)

    def test_load_profiles_with_ephemeral(self, temporary_profiles_path):
        temporary_profiles_path.write_text(
            """
            [profiles.ephemeral]
            PREFECT_API_KEY = "foo"

            [profiles.bar]
            PREFECT_API_KEY = "bar"
            """
        )
        profiles = load_profiles()
        expected = {
            "ephemeral": {
                PREFECT_API_KEY: "foo",
                PREFECT_SERVER_ALLOW_EPHEMERAL_MODE: "true",  # default value
            },
            "bar": {PREFECT_API_KEY: "bar"},
        }
        for name, settings in expected.items():
            assert profiles[name].settings == settings
            assert profiles[name].source == temporary_profiles_path

    def test_load_profile_ephemeral(self):
        assert load_profile("ephemeral") == Profile(
            name="ephemeral",
            settings={PREFECT_SERVER_ALLOW_EPHEMERAL_MODE: "true"},
            source=DEFAULT_PROFILES_PATH,
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
        with pytest.raises(UserWarning, match="Setting 'nested' is not recognized"):
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
        with pytest.warns(UserWarning, match="Setting 'test' is not recognized"):
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
                PREFECT_API_KEY = "1"

                [profiles.bar]
                PREFECT_API_KEY = "2"
                """
            ).lstrip()
        )


class TestProfile:
    def test_init_casts_names_to_setting_types(self):
        profile = Profile(name="test", settings={"PREFECT_DEBUG_MODE": 1})
        assert profile.settings == {PREFECT_DEBUG_MODE: 1}

    def test_validate_settings(self):
        profile = Profile(name="test", settings={PREFECT_SERVER_API_PORT: "foo"})
        with pytest.raises(
            ProfileSettingsValidationError, match="should be a valid integer"
        ):
            profile.validate_settings()

    def test_validate_settings_ignores_environment_variables(self, monkeypatch):
        """
        If using `context.use_profile` to validate settings, environment variables may
        override the setting and hide validation errors
        """
        monkeypatch.setenv("PREFECT_SERVER_API_PORT", "1234")
        profile = Profile(name="test", settings={PREFECT_SERVER_API_PORT: "foo"})
        with pytest.raises(
            ProfileSettingsValidationError, match="should be a valid integer"
        ):
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

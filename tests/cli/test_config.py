import pytest

import prefect.context
import prefect.settings
from prefect.context import use_profile
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_LOGGING_ORION_MAX_LOG_SIZE,
    PREFECT_ORION_DATABASE_TIMEOUT,
    PREFECT_PROFILES_PATH,
    PREFECT_TEST_SETTING,
    SETTING_VARIABLES,
    Profile,
    ProfilesCollection,
    load_profiles,
    save_profiles,
    temporary_settings,
)
from prefect.testing.cli import invoke_and_assert

# Source strings displayed by `prefect config view`
FROM_DEFAULT = "(from defaults)"
FROM_ENV = "(from env)"
FROM_PROFILE = "(from profile)"


@pytest.fixture(autouse=True)
def temporary_profiles_path(tmp_path):
    path = tmp_path / "profiles.toml"
    with temporary_settings({PREFECT_PROFILES_PATH: path}):
        yield path


def test_set_using_default_profile():
    with use_profile("default"):
        invoke_and_assert(
            ["config", "set", "PREFECT_TEST_SETTING=DEBUG"],
            expected_output=(
                """
                Set 'PREFECT_TEST_SETTING' to 'DEBUG'.
                Updated profile 'default'.
                """
            ),
        )

    profiles = load_profiles()
    assert "default" in profiles
    assert profiles["default"].settings == {PREFECT_TEST_SETTING: "DEBUG"}


def test_set_using_profile_flag():
    save_profiles(ProfilesCollection([Profile(name="foo", settings={})], active=None))

    invoke_and_assert(
        ["--profile", "foo", "config", "set", "PREFECT_TEST_SETTING=DEBUG"],
        expected_output=(
            """
            Set 'PREFECT_TEST_SETTING' to 'DEBUG'.
            Updated profile 'foo'.
            """
        ),
    )

    profiles = load_profiles()
    assert "foo" in profiles
    assert profiles["foo"].settings == {PREFECT_TEST_SETTING: "DEBUG"}


def test_set_with_unknown_setting():
    save_profiles(ProfilesCollection([Profile(name="foo", settings={})], active=None))

    invoke_and_assert(
        ["--profile", "foo", "config", "set", "PREFECT_FOO=BAR"],
        expected_output=(
            """
            Unknown setting name 'PREFECT_FOO'.
            """
        ),
        expected_code=1,
    )


def test_set_with_invalid_value_type():
    save_profiles(ProfilesCollection([Profile(name="foo", settings={})], active=None))

    invoke_and_assert(
        ["--profile", "foo", "config", "set", "PREFECT_ORION_DATABASE_TIMEOUT=HELLO"],
        expected_output=(
            """
            Validation error for setting 'PREFECT_ORION_DATABASE_TIMEOUT': value is not a valid float
            Invalid setting value.
            """
        ),
        expected_code=1,
    )

    profiles = load_profiles()
    assert (
        PREFECT_ORION_DATABASE_TIMEOUT not in profiles["foo"].settings
    ), "The setting should not be saved"


def test_set_with_unparsable_setting():
    save_profiles(ProfilesCollection([Profile(name="foo", settings={})], active=None))

    invoke_and_assert(
        ["--profile", "foo", "config", "set", "PREFECT_FOO_BAR"],
        expected_output=(
            """
            Failed to parse argument 'PREFECT_FOO_BAR'. Use the format 'VAR=VAL'.
            """
        ),
        expected_code=1,
    )


def test_set_setting_with_equal_sign_in_value():
    save_profiles(ProfilesCollection([Profile(name="foo", settings={})], active=None))

    invoke_and_assert(
        ["--profile", "foo", "config", "set", "PREFECT_API_KEY=foo=bar"],
        expected_output=(
            """
            Set 'PREFECT_API_KEY' to 'foo=bar'.
            Updated profile 'foo'.
            """
        ),
    )

    profiles = load_profiles()
    assert "foo" in profiles
    assert profiles["foo"].settings == {PREFECT_API_KEY: "foo=bar"}


def test_set_multiple_settings():
    save_profiles(ProfilesCollection([Profile(name="foo", settings={})], active=None))

    invoke_and_assert(
        [
            "--profile",
            "foo",
            "config",
            "set",
            "PREFECT_API_KEY=FOO",
            "PREFECT_TEST_SETTING=DEBUG",
        ],
        expected_output=(
            """
            Set 'PREFECT_API_KEY' to 'FOO'.
            Set 'PREFECT_TEST_SETTING' to 'DEBUG'.
            Updated profile 'foo'.
            """
        ),
    )

    profiles = load_profiles()
    assert "foo" in profiles
    assert profiles["foo"].settings == {
        PREFECT_TEST_SETTING: "DEBUG",
        PREFECT_API_KEY: "FOO",
    }


def test_unset_retains_other_keys():
    save_profiles(
        ProfilesCollection(
            [
                Profile(
                    name="foo",
                    settings={
                        PREFECT_TEST_SETTING: "DEBUG",
                        PREFECT_API_KEY: "FOO",
                    },
                )
            ],
            active=None,
        )
    )

    invoke_and_assert(
        [
            "--profile",
            "foo",
            "config",
            "unset",
            "PREFECT_API_KEY",
        ],
        expected_output=(
            """
            Unset 'PREFECT_API_KEY'.
            Updated profile 'foo'.
            """
        ),
    )

    profiles = load_profiles()
    assert "foo" in profiles
    assert profiles["foo"].settings == {PREFECT_TEST_SETTING: "DEBUG"}


def test_unset_warns_if_present_in_environment(monkeypatch):
    monkeypatch.setenv("PREFECT_API_KEY", "TEST")
    save_profiles(
        ProfilesCollection(
            [
                Profile(
                    name="foo",
                    settings={PREFECT_API_KEY: "FOO"},
                )
            ],
            active=None,
        )
    )

    invoke_and_assert(
        [
            "--profile",
            "foo",
            "config",
            "unset",
            "PREFECT_API_KEY",
        ],
        expected_output=(
            """
            Unset 'PREFECT_API_KEY'.
            'PREFECT_API_KEY' is also set by an environment variable. Use `unset PREFECT_API_KEY` to clear it.
            Updated profile 'foo'.
            """
        ),
    )

    profiles = load_profiles()
    assert "foo" in profiles
    assert profiles["foo"].settings == {}


def test_unset_with_unknown_setting():
    save_profiles(ProfilesCollection([Profile(name="foo", settings={})], active=None))

    invoke_and_assert(
        ["--profile", "foo", "config", "unset", "PREFECT_FOO"],
        expected_output=(
            """
            Unknown setting name 'PREFECT_FOO'.
            """
        ),
        expected_code=1,
    )


def test_unset_with_setting_not_in_profile():
    save_profiles(
        ProfilesCollection(
            [
                Profile(
                    name="foo",
                    settings={PREFECT_API_KEY: "FOO"},
                )
            ],
            active=None,
        )
    )

    invoke_and_assert(
        [
            "--profile",
            "foo",
            "config",
            "unset",
            "PREFECT_TEST_SETTING",
        ],
        expected_output=(
            """
           'PREFECT_TEST_SETTING' is not set in profile 'foo'.
            """
        ),
        expected_code=1,
    )


def test_unset_multiple_settings():
    save_profiles(
        ProfilesCollection(
            [
                Profile(
                    name="foo",
                    settings={
                        PREFECT_TEST_SETTING: "DEBUG",
                        PREFECT_API_KEY: "FOO",
                    },
                )
            ],
            active=None,
        )
    )

    invoke_and_assert(
        [
            "--profile",
            "foo",
            "config",
            "unset",
            "PREFECT_API_KEY",
            "PREFECT_TEST_SETTING",
        ],
        expected_output=(
            """
            Unset 'PREFECT_API_KEY'.
            Unset 'PREFECT_TEST_SETTING'.
            Updated profile 'foo'.
            """
        ),
    )

    profiles = load_profiles()
    assert "foo" in profiles
    assert profiles["foo"].settings == {}


def test_view_excludes_unset_settings_without_show_defaults_flag(monkeypatch):
    # Clear the environment
    for key in SETTING_VARIABLES:
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("PREFECT_ORION_DATABASE_CONNECTION_TIMEOUT", "2.5")

    with prefect.context.use_profile(
        prefect.settings.Profile(
            name="foo",
            settings={
                PREFECT_ORION_DATABASE_TIMEOUT: 2.0,
                PREFECT_LOGGING_ORION_MAX_LOG_SIZE: 1000001,
            },
        ),
        include_current_context=True,
    ) as ctx:
        res = invoke_and_assert(["config", "view", "--hide-sources"])

        # Collect just settings that are set
        expected = ctx.settings.dict(exclude_unset=True)

    lines = res.stdout.splitlines()
    assert lines[0] == "PREFECT_PROFILE='foo'"

    # Parse the output for settings displayed, skip the first PREFECT_PROFILE line
    printed_settings = {}
    for line in lines[1:]:
        setting, value = line.split("=", maxsplit=1)
        assert (
            setting not in printed_settings
        ), f"Setting displayed multiple times: {setting}"
        printed_settings[setting] = value

    assert set(printed_settings.keys()) == set(
        expected.keys()
    ), "Only set keys should be included."

    for key, value in printed_settings.items():
        # windows display duplicates slashes
        if "\\" in value:
            continue
        if SETTING_VARIABLES[key].is_secret:
            continue
        assert (
            repr(str(expected[key])) == value
        ), "Displayed setting does not match set value."

    assert len(expected) < len(
        SETTING_VARIABLES
    ), "All settings were expected; we should only have a subset."


def test_view_includes_unset_settings_with_show_defaults():
    expected_settings = (
        prefect.settings.get_current_settings().with_obfuscated_secrets().dict()
    )

    res = invoke_and_assert(["config", "view", "--show-defaults", "--hide-sources"])

    lines = res.stdout.splitlines()

    # Parse the output for settings displayed, skip the first PREFECT_PROFILE line
    printed_settings = {}
    for line in lines[1:]:
        setting, value = line.split("=", maxsplit=1)
        assert (
            setting not in printed_settings
        ), f"Setting displayed multiple times: {setting}"
        printed_settings[setting] = value

    assert (
        printed_settings.keys() == SETTING_VARIABLES.keys()
    ), "All settings should be displayed"

    for key, value in printed_settings.items():
        assert (
            value == f"'{expected_settings[key]}'"
        ), "Displayed setting does not match set value."


@pytest.mark.parametrize(
    "command",
    [
        ["config", "view"],  # --show-sources is default behavior
        ["config", "view", "--show-sources"],
        ["config", "view", "--show-defaults"],
    ],
)
def test_view_shows_setting_sources(monkeypatch, command):
    monkeypatch.setenv("PREFECT_ORION_DATABASE_CONNECTION_TIMEOUT", "2.5")

    with prefect.context.use_profile(
        prefect.settings.Profile(
            name="foo",
            settings={
                PREFECT_ORION_DATABASE_TIMEOUT: 2.0,
                PREFECT_LOGGING_ORION_MAX_LOG_SIZE: 1000001,
            },
        )
    ):
        res = invoke_and_assert(command)

    lines = res.stdout.splitlines()

    # The first line should not include a source
    assert lines[0] == "PREFECT_PROFILE='foo'"

    for line in lines[1:]:
        # Assert that each line ends with a source
        assert any(
            line.endswith(s) for s in [FROM_DEFAULT, FROM_PROFILE, FROM_ENV]
        ), f"Source missing from line: {line}"

    # Assert that sources are correct
    assert f"PREFECT_ORION_DATABASE_TIMEOUT='2.0' {FROM_PROFILE}" in lines
    assert f"PREFECT_LOGGING_ORION_MAX_LOG_SIZE='1000001' {FROM_PROFILE}" in lines
    assert f"PREFECT_ORION_DATABASE_CONNECTION_TIMEOUT='2.5' {FROM_ENV}" in lines

    if "--show-defaults" in command:
        # Check that defaults sources are correct by checking an unset setting
        assert (
            f"PREFECT_ORION_SERVICES_SCHEDULER_LOOP_SECONDS='60.0' {FROM_DEFAULT}"
            in lines
        )


@pytest.mark.parametrize(
    "command",
    [
        ["config", "view", "--hide-sources"],
        ["config", "view", "--hide-sources", "--show-defaults"],
    ],
)
def test_view_with_hide_sources_excludes_sources(monkeypatch, command):
    monkeypatch.setenv("PREFECT_ORION_DATABASE_CONNECTION_TIMEOUT", "2.5")

    with prefect.context.use_profile(
        prefect.settings.Profile(
            name="foo",
            settings={
                PREFECT_ORION_DATABASE_TIMEOUT: 2.0,
                PREFECT_LOGGING_ORION_MAX_LOG_SIZE: 1000001,
            },
        ),
    ):
        res = invoke_and_assert(command)

    lines = res.stdout.splitlines()

    for line in lines:
        # Assert that each line does not end with a source
        assert not any(
            line.endswith(s) for s in [FROM_DEFAULT, FROM_PROFILE, FROM_ENV]
        ), f"Source included in line: {line}"

    # Ensure that the settings that we know are set are still included
    assert f"PREFECT_ORION_DATABASE_TIMEOUT='2.0'" in lines
    assert f"PREFECT_LOGGING_ORION_MAX_LOG_SIZE='1000001'" in lines
    assert f"PREFECT_ORION_DATABASE_CONNECTION_TIMEOUT='2.5'" in lines

    if "--show-defaults" in command:
        # Check that defaults are included correctly by checking an unset setting
        assert f"PREFECT_ORION_SERVICES_SCHEDULER_LOOP_SECONDS='60.0'" in lines


@pytest.mark.parametrize(
    "command",
    [
        ["config", "view"],  # --hide-secrets is default behavior
        ["config", "view", "--hide-secrets"],
        ["config", "view", "--show-defaults"],
    ],
)
def test_view_obfuscates_secrets(monkeypatch, command):
    monkeypatch.setenv("PREFECT_ORION_DATABASE_CONNECTION_URL", "secret-connection-url")

    with prefect.context.use_profile(
        prefect.settings.Profile(
            name="foo",
            settings={PREFECT_API_KEY: "secret-api-key"},
        ),
        include_current_context=False,
    ):
        res = invoke_and_assert(command)

    lines = res.stdout.splitlines()
    assert f"PREFECT_ORION_DATABASE_CONNECTION_URL='********' {FROM_ENV}" in lines
    assert f"PREFECT_API_KEY='********' {FROM_PROFILE}" in lines

    if "--show-defaults" in command:
        assert f"PREFECT_ORION_DATABASE_PASSWORD='********' {FROM_DEFAULT}" in lines

    assert "secret-" not in res.stdout


@pytest.mark.parametrize(
    "command",
    [
        ["config", "view", "--show-secrets"],
        ["config", "view", "--show-secrets", "--show-defaults"],
    ],
)
def test_view_shows_secrets(monkeypatch, command):
    monkeypatch.setenv("PREFECT_ORION_DATABASE_CONNECTION_URL", "secret-connection-url")

    with prefect.context.use_profile(
        prefect.settings.Profile(
            name="foo",
            settings={PREFECT_API_KEY: "secret-api-key"},
        ),
        include_current_context=False,
    ):
        res = invoke_and_assert(command)

    lines = res.stdout.splitlines()

    assert (
        f"PREFECT_ORION_DATABASE_CONNECTION_URL='secret-connection-url' {FROM_ENV}"
        in lines
    )
    assert f"PREFECT_API_KEY='secret-api-key' {FROM_PROFILE}" in lines

    if "--show-defaults" in command:
        assert f"PREFECT_ORION_DATABASE_PASSWORD='None' {FROM_DEFAULT}" in lines

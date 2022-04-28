import re
import textwrap
from typing import Any, List

import pytest
import rich
from typer.testing import CliRunner, Result

from prefect.cli import app
from prefect.context import SettingsContext, use_profile
from prefect.settings import (
    DEFAULT_PROFILES_PATH,
    PREFECT_API_KEY,
    PREFECT_DEBUG_MODE,
    PREFECT_PROFILES_PATH,
    Profile,
    ProfilesCollection,
    get_current_settings,
    load_profiles,
    save_profiles,
    temporary_settings,
)


def invoke_and_assert(
    command: List[str],
    expected_output: str = None,
    expected_code: int = 0,
    echo: bool = True,
) -> Result:
    runner = CliRunner()
    result = runner.invoke(app, command, catch_exceptions=False)

    if echo:
        print(result.stdout)

    if expected_code is not None:
        assert result.exit_code == expected_code

    if expected_output is not None:
        output = result.stdout.strip()
        expected_output = textwrap.dedent(expected_output).strip()

        print("------ expected ------")
        print(expected_output)
        print()

        assert output == expected_output

    return result


@pytest.fixture(autouse=True)
def temporary_profiles_path(tmp_path):
    path = tmp_path / "profiles.toml"
    with temporary_settings({PREFECT_PROFILES_PATH: path}):
        yield path


@pytest.fixture()
def disable_terminal_wrapping(monkeypatch):
    monkeypatch.setattr(
        "prefect.cli.profile.console", rich.console.Console(soft_wrap=True)
    )


def test_use_profile_unknown_key():
    invoke_and_assert(
        ["profile", "use", "foo"],
        expected_code=1,
        expected_output="Profile 'foo' not found.",
    )


def test_use_profile_sets_active():
    save_profiles(
        ProfilesCollection(profiles=[Profile(name="foo", settings={})], active="bar")
    )

    invoke_and_assert(
        ["profile", "use", "foo"], expected_output="Profile 'foo' now active."
    )

    profiles = load_profiles()
    assert profiles.active_name == "foo"


def test_ls_default_profiles():
    # 'default' is not the current profile because we have a temporary profile in-use
    # during tests

    invoke_and_assert(["profile", "ls"], expected_output="default")


def test_ls_additional_profiles():
    # 'default' is not the current profile because we have a temporary profile in-use
    # during tests

    save_profiles(
        ProfilesCollection(
            profiles=[
                Profile(name="foo", settings={}),
                Profile(name="bar", settings={}),
            ],
            active=None,
        )
    )

    invoke_and_assert(
        ["profile", "ls"],
        expected_output=(
            """
            default
            foo
            bar
            """
        ),
    )


def test_ls_respects_current_from_profile_flag():
    save_profiles(
        ProfilesCollection(
            profiles=[
                Profile(name="foo", settings={}),
            ],
            active=None,
        )
    )

    invoke_and_assert(
        ["--profile", "foo", "profile", "ls"],
        expected_output=(
            """
            default
            * foo
            """
        ),
    )


def test_ls_respects_current_from_context():
    save_profiles(
        ProfilesCollection(
            profiles=[
                Profile(name="foo", settings={}),
                Profile(name="bar", settings={}),
            ],
            active=None,
        )
    )

    with use_profile("bar"):
        invoke_and_assert(
            ["profile", "ls"],
            expected_output=(
                """
                default
                foo
                * bar
                """
            ),
        )


def test_create_profile():
    invoke_and_assert(
        ["profile", "create", "foo"],
        expected_output=(
            f"""
            Created profile 'foo'.

            Switch to your new profile with:

                prefect profile use 'foo'

            Or, to use it for a single command, include the `-p` option:

                prefect -p 'foo' config view
            """
        ),
    )

    profiles = load_profiles()
    assert profiles["foo"] == Profile(
        name="foo", settings={}, source=PREFECT_PROFILES_PATH.value()
    )


def test_create_profile_from_existing():
    save_profiles(
        ProfilesCollection(
            profiles=[
                Profile(name="foo", settings={PREFECT_API_KEY: "foo"}),
            ],
            active=None,
        )
    )

    invoke_and_assert(
        ["profile", "create", "bar", "--from", "foo"],
        expected_output=(
            f"""
            Created profile 'bar' matching 'foo'.

            Switch to your new profile with:

                prefect profile use 'bar'

            Or, to use it for a single command, include the `-p` option:

                prefect -p 'bar' config view
            """
        ),
    )

    profiles = load_profiles()
    assert profiles["foo"].settings == {PREFECT_API_KEY: "foo"}, "Foo is unchanged"
    assert profiles["bar"] == Profile(
        name="bar",
        settings={PREFECT_API_KEY: "foo"},
        source=PREFECT_PROFILES_PATH.value(),
    )


def test_create_profile_from_unknown_profile():
    invoke_and_assert(
        ["profile", "create", "bar", "--from", "foo"],
        expected_output="Profile 'foo' not found.",
        expected_code=1,
    )


def test_create_profile_with_existing_profile():
    invoke_and_assert(
        ["profile", "create", "default"],
        expected_output=(
            """
            Profile 'default' already exists.
            To create a new profile, remove the existing profile first:

                prefect profile delete 'default'
            """
        ),
        expected_code=1,
    )


def test_delete_profile():
    save_profiles(
        ProfilesCollection(
            profiles=[
                Profile(name="foo", settings={PREFECT_API_KEY: "foo"}),
                Profile(name="bar", settings={PREFECT_API_KEY: "bar"}),
            ],
            active=None,
        )
    )

    invoke_and_assert(
        ["profile", "delete", "bar"], expected_output="Removed profile 'bar'."
    )

    profiles = load_profiles()
    assert "foo" in profiles
    assert "bar" not in profiles


def test_delete_profile_default_is_reset():
    save_profiles(
        ProfilesCollection(
            profiles=[
                Profile(name="default", settings={PREFECT_API_KEY: "foo"}),
            ],
            active=None,
        )
    )

    invoke_and_assert(
        ["profile", "delete", "default"], expected_output="Reset profile 'default'."
    )

    profiles = load_profiles()
    assert profiles["default"] == Profile(
        name="default",
        settings={},
        source=DEFAULT_PROFILES_PATH,
    )


def test_delete_profile_unknown_name():
    invoke_and_assert(
        ["profile", "delete", "foo"],
        expected_output="Profile 'foo' not found.",
        expected_code=1,
    )


def test_rename_profile_name_exists():
    save_profiles(
        ProfilesCollection(
            profiles=[
                Profile(name="foo", settings={}),
                Profile(name="bar", settings={}),
            ],
            active=None,
        )
    )

    invoke_and_assert(
        ["profile", "rename", "foo", "bar"],
        expected_output="Profile 'bar' already exists.",
        expected_code=1,
    )


def test_rename_profile_unknown_name():
    invoke_and_assert(
        ["profile", "rename", "foo", "bar"],
        expected_output="Profile 'foo' not found.",
        expected_code=1,
    )


def test_inspect_profile_unknown_name():
    invoke_and_assert(
        ["profile", "inspect", "foo"],
        expected_output="Profile 'foo' not found.",
        expected_code=1,
    )


def test_inspect_profile():
    save_profiles(
        ProfilesCollection(
            profiles=[
                Profile(
                    name="foo",
                    settings={PREFECT_API_KEY: "foo", PREFECT_DEBUG_MODE: True},
                ),
            ],
            active=None,
        )
    )

    invoke_and_assert(
        ["profile", "inspect", "foo"],
        expected_output=(
            """
            PREFECT_API_KEY='foo'
            PREFECT_DEBUG_MODE='True'
            """
        ),
    )


def test_inspect_profile_without_settings():
    save_profiles(
        ProfilesCollection(
            profiles=[Profile(name="foo", settings={})],
            active=None,
        )
    )

    invoke_and_assert(
        ["profile", "inspect", "foo"],
        expected_output=(
            """
            Profile 'foo' is empty.
            """
        ),
    )

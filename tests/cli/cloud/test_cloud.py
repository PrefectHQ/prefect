import sys
import urllib.parse
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
import readchar
import respx
from starlette import status
from typer import Exit

from prefect.cli.cloud import LoginFailed, LoginSuccess
from prefect.client.schemas import Workspace
from prefect.context import get_settings_context, use_profile
from prefect.logging.configuration import setup_logging
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_URL,
    PREFECT_CLOUD_API_URL,
    PREFECT_CLOUD_UI_URL,
    PREFECT_PROFILES_PATH,
    Profile,
    ProfilesCollection,
    load_current_profile,
    load_profiles,
    save_profiles,
    temporary_settings,
)
from prefect.testing.cli import invoke_and_assert


def gen_test_workspace(**kwargs: Any) -> Workspace:
    kwargs.setdefault("account_id", uuid.uuid4())
    kwargs.setdefault("account_name", "account name")
    kwargs.setdefault("account_handle", "account-handle")
    kwargs.setdefault("workspace_id", uuid.uuid4())
    kwargs.setdefault("workspace_name", "workspace name")
    kwargs.setdefault("workspace_handle", "workspace-handle")
    kwargs.setdefault("workspace_description", "workspace description")
    return Workspace(**kwargs)


@pytest.fixture
def interactive_console(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("prefect.cli.cloud.is_interactive", lambda: True)

    # `readchar` does not like the fake stdin provided by typer isolation so we provide
    # a version that does not require a fd to be attached
    def readchar() -> str:
        sys.stdin.flush()
        position = sys.stdin.tell()
        remaining_input = sys.stdin.read()

        if not remaining_input:
            print("TEST ERROR: CLI is attempting to read input but stdin is empty.")
            raise Exit(-2)

        # Take the first character and put the rest back
        char = remaining_input[0]
        rest = remaining_input[1:]

        # Reset stdin position and write back the remaining input
        sys.stdin.seek(position)
        sys.stdin.truncate()
        if rest:
            sys.stdin.write(rest)
            sys.stdin.seek(position)

        return char

    monkeypatch.setattr("readchar._posix_read.readchar", readchar)


@pytest.fixture(autouse=True)
def restore_logging_setup():
    yield
    # Uvicorn is a maniac and will set logging to their configuration on startup
    setup_logging(incremental=False)


@pytest.fixture(autouse=True)
def temporary_profiles_path(tmp_path: Path):
    path = tmp_path / "profiles.toml"
    with temporary_settings({PREFECT_PROFILES_PATH: path}):
        # Ensure the test profile is persisted already to simplify assertions
        save_profiles(
            profiles=ProfilesCollection(profiles=[get_settings_context().profile])
        )
        yield path


@pytest.fixture
def mock_webbrowser(monkeypatch: pytest.MonkeyPatch):
    mock = MagicMock()
    monkeypatch.setattr("prefect.cli.cloud.webbrowser", mock)
    yield mock


@pytest.mark.parametrize(
    "key,expected_output",
    [
        (
            "pcu_foo",
            (
                "Unable to authenticate with Prefect Cloud. It looks like you're using"
                " API key from Cloud 1 (https://cloud.prefect.io). Make sure that you"
                " generate API key using Cloud 2 (https://app.prefect.cloud)"
            ),
        ),
        (
            "pnu_foo",
            (
                "Unable to authenticate with Prefect Cloud. Please ensure your"
                " credentials are correct and unexpired."
            ),
        ),
        (
            "foo",
            (
                "Unable to authenticate with Prefect Cloud. Your key is not in our"
                " expected format: 'pnu_' or 'pnb_'."
            ),
        ),
    ],
)
def test_login_with_invalid_key(
    key: str, expected_output: str, respx_mock: respx.MockRouter
):
    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(status.HTTP_403_FORBIDDEN)
    )
    invoke_and_assert(
        ["cloud", "login", "--key", key, "--workspace", "foo"],
        expected_code=1,
        expected_output=expected_output,
    )


@pytest.mark.parametrize(
    "key",
    [
        "pnu_foo",
        "foo",
    ],
)
def test_login_with_prefect_api_key_env_var_different_than_key_exits_with_error(
    key: str, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("PREFECT_API_KEY", "pnu_baz")
    invoke_and_assert(
        ["cloud", "login", "--key", key, "--workspace", "foo"],
        expected_code=1,
        expected_output=(
            "Cannot log in with a key when a different PREFECT_API_KEY is present"
            " as an environment variable that will override it."
        ),
    )


@pytest.mark.parametrize(
    "env_var_api_key,key,expected_output",
    [
        (
            "pnu_foo",
            "pnu_foo",
            (
                "Unable to authenticate with Prefect Cloud. Please ensure your"
                " credentials are correct and unexpired."
            ),
        ),
        (
            "foo",
            "foo",
            (
                "Unable to authenticate with Prefect Cloud. Your key is not in our"
                " expected format: 'pnu_' or 'pnb_'."
            ),
        ),
    ],
)
def test_login_with_prefect_api_key_env_var_equal_to_invalid_key_exits_with_error(
    key: str, expected_output: str, env_var_api_key: str, respx_mock: respx.MockRouter
):
    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(status.HTTP_403_FORBIDDEN)
    )
    with temporary_settings({PREFECT_API_KEY: env_var_api_key}):
        invoke_and_assert(
            ["cloud", "login", "--key", key, "--workspace", "test/foo"],
            expected_code=1,
            expected_output=(expected_output),
        )


def test_login_with_prefect_api_key_env_var_equal_to_valid_key_succeeds(
    respx_mock: respx.MockRouter,
):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[foo_workspace.model_dump(mode="json")],
        )
    )

    with temporary_settings({PREFECT_API_KEY: "pnu_foo"}):
        invoke_and_assert(
            ["cloud", "login", "--key", "pnu_foo", "--workspace", "test/foo"],
            expected_code=0,
            expected_output=(
                "Authenticated with Prefect Cloud! Using workspace 'test/foo'."
            ),
        )


def test_login_with_key_and_missing_workspace(respx_mock: respx.MockRouter):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
    bar_workspace = gen_test_workspace(account_handle="test", workspace_handle="bar")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[
                foo_workspace.model_dump(mode="json"),
                bar_workspace.model_dump(mode="json"),
            ],
        )
    )

    invoke_and_assert(
        ["cloud", "login", "--key", "foo", "--workspace", "apple/berry"],
        expected_code=1,
        expected_output=(
            "Workspace 'apple/berry' not found. Available workspaces: 'test/foo',"
            " 'test/bar'"
        ),
    )


def test_login_with_key_and_workspace_with_no_workspaces(respx_mock: respx.MockRouter):
    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(status.HTTP_200_OK, json=[])
    )
    invoke_and_assert(
        ["cloud", "login", "--key", "foo", "--workspace", "bar"],
        expected_code=1,
        expected_output="Workspace 'bar' not found.",
    )


def test_login_with_key_and_workspace(respx_mock: respx.MockRouter):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
    bar_workspace = gen_test_workspace(account_handle="test", workspace_handle="bar")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[
                foo_workspace.model_dump(mode="json"),
                bar_workspace.model_dump(mode="json"),
            ],
        )
    )

    invoke_and_assert(
        ["cloud", "login", "--key", "foo", "--workspace", "test/foo"],
        expected_code=0,
        expected_output="Authenticated with Prefect Cloud! Using workspace 'test/foo'.",
    )

    settings = load_current_profile().settings
    assert settings[PREFECT_API_KEY] == "foo"
    assert settings[PREFECT_API_URL] == foo_workspace.api_url()


@pytest.mark.parametrize("args", [[], ["--workspace", "test/foo"], ["--key", "key"]])
def test_login_with_non_interactive_missing_args(args: list[str]):
    invoke_and_assert(
        ["cloud", "login", *args],
        expected_code=1,
        expected_output=(
            "When not using an interactive terminal, you must supply a `--key` and"
            " `--workspace`."
        ),
    )


def test_login_with_key_and_workspace_overrides_current_workspace(
    respx_mock: respx.MockRouter,
):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
    bar_workspace = gen_test_workspace(account_handle="test", workspace_handle="bar")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[
                foo_workspace.model_dump(mode="json"),
                bar_workspace.model_dump(mode="json"),
            ],
        )
    )

    # Set up a current profile with a different workspace
    profiles = load_profiles()
    profiles.set_active("ephemeral")
    assert profiles.active_profile is not None
    profiles.active_profile.settings[PREFECT_API_URL] = foo_workspace.api_url()
    assert profiles.active_profile.settings[PREFECT_API_URL] == foo_workspace.api_url()

    invoke_and_assert(
        ["cloud", "login", "--key", "new_key", "--workspace", "test/bar"],
        expected_code=0,
        expected_output="Authenticated with Prefect Cloud! Using workspace 'test/bar'.",
    )

    settings = load_current_profile().settings
    assert settings[PREFECT_API_KEY] == "new_key"
    assert settings[PREFECT_API_URL] == bar_workspace.api_url()


@pytest.mark.usefixtures("interactive_console")
def test_login_with_key_and_no_workspaces(respx_mock: respx.MockRouter):
    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[],
        )
    )
    invoke_and_assert(
        ["cloud", "login", "--key", "foo"],
        expected_code=1,
        user_input=readchar.key.ENTER,
        expected_output_contains=[
            "No workspaces found! Create a workspace at"
            f" {PREFECT_CLOUD_UI_URL.value()} and try again."
        ],
    )


@pytest.mark.usefixtures("interactive_console")
def test_login_with_key_and_select_first_workspace(respx_mock: respx.MockRouter):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
    bar_workspace = gen_test_workspace(account_handle="test", workspace_handle="bar")
    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[
                foo_workspace.model_dump(mode="json"),
                bar_workspace.model_dump(mode="json"),
            ],
        )
    )
    invoke_and_assert(
        ["cloud", "login", "--key", "foo"],
        expected_code=0,
        user_input=readchar.key.ENTER,
        expected_output_contains=[
            "? Which workspace would you like to use?",
            "test/foo",
            "test/bar",
            "Authenticated with Prefect Cloud! Using workspace 'test/foo'.",
        ],
    )

    settings = load_current_profile().settings
    assert settings[PREFECT_API_KEY] == "foo"
    assert settings[PREFECT_API_URL] == foo_workspace.api_url()


@pytest.mark.usefixtures("interactive_console")
def test_login_with_key_and_select_second_workspace(respx_mock: respx.MockRouter):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
    bar_workspace = gen_test_workspace(account_handle="test", workspace_handle="bar")
    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[
                foo_workspace.model_dump(mode="json"),
                bar_workspace.model_dump(mode="json"),
            ],
        )
    )
    invoke_and_assert(
        ["cloud", "login", "--key", "foo"],
        expected_code=0,
        user_input=readchar.key.DOWN + readchar.key.ENTER,
        expected_output_contains=[
            "? Which workspace would you like to use?",
            "test/foo",
            "test/bar",
            "Authenticated with Prefect Cloud! Using workspace 'test/bar'.",
        ],
    )

    settings = load_current_profile().settings
    assert settings[PREFECT_API_KEY] == "foo"
    assert settings[PREFECT_API_URL] == bar_workspace.api_url()


@pytest.mark.usefixtures("interactive_console")
def test_login_with_interactive_key_single_workspace(respx_mock: respx.MockRouter):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[foo_workspace.model_dump(mode="json")],
        )
    )

    invoke_and_assert(
        ["cloud", "login"],
        expected_code=0,
        user_input=readchar.key.DOWN + readchar.key.ENTER + "foo" + readchar.key.ENTER,
        expected_output_contains=[
            (
                "? How would you like to authenticate? [Use arrows to move; enter to"
                " select]"
            ),
            "Log in with a web browser",
            "Paste an API key",
            "Paste your API key:",
            "Authenticated with Prefect Cloud! Using workspace 'test/foo'.",
        ],
    )

    settings = load_current_profile().settings
    assert settings[PREFECT_API_KEY] == "foo"
    assert settings[PREFECT_API_URL] == foo_workspace.api_url()


@pytest.mark.usefixtures("interactive_console")
def test_login_with_interactive_key_multiple_workspaces(respx_mock: respx.MockRouter):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
    bar_workspace = gen_test_workspace(account_handle="test", workspace_handle="bar")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[
                foo_workspace.model_dump(mode="json"),
                bar_workspace.model_dump(mode="json"),
            ],
        )
    )

    invoke_and_assert(
        ["cloud", "login"],
        expected_code=0,
        user_input=(
            # Select paste a key
            readchar.key.DOWN
            + readchar.key.ENTER
            # Send a key
            + "foo"
            + readchar.key.ENTER
            # Select the second workspace
            + readchar.key.DOWN
            + readchar.key.ENTER
        ),
        expected_output_contains=[
            (
                "? How would you like to authenticate? [Use arrows to move; enter to"
                " select]"
            ),
            "Log in with a web browser",
            "Paste an API key",
            "Paste your API key:",
        ],
    )

    settings = load_current_profile().settings
    assert settings[PREFECT_API_KEY] == "foo"
    assert settings[PREFECT_API_URL] == bar_workspace.api_url()


@pytest.mark.usefixtures("interactive_console")
def test_login_with_browser_single_workspace(
    respx_mock: respx.MockRouter, mock_webbrowser: MagicMock
):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[foo_workspace.model_dump(mode="json")],
        )
    )

    def post_success(ui_url: str):
        # Parse the callback url that the UI would send a response to
        callback = urllib.parse.unquote(
            urllib.parse.urlparse(ui_url).query.split("=")[1]
        )
        # Bypass the mocks
        respx_mock.route(url__startswith=callback).pass_through()
        httpx.post(
            callback + "/success", content=LoginSuccess(api_key="foo").model_dump_json()
        )

    mock_webbrowser.open_new_tab.side_effect = post_success

    invoke_and_assert(
        ["cloud", "login"],
        expected_code=0,
        user_input=(
            # Select with browser
            readchar.key.ENTER
        ),
        expected_output_contains=[
            (
                "? How would you like to authenticate? [Use arrows to move; enter to"
                " select]"
            ),
            "Log in with a web browser",
            "Paste an API key",
            "Authenticated with Prefect Cloud! Using workspace 'test/foo'.",
        ],
    )

    settings = load_current_profile().settings
    assert settings[PREFECT_API_KEY] == "foo"
    assert settings[PREFECT_API_URL] == foo_workspace.api_url()


@pytest.mark.usefixtures("interactive_console")
def test_login_with_browser_failure_in_browser(
    respx_mock: respx.MockRouter, mock_webbrowser: MagicMock
):
    def post_failure(ui_url: str):
        # Parse the callback url that the UI would send a response to
        callback = urllib.parse.unquote(
            urllib.parse.urlparse(ui_url).query.split("=")[1]
        )
        # Bypass the mocks
        respx_mock.route(url__startswith=callback).pass_through()
        httpx.post(
            callback + "/failure",
            content=LoginFailed(reason="Oh no!").model_dump_json(),
        )

    mock_webbrowser.open_new_tab.side_effect = post_failure

    invoke_and_assert(
        ["cloud", "login"],
        expected_code=1,
        user_input=(
            # Select with browser
            readchar.key.ENTER
        ),
        expected_output_contains=[
            (
                "? How would you like to authenticate? [Use arrows to move; enter to"
                " select]"
            ),
            "Log in with a web browser",
            "Paste an API key",
            "Failed to log in. Oh no!",
        ],
    )

    profile = load_current_profile()
    assert profile is not None
    assert PREFECT_API_KEY not in profile.settings
    assert PREFECT_API_URL not in profile.settings


@pytest.mark.usefixtures("interactive_console")
def test_login_already_logged_in_to_current_profile_no_reauth(
    respx_mock: respx.MockRouter,
):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[foo_workspace.model_dump(mode="json")],
        )
    )

    save_profiles(
        ProfilesCollection(
            [
                Profile(
                    name="logged-in-profile",
                    settings={
                        PREFECT_API_URL: foo_workspace.api_url(),
                        PREFECT_API_KEY: "foo",
                    },
                )
            ],
            active=None,
        )
    )

    with use_profile("logged-in-profile"):
        invoke_and_assert(
            ["cloud", "login"],
            expected_code=0,
            user_input="n" + readchar.key.ENTER,
            expected_output_contains=[
                "Would you like to reauthenticate? [y/N]",
                "Using the existing authentication on this profile.",
                "Authenticated with Prefect Cloud! Using workspace 'test/foo'.",
            ],
        )

        settings = load_current_profile().settings

    assert settings[PREFECT_API_KEY] == "foo"
    assert settings[PREFECT_API_URL] == foo_workspace.api_url()


@pytest.mark.usefixtures("interactive_console")
def test_login_already_logged_in_to_current_profile_no_reauth_new_workspace(
    respx_mock: respx.MockRouter,
):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
    bar_workspace = gen_test_workspace(account_handle="test", workspace_handle="bar")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[
                foo_workspace.model_dump(mode="json"),
                bar_workspace.model_dump(mode="json"),
            ],
        )
    )

    save_profiles(
        ProfilesCollection(
            [
                Profile(
                    name="logged-in-profile",
                    settings={
                        PREFECT_API_URL: foo_workspace.api_url(),
                        PREFECT_API_KEY: "foo",
                    },
                )
            ],
            active=None,
        )
    )

    with use_profile("logged-in-profile"):
        invoke_and_assert(
            ["cloud", "login"],
            expected_code=0,
            user_input=(
                # No, do not reuath
                "n"
                + readchar.key.ENTER
                # Yes, switch workspaces
                + "y"
                + readchar.key.ENTER
                # Select 'bar'
                + readchar.key.DOWN
                + readchar.key.ENTER
            ),
            expected_output_contains=[
                "Would you like to reauthenticate? [y/N]",
                "Using the existing authentication on this profile.",
                (
                    "? Which workspace would you like to use? [Use arrows to move;"
                    " enter to select]"
                ),
                "Authenticated with Prefect Cloud! Using workspace 'test/bar'.",
            ],
        )

        settings = load_current_profile().settings

    assert settings[PREFECT_API_KEY] == "foo"
    assert settings[PREFECT_API_URL] == bar_workspace.api_url()


@pytest.mark.usefixtures("interactive_console")
def test_login_already_logged_in_to_current_profile_yes_reauth(
    respx_mock: respx.MockRouter,
):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[foo_workspace.model_dump(mode="json")],
        )
    )

    save_profiles(
        ProfilesCollection(
            [
                Profile(
                    name="logged-in-profile",
                    settings={
                        PREFECT_API_URL: foo_workspace.api_url(),
                        PREFECT_API_KEY: "foo",
                    },
                )
            ],
            active=None,
        )
    )

    with use_profile("logged-in-profile"):
        invoke_and_assert(
            ["cloud", "login"],
            expected_code=0,
            user_input=(
                # Yes, reauth
                "y"
                + readchar.key.ENTER
                # Enter key manually
                + readchar.key.DOWN
                + readchar.key.ENTER
                # Enter new key
                + "bar"
                + readchar.key.ENTER
            ),
            expected_output_contains=[
                "Would you like to reauthenticate? [y/N]",
                (
                    "? How would you like to authenticate? [Use arrows to move; enter"
                    " to select]"
                ),
                "Log in with a web browser",
                "Paste an API key",
                "Paste your API key:",
                "Authenticated with Prefect Cloud! Using workspace 'test/foo'.",
            ],
        )

        settings = load_current_profile().settings

    assert settings[PREFECT_API_KEY] == "bar"
    assert settings[PREFECT_API_URL] == foo_workspace.api_url()


@pytest.mark.usefixtures("interactive_console")
def test_login_already_logged_in_with_invalid_api_url_prompts_workspace_change(
    respx_mock: respx.MockRouter,
):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
    bar_workspace = gen_test_workspace(account_handle="test", workspace_handle="bar")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[
                foo_workspace.model_dump(mode="json"),
                bar_workspace.model_dump(mode="json"),
            ],
        )
    )

    save_profiles(
        ProfilesCollection(
            [
                Profile(
                    name="logged-in-profile",
                    settings={
                        PREFECT_API_URL: "oh-no",
                        PREFECT_API_KEY: "foo",
                    },
                )
            ],
            active=None,
        )
    )

    with use_profile("logged-in-profile"):
        invoke_and_assert(
            ["cloud", "login"],
            expected_code=0,
            user_input=(
                # Yes, reauth
                "y"
                + readchar.key.ENTER
                # Enter a key
                + readchar.key.DOWN
                + readchar.key.ENTER
                + "bar"
                + readchar.key.ENTER
                # Select the first workspace
                + readchar.key.ENTER
            ),
            expected_output_contains=[
                "It looks like you're already authenticated on this profile.",
                "? Which workspace would you like to use?",
                "test/foo",
                "test/bar",
                "Authenticated with Prefect Cloud! Using workspace 'test/foo'.",
            ],
        )

        settings = load_current_profile().settings

    assert settings[PREFECT_API_KEY] == "bar"
    assert settings[PREFECT_API_URL] == foo_workspace.api_url()


@pytest.mark.usefixtures("interactive_console")
def test_login_already_logged_in_to_another_profile(respx_mock: respx.MockRouter):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[foo_workspace.model_dump(mode="json")],
        )
    )

    current_profile = load_current_profile()

    save_profiles(
        ProfilesCollection(
            [
                Profile(
                    name="logged-in-profile",
                    settings={
                        PREFECT_API_URL: foo_workspace.api_url(),
                        PREFECT_API_KEY: "foo",
                    },
                ),
                current_profile,
            ],
            active=current_profile.name,
        )
    )

    invoke_and_assert(
        ["cloud", "login"],
        expected_code=0,
        user_input=(
            # Yes, switch profiles
            "y"
            + readchar.key.ENTER
            # Use the first profile
            + readchar.key.ENTER
        ),
        expected_output_contains=[
            "? Would you like to switch profiles? [Y/n]:",
            "? Which authenticated profile would you like to switch to?",
            "logged-in-profile",
            "Switched to authenticated profile 'logged-in-profile'.",
        ],
    )

    profiles = load_profiles()
    assert profiles.active_name == "logged-in-profile"
    assert profiles.active_profile
    settings = profiles.active_profile.settings
    assert settings[PREFECT_API_KEY] == "foo"
    assert settings[PREFECT_API_URL] == foo_workspace.api_url()

    # Current is the test profile active in the context
    previous_profile = load_current_profile()
    assert PREFECT_API_KEY not in previous_profile.settings


@pytest.mark.usefixtures("interactive_console")
def test_login_already_logged_in_to_another_profile_cancel_during_select(
    respx_mock: respx.MockRouter,
):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[foo_workspace.model_dump(mode="json")],
        )
    )

    current_profile = load_current_profile()

    save_profiles(
        ProfilesCollection(
            [
                Profile(
                    name="logged-in-profile",
                    settings={
                        PREFECT_API_URL: foo_workspace.api_url(),
                        PREFECT_API_KEY: "foo",
                    },
                ),
                current_profile,
            ],
            active=current_profile.name,
        )
    )

    invoke_and_assert(
        ["cloud", "login"],
        expected_code=130,  # assumes typer>=0.13.0
        user_input=(
            # Yes, switch profiles
            "y"
            + readchar.key.ENTER
            # Abort!
            + readchar.key.CTRL_C
        ),
        expected_output_contains=[
            "? Would you like to switch profiles? [Y/n]:",
            "? Which authenticated profile would you like to switch to?",
            "logged-in-profile",
        ],
    )

    current_profile = load_current_profile()
    profiles = load_profiles()

    # The active profile should not have changed
    assert profiles.active_name != "logged-in-profile"
    assert profiles.active_name == current_profile.name

    # The current profile settings are not mutated
    settings = current_profile.settings
    assert PREFECT_API_KEY not in settings
    assert PREFECT_API_URL not in settings

    # Other profile should not be updated
    assert PREFECT_API_KEY not in settings


def test_logout_current_profile_is_not_logged_in():
    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection([Profile(name=cloud_profile, settings={})], active=None)
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "logout"],
            expected_code=1,
            expected_output_contains=(
                "Current profile is not logged into Prefect Cloud."
            ),
        )


def test_logout_reset_prefect_api_key_and_prefect_api_url():
    profile = None
    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection(
            [
                Profile(
                    name=cloud_profile,
                    settings={PREFECT_API_URL: "foo", PREFECT_API_KEY: "bar"},
                )
            ],
            active=None,
        )
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "logout"],
            expected_code=0,
            expected_output_contains="Logged out from Prefect Cloud.",
        )

        profile = load_current_profile()

    assert profile is not None
    assert PREFECT_API_URL not in profile.settings
    assert PREFECT_API_KEY not in profile.settings


def test_cannot_set_workspace_if_you_are_not_logged_in():
    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection([Profile(name=cloud_profile, settings={})], active=None)
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "workspace", "set", "--workspace", "foo/bar"],
            expected_code=1,
            expected_output=(
                f"Currently not authenticated in profile {cloud_profile!r}. "
                "Please log in with `prefect cloud login`."
            ),
        )


def test_set_workspace_updates_profile(respx_mock: respx.MockRouter):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
    bar_workspace = gen_test_workspace(account_handle="test", workspace_handle="bar")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[
                foo_workspace.model_dump(mode="json"),
                bar_workspace.model_dump(mode="json"),
            ],
        )
    )

    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection(
            [
                Profile(
                    name=cloud_profile,
                    settings={
                        PREFECT_API_URL: foo_workspace.api_url(),
                        PREFECT_API_KEY: "fake-key",
                    },
                )
            ],
            active=None,
        )
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "workspace", "set", "--workspace", bar_workspace.handle],
            expected_code=0,
            expected_output=(
                f"Successfully set workspace to {bar_workspace.handle!r} "
                f"in profile {cloud_profile!r}."
            ),
        )

    profiles = load_profiles()
    assert profiles[cloud_profile].settings == {
        PREFECT_API_URL: bar_workspace.api_url(),
        PREFECT_API_KEY: "fake-key",
    }


@pytest.mark.usefixtures("interactive_console")
def test_set_workspace_with_account_selection():
    foo_workspace = gen_test_workspace(account_handle="test1", workspace_handle="foo")
    bar_workspace = gen_test_workspace(account_handle="test2", workspace_handle="bar")

    with respx.mock(
        using="httpx", base_url=PREFECT_CLOUD_API_URL.value()
    ) as respx_mock:
        respx_mock.get("/me/workspaces").mock(
            return_value=httpx.Response(
                status.HTTP_200_OK,
                json=[
                    foo_workspace.model_dump(mode="json"),
                    bar_workspace.model_dump(mode="json"),
                ],
            )
        )

        cloud_profile = "cloud-foo"
        save_profiles(
            ProfilesCollection(
                [
                    Profile(
                        name=cloud_profile,
                        settings={
                            PREFECT_API_URL: foo_workspace.api_url(),
                            PREFECT_API_KEY: "fake-key",
                        },
                    )
                ],
                active=None,
            )
        )

        with use_profile(cloud_profile):
            invoke_and_assert(
                ["cloud", "workspace", "set"],
                expected_code=0,
                user_input=readchar.key.DOWN + readchar.key.ENTER + readchar.key.ENTER,
                expected_output_contains=[
                    f"Successfully set workspace to {bar_workspace.handle!r} in profile {cloud_profile!r}.",
                ],
            )

        profiles = load_profiles()
        assert profiles[cloud_profile].settings == {
            PREFECT_API_URL: bar_workspace.api_url(),
            PREFECT_API_KEY: "fake-key",
        }


@pytest.mark.usefixtures("interactive_console")
def test_set_workspace_with_less_than_10_workspaces(respx_mock: respx.MockRouter):
    foo_workspace = gen_test_workspace(account_handle="test1", workspace_handle="foo")
    bar_workspace = gen_test_workspace(account_handle="test2", workspace_handle="bar")

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[
                foo_workspace.model_dump(mode="json"),
                bar_workspace.model_dump(mode="json"),
            ],
        )
    )

    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection(
            [
                Profile(
                    name=cloud_profile,
                    settings={
                        PREFECT_API_URL: foo_workspace.api_url(),
                        PREFECT_API_KEY: "fake-key",
                    },
                )
            ],
            active=None,
        )
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "workspace", "set"],
            expected_code=0,
            user_input=readchar.key.DOWN + readchar.key.ENTER,
            expected_output_contains=[
                f"Successfully set workspace to {bar_workspace.handle!r} in profile {cloud_profile!r}.",
            ],
        )

    profiles = load_profiles()
    assert profiles[cloud_profile].settings == {
        PREFECT_API_URL: bar_workspace.api_url(),
        PREFECT_API_KEY: "fake-key",
    }


class TestCloudWorkspaceLs:
    @pytest.fixture
    def workspaces(self, respx_mock: respx.MockRouter):
        foo_workspace = gen_test_workspace(
            account_handle="test1", workspace_handle="foo"
        )
        bar_workspace = gen_test_workspace(
            account_handle="test2", workspace_handle="bar"
        )

        respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
            return_value=httpx.Response(
                status.HTTP_200_OK,
                json=[
                    foo_workspace.model_dump(mode="json"),
                    bar_workspace.model_dump(mode="json"),
                ],
            )
        )

        cloud_profile = "cloud-foo"
        save_profiles(
            ProfilesCollection(
                [
                    Profile(
                        name=cloud_profile,
                        settings={
                            PREFECT_API_URL: foo_workspace.api_url(),
                            PREFECT_API_KEY: "fake-key",
                        },
                    )
                ],
                active=None,
            )
        )

        with use_profile(cloud_profile):
            yield foo_workspace, bar_workspace

    def test_ls(self, workspaces: tuple[Workspace, Workspace]):
        _, _ = workspaces
        invoke_and_assert(
            ["cloud", "workspace", "ls"],
            expected_code=0,
            expected_output_contains=[
                "* test1/foo",
                "test2/bar",
            ],
        )

    def test_ls_without_active_workspace(self, workspaces: tuple[Workspace, Workspace]):
        """
        Regression test for https://github.com/PrefectHQ/prefect/issues/16098
        """
        _, _ = workspaces
        wonky_profile = "wonky-profile"
        save_profiles(
            ProfilesCollection(
                [
                    Profile(
                        name=wonky_profile,
                        settings={
                            PREFECT_API_URL: "http://something-else.com/api",
                            PREFECT_API_KEY: "fake-key",
                        },
                    )
                ],
                active=None,
            )
        )

        with use_profile(wonky_profile):
            invoke_and_assert(
                ["cloud", "workspace", "ls"],
                expected_code=0,
                expected_output_contains=[
                    "test1/foo",
                    "test2/bar",
                ],
                expected_output_does_not_contain=[
                    "* test1/foo",
                    "* test2/bar",
                ],
            )


@pytest.mark.usefixtures("interactive_console")
def test_set_workspace_with_go_back_to_account_selection():
    # Create workspaces in different accounts - need more than 10 total to trigger account selection
    account1_id = uuid.uuid4()
    account2_id = uuid.uuid4()

    # Create 6 workspaces for account1
    account1_workspaces: list[Workspace] = []
    for i in range(1, 7):
        workspace = gen_test_workspace(
            account_handle="account1",
            workspace_handle=f"workspace{i}",
            account_id=account1_id,
        )
        account1_workspaces.append(workspace)

    # Create 6 workspaces for account2
    account2_workspaces: list[Workspace] = []
    for i in range(1, 7):
        workspace = gen_test_workspace(
            account_handle="account2",
            workspace_handle=f"workspace{i}",
            account_id=account2_id,
        )
        account2_workspaces.append(workspace)

    # Combine all workspaces
    all_workspaces = account1_workspaces + account2_workspaces

    # We'll target selecting the second workspace in account2
    target_workspace = account2_workspaces[1]  # workspace2 in account2

    with respx.mock(
        using="httpx", base_url=PREFECT_CLOUD_API_URL.value()
    ) as respx_mock:
        respx_mock.get("/me/workspaces").mock(
            return_value=httpx.Response(
                status.HTTP_200_OK,
                json=[
                    workspace.model_dump(mode="json") for workspace in all_workspaces
                ],
            )
        )

        cloud_profile = "cloud-foo"
        save_profiles(
            ProfilesCollection(
                [
                    Profile(
                        name=cloud_profile,
                        settings={
                            PREFECT_API_URL: account1_workspaces[0].api_url(),
                            PREFECT_API_KEY: "fake-key",
                        },
                    )
                ],
                active=None,
            )
        )

        with use_profile(cloud_profile):
            invoke_and_assert(
                ["cloud", "workspace", "set"],
                expected_code=0,
                user_input=(
                    # First select account1
                    readchar.key.ENTER
                    # Then select "Go back to account selection" option (last option) - using UP once
                    + readchar.key.UP
                    + readchar.key.ENTER
                    # Now select account2
                    + readchar.key.DOWN
                    + readchar.key.ENTER
                    # Select workspace2 in account2
                    + readchar.key.DOWN
                    + readchar.key.ENTER
                ),
                expected_output_contains=[
                    "Which account would you like to use?",
                    "Which workspace would you like to use?",
                    "Go back to account selection",
                    f"Successfully set workspace to {target_workspace.handle!r} in profile {cloud_profile!r}.",
                ],
            )

        profiles = load_profiles()
        assert profiles[cloud_profile].settings == {
            PREFECT_API_URL: target_workspace.api_url(),
            PREFECT_API_KEY: "fake-key",
        }


@pytest.mark.usefixtures("interactive_console")
def test_login_with_go_back_to_account_selection(respx_mock: respx.MockRouter):
    # Create workspaces in different accounts - need more than 10 total to trigger account selection
    account1_id = uuid.uuid4()
    account2_id = uuid.uuid4()

    # Create 6 workspaces for account1
    account1_workspaces: list[Workspace] = []
    for i in range(1, 7):
        workspace = gen_test_workspace(
            account_handle="account1",
            workspace_handle=f"workspace{i}",
            account_id=account1_id,
        )
        account1_workspaces.append(workspace)

    # Create 6 workspaces for account2
    account2_workspaces: list[Workspace] = []
    for i in range(1, 7):
        workspace = gen_test_workspace(
            account_handle="account2",
            workspace_handle=f"workspace{i}",
            account_id=account2_id,
        )
        account2_workspaces.append(workspace)

    all_workspaces = account1_workspaces + account2_workspaces

    target_workspace = account2_workspaces[1]  # workspace2 in account2

    respx_mock.get(PREFECT_CLOUD_API_URL.value() + "/me/workspaces").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[workspace.model_dump(mode="json") for workspace in all_workspaces],
        )
    )

    invoke_and_assert(
        ["cloud", "login"],
        expected_code=0,
        user_input=(
            # Select paste a key
            readchar.key.DOWN
            + readchar.key.ENTER
            # Send a key
            + "foo"
            + readchar.key.ENTER
            # First select account1
            + readchar.key.ENTER
            # Then select "Go back to account selection" option (last option) - using UP once
            + readchar.key.UP
            + readchar.key.ENTER
            # Now select account2
            + readchar.key.DOWN
            + readchar.key.ENTER
            # Select workspace2 in account2
            + readchar.key.DOWN
            + readchar.key.ENTER
        ),
        expected_output_contains=[
            "Paste your API key:",
            "Which account would you like to use?",
            "Which workspace would you like to use?",
            "Go back to account selection",
            f"Authenticated with Prefect Cloud! Using workspace {target_workspace.handle!r}.",
        ],
    )

    settings = load_current_profile().settings
    assert settings[PREFECT_API_KEY] == "foo"
    assert settings[PREFECT_API_URL] == target_workspace.api_url()

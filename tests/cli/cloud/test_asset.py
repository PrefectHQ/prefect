from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import readchar
from starlette import status
from tests.cli.cloud.test_cloud import gen_test_workspace

from prefect.context import use_profile
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_URL,
    Profile,
    ProfilesCollection,
    save_profiles,
)
from prefect.testing.cli import invoke_and_assert


def test_cannot_list_assets_if_you_are_not_logged_in():
    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection([Profile(name=cloud_profile, settings={})], active=None)
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "asset", "ls"],
            expected_code=1,
            expected_output=(
                f"Currently not authenticated in profile {cloud_profile!r}. "
                "Please log in with `prefect cloud login`."
            ),
        )


def test_list_assets(respx_mock):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
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

    asset1 = {
        "key": "s3://my-bucket/data.csv",
        "name": "My Data Asset",
        "description": "A test asset",
    }
    asset2 = {
        "key": "postgres://db/table",
        "name": "Database Table",
        "description": None,
    }

    respx_mock.get(f"{foo_workspace.api_url()}/assets/").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[asset1, asset2],
        )
    )

    with use_profile("logged-in-profile"):
        invoke_and_assert(
            ["cloud", "asset", "ls"],
            expected_code=0,
            expected_output_contains=[asset1["key"], asset2["key"]],
        )


def test_list_assets_empty(respx_mock):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
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

    respx_mock.get(f"{foo_workspace.api_url()}/assets/").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[],
        )
    )

    with use_profile("logged-in-profile"):
        invoke_and_assert(
            ["cloud", "asset", "ls"],
            expected_code=0,
            expected_output_contains="No assets found in workspace.",
        )


def test_cannot_inspect_asset_if_you_are_not_logged_in():
    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection([Profile(name=cloud_profile, settings={})], active=None)
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "asset", "inspect", "s3://my-bucket/data.csv"],
            expected_code=1,
            expected_output=(
                f"Currently not authenticated in profile {cloud_profile!r}. "
                "Please log in with `prefect cloud login`."
            ),
        )


def test_inspect_asset(respx_mock):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
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

    asset_key = "s3://my-bucket/data.csv"
    asset = {
        "key": asset_key,
        "name": "My Data Asset",
        "description": "A test asset",
    }

    respx_mock.get(
        f"{foo_workspace.api_url()}/assets/key/s3%3A%2F%2Fmy-bucket%2Fdata.csv"
    ).mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=asset,
        )
    )

    with use_profile("logged-in-profile"):
        invoke_and_assert(
            ["cloud", "asset", "inspect", asset_key],
            expected_code=0,
            expected_output_contains=[asset["key"], asset["name"]],
        )


def test_inspect_asset_json_output(respx_mock):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
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

    asset_key = "s3://my-bucket/data.csv"
    asset = {
        "key": asset_key,
        "name": "My Data Asset",
        "description": "A test asset",
    }

    respx_mock.get(
        f"{foo_workspace.api_url()}/assets/key/s3%3A%2F%2Fmy-bucket%2Fdata.csv"
    ).mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=asset,
        )
    )

    with use_profile("logged-in-profile"):
        invoke_and_assert(
            ["cloud", "asset", "inspect", asset_key, "--output", "json"],
            expected_code=0,
            expected_output_contains=[
                '"key": "s3://my-bucket/data.csv"',
                '"name": "My Data Asset"',
            ],
        )


def test_inspect_asset_invalid_output_format():
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
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
            ["cloud", "asset", "inspect", "s3://my-bucket/data.csv", "--output", "xml"],
            expected_code=1,
            expected_output_contains="Only 'json' output format is supported.",
        )


def test_cannot_delete_asset_if_you_are_not_logged_in():
    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection([Profile(name=cloud_profile, settings={})], active=None)
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "asset", "delete", "s3://my-bucket/data.csv"],
            expected_code=1,
            expected_output=(
                f"Currently not authenticated in profile {cloud_profile!r}. "
                "Please log in with `prefect cloud login`."
            ),
        )


def test_delete_asset(respx_mock):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
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

    asset_key = "s3://my-bucket/data.csv"

    respx_mock.delete(
        f"{foo_workspace.api_url()}/assets/key/s3%3A%2F%2Fmy-bucket%2Fdata.csv"
    ).mock(
        return_value=httpx.Response(
            status.HTTP_204_NO_CONTENT,
        )
    )

    with use_profile("logged-in-profile"):
        invoke_and_assert(
            ["cloud", "asset", "delete", asset_key],
            expected_code=0,
            user_input="y" + readchar.key.ENTER,
            expected_output_contains=f"Successfully deleted asset '{asset_key}'.",
        )


def test_cannot_delete_old_assets_if_you_are_not_logged_in():
    cloud_profile = "cloud-foo"
    save_profiles(
        ProfilesCollection([Profile(name=cloud_profile, settings={})], active=None)
    )

    with use_profile(cloud_profile):
        invoke_and_assert(
            ["cloud", "asset", "delete-old", "--days", "7"],
            expected_code=1,
            expected_output=(
                f"Currently not authenticated in profile {cloud_profile!r}. "
                "Please log in with `prefect cloud login`."
            ),
        )


def test_delete_old_assets_dry_run(respx_mock):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
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

    old_time = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    asset1 = {
        "key": "s3://my-bucket/old-data.csv",
        "name": "Old Data Asset",
        "description": "An old asset",
    }

    respx_mock.get(f"{foo_workspace.api_url()}/assets/").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[asset1],
        )
    )

    respx_mock.get(f"{foo_workspace.api_url()}/assets/latest-dependencies").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[
                {
                    "upstream": asset1["key"],
                    "downstream": None,
                    "occurred": old_time,
                }
            ],
        )
    )

    with use_profile("logged-in-profile"):
        invoke_and_assert(
            ["cloud", "asset", "delete-old", "--days", "7", "--dry-run"],
            expected_code=0,
            expected_output_contains=[
                "DRY RUN",
                asset1["key"],
                "No assets were deleted",
            ],
        )


def test_delete_old_assets_with_force(respx_mock):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
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

    old_time = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    asset1 = {
        "key": "s3://my-bucket/old-data.csv",
        "name": "Old Data Asset",
        "description": "An old asset",
    }

    respx_mock.get(f"{foo_workspace.api_url()}/assets/").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[asset1],
        )
    )

    respx_mock.get(f"{foo_workspace.api_url()}/assets/latest-dependencies").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[
                {
                    "upstream": asset1["key"],
                    "downstream": None,
                    "occurred": old_time,
                }
            ],
        )
    )

    respx_mock.delete(
        f"{foo_workspace.api_url()}/assets/key/s3%3A%2F%2Fmy-bucket%2Fold-data.csv"
    ).mock(
        return_value=httpx.Response(
            status.HTTP_204_NO_CONTENT,
        )
    )

    with use_profile("logged-in-profile"):
        invoke_and_assert(
            ["cloud", "asset", "delete-old", "--days", "7", "--force"],
            expected_code=0,
            expected_output_contains="Successfully deleted 1 asset(s).",
        )


def test_delete_old_assets_no_assets_to_delete(respx_mock):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
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

    recent_time = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    asset1 = {
        "key": "s3://my-bucket/recent-data.csv",
        "name": "Recent Data Asset",
        "description": "A recent asset",
    }

    respx_mock.get(f"{foo_workspace.api_url()}/assets/").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[asset1],
        )
    )

    respx_mock.get(f"{foo_workspace.api_url()}/assets/latest-dependencies").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[
                {
                    "upstream": asset1["key"],
                    "downstream": None,
                    "occurred": recent_time,
                }
            ],
        )
    )

    with use_profile("logged-in-profile"):
        invoke_and_assert(
            ["cloud", "asset", "delete-old", "--days", "7", "--force"],
            expected_code=0,
            expected_output_contains="No assets to delete.",
        )


def test_delete_old_assets_requires_confirmation_in_non_interactive_mode(respx_mock):
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
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

    old_time = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    asset1 = {
        "key": "s3://my-bucket/old-data.csv",
        "name": "Old Data Asset",
        "description": "An old asset",
    }

    respx_mock.get(f"{foo_workspace.api_url()}/assets/").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[asset1],
        )
    )

    respx_mock.get(f"{foo_workspace.api_url()}/assets/latest-dependencies").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[
                {
                    "upstream": asset1["key"],
                    "downstream": None,
                    "occurred": old_time,
                }
            ],
        )
    )

    with use_profile("logged-in-profile"):
        invoke_and_assert(
            ["cloud", "asset", "delete-old", "--days", "7"],
            expected_code=1,
            expected_output_contains=(
                "Confirmation required. Use --force to skip confirmation"
            ),
        )


def test_list_assets_with_aliases(respx_mock):
    """Test that the 'assets' alias works for the 'asset' command."""
    foo_workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
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

    respx_mock.get(f"{foo_workspace.api_url()}/assets/").mock(
        return_value=httpx.Response(
            status.HTTP_200_OK,
            json=[],
        )
    )

    with use_profile("logged-in-profile"):
        invoke_and_assert(
            ["cloud", "assets", "ls"],
            expected_code=0,
            expected_output_contains="No assets found in workspace.",
        )

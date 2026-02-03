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


class TestAssetList:
    def test_cannot_list_assets_if_not_logged_in(self):
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

    def test_list_assets_empty(self, respx_mock):
        foo_workspace = gen_test_workspace(
            account_handle="test", workspace_handle="foo"
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
                expected_output_contains="No assets found in this workspace",
            )

    def test_list_assets(self, respx_mock):
        foo_workspace = gen_test_workspace(
            account_handle="test", workspace_handle="foo"
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

        asset1 = {
            "key": "s3://my-bucket/data.csv",
            "last_seen": "2026-01-20T18:52:16.681416Z",
        }
        asset2 = {
            "key": "postgres://db/users",
            "last_seen": "2026-01-21T10:30:00.000000Z",
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

    def test_list_assets_with_prefix(self, respx_mock):
        foo_workspace = gen_test_workspace(
            account_handle="test", workspace_handle="foo"
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

        asset = {
            "key": "s3://my-bucket/data.csv",
            "last_seen": "2026-01-20T18:52:16.681416Z",
        }

        respx_mock.get(f"{foo_workspace.api_url()}/assets/").mock(
            return_value=httpx.Response(
                status.HTTP_200_OK,
                json=[asset],
            )
        )

        with use_profile("logged-in-profile"):
            invoke_and_assert(
                ["cloud", "asset", "ls", "--prefix", "s3://"],
                expected_code=0,
                expected_output_contains=asset["key"],
            )

    def test_list_assets_with_search(self, respx_mock):
        foo_workspace = gen_test_workspace(
            account_handle="test", workspace_handle="foo"
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

        asset = {
            "key": "s3://my-bucket/data.csv",
            "last_seen": "2026-01-20T18:52:16.681416Z",
        }

        respx_mock.get(f"{foo_workspace.api_url()}/assets/").mock(
            return_value=httpx.Response(
                status.HTTP_200_OK,
                json=[asset],
            )
        )

        with use_profile("logged-in-profile"):
            invoke_and_assert(
                ["cloud", "asset", "ls", "--search", "bucket"],
                expected_code=0,
                expected_output_contains=asset["key"],
            )

    def test_list_assets_json_output(self, respx_mock):
        foo_workspace = gen_test_workspace(
            account_handle="test", workspace_handle="foo"
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

        asset = {
            "key": "s3://my-bucket/data.csv",
            "last_seen": "2026-01-20T18:52:16.681416Z",
        }

        respx_mock.get(f"{foo_workspace.api_url()}/assets/").mock(
            return_value=httpx.Response(
                status.HTTP_200_OK,
                json=[asset],
            )
        )

        with use_profile("logged-in-profile"):
            invoke_and_assert(
                ["cloud", "asset", "ls", "-o", "json"],
                expected_code=0,
                expected_output_contains=[asset["key"], asset["last_seen"]],
            )

    def test_list_assets_invalid_output_format(self):
        foo_workspace = gen_test_workspace(
            account_handle="test", workspace_handle="foo"
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
                ["cloud", "asset", "ls", "-o", "xml"],
                expected_code=1,
                expected_output_contains="Only 'json' output format is supported",
            )


class TestAssetDelete:
    def test_cannot_delete_asset_if_not_logged_in(self):
        cloud_profile = "cloud-foo"
        save_profiles(
            ProfilesCollection([Profile(name=cloud_profile, settings={})], active=None)
        )

        with use_profile(cloud_profile):
            invoke_and_assert(
                ["cloud", "asset", "delete", "s3://bucket/data.csv"],
                expected_code=1,
                expected_output=(
                    f"Currently not authenticated in profile {cloud_profile!r}. "
                    "Please log in with `prefect cloud login`."
                ),
            )

    def test_delete_asset_with_confirmation(self, respx_mock):
        foo_workspace = gen_test_workspace(
            account_handle="test", workspace_handle="foo"
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

        asset_key = "s3://my-bucket/data.csv"

        respx_mock.delete(f"{foo_workspace.api_url()}/assets/key").mock(
            return_value=httpx.Response(
                status.HTTP_204_NO_CONTENT,
            )
        )

        with use_profile("logged-in-profile"):
            invoke_and_assert(
                ["cloud", "asset", "delete", asset_key],
                expected_code=0,
                user_input="y" + readchar.key.ENTER,
                expected_output_contains=f"Deleted asset {asset_key!r}",
            )

    def test_delete_asset_with_force_flag(self, respx_mock):
        foo_workspace = gen_test_workspace(
            account_handle="test", workspace_handle="foo"
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

        asset_key = "s3://my-bucket/data.csv"

        respx_mock.delete(f"{foo_workspace.api_url()}/assets/key").mock(
            return_value=httpx.Response(
                status.HTTP_204_NO_CONTENT,
            )
        )

        with use_profile("logged-in-profile"):
            invoke_and_assert(
                ["cloud", "asset", "delete", asset_key, "--force"],
                expected_code=0,
                expected_output_contains=f"Deleted asset {asset_key!r}",
            )

    def test_delete_asset_not_found(self, respx_mock):
        foo_workspace = gen_test_workspace(
            account_handle="test", workspace_handle="foo"
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

        asset_key = "s3://nonexistent/data.csv"

        respx_mock.delete(f"{foo_workspace.api_url()}/assets/key").mock(
            return_value=httpx.Response(
                status.HTTP_404_NOT_FOUND,
                json={"detail": "Asset not found"},
            )
        )

        with use_profile("logged-in-profile"):
            invoke_and_assert(
                ["cloud", "asset", "delete", asset_key, "--force"],
                expected_code=1,
                expected_output_contains=f"Asset {asset_key!r} not found",
            )

    def test_delete_asset_abort_confirmation(self):
        foo_workspace = gen_test_workspace(
            account_handle="test", workspace_handle="foo"
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
                ["cloud", "asset", "delete", "s3://bucket/data.csv"],
                expected_code=1,
                user_input="n" + readchar.key.ENTER,
                expected_output_contains="Deletion aborted",
            )

    def test_delete_asset_uses_aliases(self, respx_mock):
        """Test that 'assets' alias works for the asset command."""
        foo_workspace = gen_test_workspace(
            account_handle="test", workspace_handle="foo"
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
                expected_output_contains="No assets found",
            )

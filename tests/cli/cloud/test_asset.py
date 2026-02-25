import uuid

import httpx
import pytest
import readchar
import respx
from starlette import status
from tests.cli.cloud.test_cloud import gen_test_workspace

from prefect.client.schemas import Workspace
from prefect.context import use_profile
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_URL,
    Profile,
    ProfilesCollection,
    save_profiles,
)
from prefect.testing.cli import invoke_and_assert


@pytest.fixture
def cloud_workspace() -> tuple[Workspace, str]:
    workspace = gen_test_workspace(account_handle="test", workspace_handle="foo")
    profile_name = f"logged-in-profile-{uuid.uuid4()}"
    save_profiles(
        ProfilesCollection(
            [
                Profile(
                    name=profile_name,
                    settings={
                        PREFECT_API_URL: workspace.api_url(),
                        PREFECT_API_KEY: "foo",
                    },
                )
            ],
            active=None,
        )
    )
    return workspace, profile_name


class TestAssetList:
    def test_cannot_list_assets_if_not_logged_in(self) -> None:
        cloud_profile = f"cloud-foo-{uuid.uuid4()}"
        save_profiles(
            ProfilesCollection([Profile(name=cloud_profile, settings={})], active=None)
        )

        with use_profile(cloud_profile):
            invoke_and_assert(
                ["cloud", "asset", "ls"],
                expected_code=1,
                expected_output_contains="Please log in with `prefect cloud login`",
            )

    def test_list_assets_empty(
        self, respx_mock: respx.MockRouter, cloud_workspace: tuple[Workspace, str]
    ) -> None:
        workspace, profile_name = cloud_workspace
        respx_mock.post(f"{workspace.api_url()}/assets/filter").mock(
            return_value=httpx.Response(
                status.HTTP_200_OK, json={"assets": [], "total": 0}
            )
        )

        with use_profile(profile_name):
            invoke_and_assert(
                ["cloud", "asset", "ls"],
                expected_code=0,
                expected_output_contains="No assets found in this workspace",
            )

    def test_list_assets(
        self, respx_mock: respx.MockRouter, cloud_workspace: tuple[Workspace, str]
    ) -> None:
        workspace, profile_name = cloud_workspace
        assets = [
            {"key": "s3://my-bucket/data.csv", "last_seen": "2026-01-20T18:52:16Z"},
            {"key": "postgres://db/users", "last_seen": "2026-01-21T10:30:00Z"},
        ]
        respx_mock.post(f"{workspace.api_url()}/assets/filter").mock(
            return_value=httpx.Response(
                status.HTTP_200_OK, json={"assets": assets, "total": 2}
            )
        )

        with use_profile(profile_name):
            invoke_and_assert(
                ["cloud", "asset", "ls"],
                expected_code=0,
                expected_output_contains=[
                    "s3://my-bucket/data.csv",
                    "postgres://db/users",
                    "Showing 2 of 2 asset(s)",
                ],
            )

    @pytest.mark.parametrize(
        "flag,value", [("--prefix", "s3://"), ("--search", "bucket")]
    )
    def test_list_assets_with_filters(
        self,
        respx_mock: respx.MockRouter,
        cloud_workspace: tuple[Workspace, str],
        flag: str,
        value: str,
    ) -> None:
        workspace, profile_name = cloud_workspace
        asset = {"key": "s3://my-bucket/data.csv", "last_seen": "2026-01-20T18:52:16Z"}
        respx_mock.post(f"{workspace.api_url()}/assets/filter").mock(
            return_value=httpx.Response(
                status.HTTP_200_OK, json={"assets": [asset], "total": 1}
            )
        )

        with use_profile(profile_name):
            invoke_and_assert(
                ["cloud", "asset", "ls", flag, value],
                expected_code=0,
                expected_output_contains=asset["key"],
            )

    def test_list_assets_with_limit(
        self, respx_mock: respx.MockRouter, cloud_workspace: tuple[Workspace, str]
    ) -> None:
        workspace, profile_name = cloud_workspace
        assets = [
            {"key": "s3://my-bucket/data.csv", "last_seen": "2026-01-20T18:52:16Z"},
        ]
        respx_mock.post(f"{workspace.api_url()}/assets/filter").mock(
            return_value=httpx.Response(
                status.HTTP_200_OK, json={"assets": assets, "total": 100}
            )
        )

        with use_profile(profile_name):
            invoke_and_assert(
                ["cloud", "asset", "ls", "--limit", "1"],
                expected_code=0,
                expected_output_contains="Showing 1 of 100 asset(s)",
            )

    def test_list_assets_invalid_limit(
        self, cloud_workspace: tuple[Workspace, str]
    ) -> None:
        _, profile_name = cloud_workspace
        with use_profile(profile_name):
            invoke_and_assert(
                ["cloud", "asset", "ls", "--limit", "500"],
                expected_code=1,
                expected_output_contains="Limit must be between 1 and 200",
            )

    def test_list_assets_json_output(
        self, respx_mock: respx.MockRouter, cloud_workspace: tuple[Workspace, str]
    ) -> None:
        workspace, profile_name = cloud_workspace
        asset = {"key": "s3://my-bucket/data.csv", "last_seen": "2026-01-20T18:52:16Z"}
        respx_mock.post(f"{workspace.api_url()}/assets/filter").mock(
            return_value=httpx.Response(
                status.HTTP_200_OK, json={"assets": [asset], "total": 1}
            )
        )

        with use_profile(profile_name):
            invoke_and_assert(
                ["cloud", "asset", "ls", "-o", "json"],
                expected_code=0,
                expected_output_contains=[asset["key"], asset["last_seen"]],
            )

    def test_list_assets_invalid_output_format(
        self, cloud_workspace: tuple[Workspace, str]
    ) -> None:
        _, profile_name = cloud_workspace
        with use_profile(profile_name):
            invoke_and_assert(
                ["cloud", "asset", "ls", "-o", "xml"],
                expected_code=1,
                expected_output_contains="Only 'json' output format is supported",
            )

    def test_assets_alias(
        self, respx_mock: respx.MockRouter, cloud_workspace: tuple[Workspace, str]
    ) -> None:
        workspace, profile_name = cloud_workspace
        respx_mock.post(f"{workspace.api_url()}/assets/filter").mock(
            return_value=httpx.Response(
                status.HTTP_200_OK, json={"assets": [], "total": 0}
            )
        )

        with use_profile(profile_name):
            invoke_and_assert(
                ["cloud", "assets", "ls"],
                expected_code=0,
                expected_output_contains="No assets found",
            )


class TestAssetDelete:
    def test_cannot_delete_asset_if_not_logged_in(self) -> None:
        cloud_profile = f"cloud-foo-{uuid.uuid4()}"
        save_profiles(
            ProfilesCollection([Profile(name=cloud_profile, settings={})], active=None)
        )

        with use_profile(cloud_profile):
            invoke_and_assert(
                ["cloud", "asset", "delete", "s3://bucket/data.csv"],
                expected_code=1,
                expected_output_contains="Please log in with `prefect cloud login`",
            )

    def test_delete_asset_with_confirmation(
        self,
        respx_mock: respx.MockRouter,
        cloud_workspace: tuple[Workspace, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        workspace, profile_name = cloud_workspace
        monkeypatch.setattr("prefect.cli._app.is_interactive", lambda: True)
        import prefect.cli._app as _cli

        monkeypatch.setattr(_cli, "is_interactive", lambda: True)

        respx_mock.delete(f"{workspace.api_url()}/assets/key").mock(
            return_value=httpx.Response(status.HTTP_204_NO_CONTENT)
        )

        with use_profile(profile_name):
            invoke_and_assert(
                ["cloud", "asset", "delete", "s3://my-bucket/data.csv"],
                expected_code=0,
                user_input="y" + readchar.key.ENTER,
                expected_output_contains="Deleted asset 's3://my-bucket/data.csv'",
            )

    def test_delete_asset_with_force_flag(
        self, respx_mock: respx.MockRouter, cloud_workspace: tuple[Workspace, str]
    ) -> None:
        workspace, profile_name = cloud_workspace
        respx_mock.delete(f"{workspace.api_url()}/assets/key").mock(
            return_value=httpx.Response(status.HTTP_204_NO_CONTENT)
        )

        with use_profile(profile_name):
            invoke_and_assert(
                ["cloud", "asset", "delete", "s3://my-bucket/data.csv", "--force"],
                expected_code=0,
                expected_output_contains="Deleted asset 's3://my-bucket/data.csv'",
            )

    def test_delete_asset_not_found(
        self, respx_mock: respx.MockRouter, cloud_workspace: tuple[Workspace, str]
    ) -> None:
        workspace, profile_name = cloud_workspace
        respx_mock.delete(f"{workspace.api_url()}/assets/key").mock(
            return_value=httpx.Response(
                status.HTTP_404_NOT_FOUND, json={"detail": "Asset not found"}
            )
        )

        with use_profile(profile_name):
            invoke_and_assert(
                ["cloud", "asset", "delete", "s3://nonexistent/data.csv", "--force"],
                expected_code=1,
                expected_output_contains="Asset 's3://nonexistent/data.csv' not found",
            )

    def test_delete_asset_abort_confirmation(
        self, cloud_workspace: tuple[Workspace, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _, profile_name = cloud_workspace
        monkeypatch.setattr("prefect.cli._app.is_interactive", lambda: True)
        import prefect.cli._app as _cli

        monkeypatch.setattr(_cli, "is_interactive", lambda: True)

        with use_profile(profile_name):
            invoke_and_assert(
                ["cloud", "asset", "delete", "s3://bucket/data.csv"],
                expected_code=1,
                user_input="n" + readchar.key.ENTER,
                expected_output_contains="Deletion aborted",
            )

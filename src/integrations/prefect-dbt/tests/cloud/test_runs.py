import pytest
import respx
from httpx import Response
from prefect_dbt.cloud.runs import (
    DbtCloudGetRunArtifactFailed,
    DbtCloudGetRunFailed,
    DbtCloudListRunArtifactsFailed,
    get_dbt_cloud_run_artifact,
    get_dbt_cloud_run_info,
    list_dbt_cloud_run_artifacts,
)


class TestGetDbtCloudRunInfo:
    async def test_get_dbt_cloud_run_info(self, dbt_cloud_credentials):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/12/",
                headers={"Authorization": "Bearer my_api_key"},
            ).mock(return_value=Response(200, json={"data": {"id": 10000}}))

            response = await get_dbt_cloud_run_info.fn(
                dbt_cloud_credentials=dbt_cloud_credentials,
                run_id=12,
            )

            assert response == {"id": 10000}

    async def test_get_nonexistent_run(self, dbt_cloud_credentials):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/12/",
                headers={"Authorization": "Bearer my_api_key"},
            ).mock(
                return_value=Response(
                    404, json={"status": {"user_message": "Not found!"}}
                )
            )
            with pytest.raises(DbtCloudGetRunFailed, match="Not found!"):
                await get_dbt_cloud_run_info.fn(
                    dbt_cloud_credentials=dbt_cloud_credentials,
                    run_id=12,
                )


class TestDbtCloudListRunArtifacts:
    async def test_list_artifacts_success(self, dbt_cloud_credentials):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/12/artifacts/",
                headers={"Authorization": "Bearer my_api_key"},
            ).mock(return_value=Response(200, json={"data": ["manifest.json"]}))

            response = await list_dbt_cloud_run_artifacts.fn(
                dbt_cloud_credentials=dbt_cloud_credentials,
                run_id=12,
            )

            assert response == ["manifest.json"]

    async def test_list_artifacts_with_step(self, dbt_cloud_credentials):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/12/artifacts/?step=1",  # noqa
                headers={"Authorization": "Bearer my_api_key"},
            ).mock(return_value=Response(200, json={"data": ["manifest.json"]}))

            response = await list_dbt_cloud_run_artifacts.fn(
                dbt_cloud_credentials=dbt_cloud_credentials, run_id=12, step=1
            )

            assert response == ["manifest.json"]

    async def test_list_artifacts_failure(self, dbt_cloud_credentials):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/12/artifacts/",
                headers={"Authorization": "Bearer my_api_key"},
            ).mock(
                return_value=Response(
                    500, json={"status": {"user_message": "This is what went wrong"}}
                )
            )
            with pytest.raises(
                DbtCloudListRunArtifactsFailed, match="This is what went wrong"
            ):
                await list_dbt_cloud_run_artifacts.fn(
                    dbt_cloud_credentials=dbt_cloud_credentials,
                    run_id=12,
                )


class TestDbtCloudGetRunArtifact:
    async def test_get_artifact_success(self, dbt_cloud_credentials):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/12/artifacts/manifest.json",  # noqa
                headers={"Authorization": "Bearer my_api_key"},
            ).mock(
                return_value=Response(
                    200,
                    json={
                        "metadata": {
                            "dbt_schema_version": "https://schemas.getdbt.com/dbt/catalog/v1.json",  # noqa
                            "dbt_version": "1.1.1",
                        }
                    },
                )
            )

            response = await get_dbt_cloud_run_artifact.fn(
                dbt_cloud_credentials=dbt_cloud_credentials,
                run_id=12,
                path="manifest.json",
            )

            assert response == {
                "metadata": {
                    "dbt_schema_version": "https://schemas.getdbt.com/dbt/catalog/v1.json",
                    "dbt_version": "1.1.1",
                }
            }

    async def test_get_non_json_artifact(self, dbt_cloud_credentials):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/12/artifacts/compiled/dbt_artifacts/models/dim_dbt__current_models.sql",  # noqa
                headers={"Authorization": "Bearer my_api_key"},
            ).mock(return_value=Response(200, text="Hi! I'm some SQL!"))

            response = await get_dbt_cloud_run_artifact.fn(
                dbt_cloud_credentials=dbt_cloud_credentials,
                run_id=12,
                path="compiled/dbt_artifacts/models/dim_dbt__current_models.sql",
            )

            assert response == "Hi! I'm some SQL!"

    async def test_get_artifact_with_step(self, dbt_cloud_credentials):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/12/artifacts/manifest.json?step=1",  # noqa
                headers={"Authorization": "Bearer my_api_key"},
            ).mock(
                return_value=Response(
                    200,
                    json={
                        "metadata": {
                            "dbt_schema_version": "https://schemas.getdbt.com/dbt/catalog/v1.json",  # noqa
                            "dbt_version": "1.1.1",
                        }
                    },
                )
            )

            response = await get_dbt_cloud_run_artifact.fn(
                dbt_cloud_credentials=dbt_cloud_credentials,
                run_id=12,
                path="manifest.json",
                step=1,
            )

            assert response == {
                "metadata": {
                    "dbt_schema_version": "https://schemas.getdbt.com/dbt/catalog/v1.json",
                    "dbt_version": "1.1.1",
                }
            }

    async def test_get_artifact_failure(self, dbt_cloud_credentials):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/12/artifacts/manifest.json",  # noqa
                headers={"Authorization": "Bearer my_api_key"},
            ).mock(
                return_value=Response(
                    500, json={"status": {"user_message": "This is what went wrong"}}
                )
            )
            with pytest.raises(
                DbtCloudGetRunArtifactFailed, match="This is what went wrong"
            ):
                await get_dbt_cloud_run_artifact.fn(
                    dbt_cloud_credentials=dbt_cloud_credentials,
                    run_id=12,
                    path="manifest.json",
                )

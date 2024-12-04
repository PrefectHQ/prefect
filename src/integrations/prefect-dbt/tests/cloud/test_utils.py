import pytest
import respx
from httpx import Response
from prefect_dbt.cloud.utils import (
    DbtCloudAdministrativeApiCallFailed,
    call_dbt_cloud_administrative_api_endpoint,
)


class TestCallDbtCloudAdministrativeApiEndpoint:
    async def test_endpoint_returns_json(self, dbt_cloud_credentials):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/projects/",
                headers={"Authorization": "Bearer my_api_key"},
            ).mock(
                return_value=Response(
                    200,
                    json={
                        "status": {
                            "code": 200,
                            "is_success": True,
                            "user_message": "Success!",
                            "developer_message": "",
                        },
                        "data": [],
                    },
                )
            )

            result = await call_dbt_cloud_administrative_api_endpoint.fn(
                dbt_cloud_credentials=dbt_cloud_credentials,
                path="/projects/",
                http_method="GET",
            )

            assert result == {
                "status": {
                    "code": 200,
                    "is_success": True,
                    "user_message": "Success!",
                    "developer_message": "",
                },
                "data": [],
            }

    async def test_endpoint_returns_text(self, dbt_cloud_credentials):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/runs/12/artifacts/compiled/dbt_artifacts/models/dim_dbt__current_models.sql",  # noqa
                headers={"Authorization": "Bearer my_api_key"},
            ).mock(return_value=Response(200, text="Hi! I'm some SQL!"))

            result = await call_dbt_cloud_administrative_api_endpoint.fn(
                dbt_cloud_credentials=dbt_cloud_credentials,
                path="/runs/12/artifacts/compiled/dbt_artifacts/models/dim_dbt__current_models.sql",  # noqa
                http_method="GET",
            )

            assert result == "Hi! I'm some SQL!"

    async def test_failure(self, dbt_cloud_credentials):
        with respx.mock(using="httpx") as respx_mock:
            respx_mock.get(
                "https://cloud.getdbt.com/api/v2/accounts/123456789/projects/",
                headers={"Authorization": "Bearer my_api_key"},
            ).mock(return_value=Response(500, json={}))

            with pytest.raises(DbtCloudAdministrativeApiCallFailed):
                await call_dbt_cloud_administrative_api_endpoint.fn(
                    dbt_cloud_credentials=dbt_cloud_credentials,
                    path="/projects/",
                    http_method="GET",
                )

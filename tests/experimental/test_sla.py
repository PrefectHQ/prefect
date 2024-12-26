from datetime import timedelta
from unittest import mock
from uuid import UUID, uuid4

import httpx
import pytest
import respx

from prefect._experimental.sla import ServiceLevelAgreement, TimeToCompletionSla
from prefect.client.orchestration import get_client
from prefect.settings import (
    PREFECT_API_URL,
    temporary_settings,
)


class TestSla:
    async def test_create_sla(self):
        sla = ServiceLevelAgreement(
            name="test-sla",
        )
        deployment_id = uuid4()
        sla.set_deployment_id(deployment_id)
        assert sla.owner_resource == f"prefect.deployment.{deployment_id}"

    async def test_model_dump_fails_if_deployment_id_is_not_set(self):
        sla = ServiceLevelAgreement(
            name="test-sla",
        )
        with pytest.raises(
            ValueError,
            match="Deployment ID is not set. Please set using `set_deployment_id`.",
        ):
            sla.model_dump()


class TestClientCreateSla:
    async def test_create_sla_against_cloud(self):
        account_id = uuid4()
        workspace_id = uuid4()
        with temporary_settings(
            updates={
                PREFECT_API_URL: f"https://api.prefect.cloud/api/accounts/{account_id}/workspaces/{workspace_id}/"
            }
        ):
            with respx.mock(
                assert_all_mocked=True,
                assert_all_called=False,
                base_url="https://api.prefect.cloud/api",
                using="httpx",
            ) as router:
                sla_id = str(uuid4())

                router.get("/csrf-token", params={"client": mock.ANY}).pass_through()
                router.post(
                    f"/accounts/{account_id}/workspaces/{workspace_id}/slas/",
                ).mock(
                    return_value=httpx.Response(
                        status_code=201,
                        json={"id": sla_id},
                    )
                )
                prefect_client = get_client()

                deployment_id = uuid4()
                sla = TimeToCompletionSla(
                    name="test-sla",
                    duration=timedelta(minutes=10).total_seconds(),
                )
                sla.set_deployment_id(deployment_id)
                response_id = await prefect_client.create_sla(sla)
                assert response_id == UUID(sla_id)


class TestDeployFunction:
    async def test_create_deployment_with_sla_config_against_cloud(self):
        pass

    async def test_create_deployment_with_multiple_slas_against_cloud(self):
        pass

    async def test_create_deployment_against_oss_server_produces_error_log(self):
        pass


class TestDeploymentWithPrefectYaml:
    async def test_create_deployment_with_sla_config_against_cloud(self):
        pass

    async def test_create_deployment_with_multiple_slas_against_cloud(self):
        pass

    async def test_create_deployment_with_invalid_sla_config_against_cloud(self):
        pass

    async def test_create_deployment_with_sla_config_against_oss_server(self):
        # should produce an error log
        pass

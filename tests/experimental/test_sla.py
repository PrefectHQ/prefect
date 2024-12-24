from uuid import uuid4

import pytest

from prefect._experimental.sla import ServiceLevelAgreement


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

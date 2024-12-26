import json
from datetime import timedelta
from time import sleep
from unittest import mock
from uuid import UUID, uuid4

import httpx
import pytest
import respx

from prefect import flow
from prefect._experimental.sla import (
    ServiceLevelAgreement,
    SlaSeverity,
    TimeToCompletionSla,
)
from prefect.client.orchestration import get_client
from prefect.deployments.runner import RunnerDeployment
from prefect.settings import (
    PREFECT_API_URL,
    temporary_settings,
)


@flow()
def tired_flow():
    print("I am so tired...")

    for _ in range(100):
        print("zzzzz...")
        sleep(5)


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


class TestRunnerDeploymentApply:
    async def test_create_deployment_with_sla_config_against_cloud(self):
        account_id = uuid4()
        workspace_id = uuid4()

        sla = TimeToCompletionSla(
            name="test-sla",
            duration=timedelta(minutes=10).total_seconds(),
        )
        deployment = RunnerDeployment.from_flow(
            flow=tired_flow,
            name=__file__,
            sla=sla,
        )

        base_url = f"https://api.prefect.cloud/api/accounts/{account_id}/workspaces/{workspace_id}"
        with temporary_settings(updates={PREFECT_API_URL: base_url}):
            with respx.mock(
                assert_all_mocked=True,
                assert_all_called=False,
                base_url=base_url,
                using="httpx",
            ) as router:
                router.get("/csrf-token", params={"client": mock.ANY}).pass_through()
                router.post("/slas/").mock(
                    return_value=httpx.Response(
                        status_code=201,
                        json={"id": str(uuid4())},
                    )
                )

                client = get_client()
                await deployment._create_slas(uuid4(), client)

                last_request = router.calls.last.request
                last_response = router.calls.last.response
                assert (
                    last_request.url.path
                    == f"/api/accounts/{account_id}/workspaces/{workspace_id}/slas/"
                )
                assert json.loads(last_request.content)["name"] == sla.name
                assert json.loads(last_request.content)["duration"] == sla.duration
                assert last_response.status_code == 201

    async def test_create_deployment_with_multiple_slas_against_cloud(self):
        account_id = uuid4()
        workspace_id = uuid4()

        sla1 = TimeToCompletionSla(
            name="a little long",
            severity=SlaSeverity.MODERATE,
            duration=timedelta(minutes=10).total_seconds(),
        )
        sla2 = TimeToCompletionSla(
            name="whoa this is bad",
            severity=SlaSeverity.HIGH,
            duration=timedelta(minutes=30).total_seconds(),
        )
        deployment = RunnerDeployment.from_flow(
            flow=tired_flow,
            name=__file__,
            sla=[sla1, sla2],
        )

        base_url = f"https://api.prefect.cloud/api/accounts/{account_id}/workspaces/{workspace_id}"
        with temporary_settings(updates={PREFECT_API_URL: base_url}):
            with respx.mock(
                assert_all_mocked=True,
                assert_all_called=False,
                base_url=base_url,
                using="httpx",
            ) as router:
                router.get("/csrf-token", params={"client": mock.ANY}).pass_through()
                router.post("/slas/").mock(
                    return_value=httpx.Response(
                        status_code=201,
                        json={"id": str(uuid4())},
                    )
                )

                client = get_client()
                await deployment._create_slas(uuid4(), client)

                assert len(router.calls) == 2

                first_request = router.calls[0].request
                first_response = router.calls[0].response
                assert (
                    first_request.url.path
                    == f"/api/accounts/{account_id}/workspaces/{workspace_id}/slas/"
                )
                assert json.loads(first_request.content)["name"] == sla1.name
                assert json.loads(first_request.content)["duration"] == sla1.duration
                assert json.loads(first_request.content)["severity"] == sla1.severity
                assert first_response.status_code == 201

                last_request = router.calls.last.request
                last_response = router.calls.last.response
                assert (
                    last_request.url.path
                    == f"/api/accounts/{account_id}/workspaces/{workspace_id}/slas/"
                )
                assert json.loads(last_request.content)["name"] == sla2.name
                assert json.loads(last_request.content)["duration"] == sla2.duration
                assert json.loads(last_request.content)["severity"] == sla2.severity
                assert last_response.status_code == 201

    async def test_create_deployment_against_oss_server_produces_error_log(
        self, prefect_client
    ):
        sla = TimeToCompletionSla(
            name="test-sla",
            duration=timedelta(minutes=10).total_seconds(),
        )
        deployment = RunnerDeployment.from_flow(
            flow=tired_flow,
            name=__file__,
            sla=sla,
        )

        with pytest.raises(
            ValueError,
            match="SLA configuration is currently only supported on Prefect Cloud.",
        ):
            await deployment._create_slas(uuid4(), prefect_client)

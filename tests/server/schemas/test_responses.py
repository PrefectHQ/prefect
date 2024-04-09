from datetime import timedelta
from uuid import uuid4

import pytest

from prefect.server.schemas.responses import DeploymentResponse
from prefect.server.schemas.schedules import IntervalSchedule


class TestDeploymentResponseDeprecatedFields:
    @pytest.fixture
    def deployment_kwargs(self):
        schedule = IntervalSchedule(interval=timedelta(days=1))
        return dict(
            flow_id=uuid4(),
            name="test-deployment",
            version="git-commit-hash",
            manifest_path="path/file.json",
            schedule=schedule,
            parameters={"foo": "bar"},
            tags=["foo", "bar"],
            infrastructure_document_id=uuid4(),
            storage_document_id=uuid4(),
            parameter_openapi_schema={},
        )

    @pytest.mark.parametrize(
        "job_variable_kwarg",
        [
            {"infra_overrides": {"foo": "bar"}},
            {"job_variables": {"foo": "bar"}},
        ],
    )
    def test_exposes_infra_overrides_as_job_variables(
        self, deployment_kwargs, job_variable_kwarg
    ):
        deployment_response = DeploymentResponse(
            **deployment_kwargs, **job_variable_kwarg
        )
        assert deployment_response.infra_overrides == {"foo": "bar"}
        assert deployment_response.job_variables == {"foo": "bar"}

        json = deployment_response.dict()
        assert json["job_variables"] == {"foo": "bar"}
        assert json["infra_overrides"] == {"foo": "bar"}

    def test_infra_overrides_sets_job_variables(self, deployment_kwargs):
        deployment_response = DeploymentResponse(
            **deployment_kwargs,
            job_variables={"foo": "bar"},
        )
        assert deployment_response.job_variables == {"foo": "bar"}

        deployment_response.infra_overrides = {"set_by": "infra_overrides"}
        assert deployment_response.job_variables == {"set_by": "infra_overrides"}

        json_dict = deployment_response.dict()
        assert json_dict["job_variables"] == {"set_by": "infra_overrides"}
        assert json_dict["infra_overrides"] == {"set_by": "infra_overrides"}

    def test_job_variables_sets_infra_overrides(self, deployment_kwargs):
        deployment_response = DeploymentResponse(
            **deployment_kwargs,
            job_variables={"foo": "bar"},
        )
        assert deployment_response.job_variables == {"foo": "bar"}

        deployment_response.job_variables = {"set_by": "job_variables"}
        assert deployment_response.infra_overrides == {"set_by": "job_variables"}

        json_dict = deployment_response.dict()
        assert json_dict["job_variables"] == {"set_by": "job_variables"}
        assert json_dict["infra_overrides"] == {"set_by": "job_variables"}

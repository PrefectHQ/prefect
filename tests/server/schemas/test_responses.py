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
        assert deployment_response.job_variables == {"foo": "bar"}
        assert deployment_response.infra_overrides == {"foo": "bar"}

        json = deployment_response.model_dump()
        assert json["infra_overrides"] == {"foo": "bar"}
        assert "job_variables" not in json

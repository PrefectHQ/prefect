from prefect.client.schemas.objects import DeploymentStatus
from prefect.client.schemas.responses import DeploymentResponse


def test_deployment_response_accepts_disabled_status():
    """DeploymentResponse accepts DISABLED status for Cloud compatibility."""
    response = DeploymentResponse.model_validate(
        {
            "id": "00000000-0000-0000-0000-000000000000",
            "name": "test",
            "flow_id": "00000000-0000-0000-0000-000000000001",
            "status": "DISABLED",
        }
    )
    assert response.status == DeploymentStatus.DISABLED

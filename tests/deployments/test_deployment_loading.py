from pathlib import Path

import pydantic

from prefect.context import PrefectObjectRegistry, registry_from_script
from prefect.deployments import Deployment

EXAMPLES = Path(__file__).parent / "examples"


def test_deployment_added_to_registry_when_loading_from_script():
    root = PrefectObjectRegistry.get().get_instances(Deployment)

    registry = registry_from_script(EXAMPLES / "single_deployment_with_flow.py")

    assert (
        PrefectObjectRegistry.get().get_instances(Deployment) == root
    ), "Root registry should not be changed"

    # Import the deployment to check equality
    from .examples.single_deployment_with_flow import deployment

    deployments = registry.get_instances(Deployment)
    assert len(deployments) == 1

    # The flow will be a different object
    assert deployments[0].dict(exclude={"flow"}) == deployment.dict(exclude={"flow"})
    assert deployments[0].flow.name == deployment.flow.name


def test_deployment_added_to_registry_on_failure_when_loading_from_script():
    registry = registry_from_script(EXAMPLES / "invalid_deployment.py")

    assert registry.get_instances(Deployment) == []
    failures = registry.get_instance_failures(Deployment)
    assert len(failures) == 1
    assert isinstance(failures[0][0], pydantic.ValidationError)
    assert isinstance(failures[0][1], Deployment)
    assert failures[0][2] == tuple()
    assert failures[0][3] == dict(flow="hello!")

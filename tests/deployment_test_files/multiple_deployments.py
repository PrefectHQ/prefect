import pathlib
from prefect.deployments import DeploymentSpec

DeploymentSpec(
    flow_location=pathlib.Path(__file__).parent / "multiple_flows.py",
    flow_name="hello-sun",
    name="hello-sun-deployment",
)


DeploymentSpec(
    flow_location=pathlib.Path(__file__).parent / "multiple_flows.py",
    flow_name="hello-moon",
    name="hello-moon-deployment",
)

from prefect import flow
from prefect.deployments import DeploymentSpec


@flow
def hello_world(name="world"):
    print(f"Hello {name}!")


DeploymentSpec(flow=hello_world, name="inline-deployment", parameters={"foo": "bar"}, tags=["foo", "bar"])

from prefect import flow
from prefect.deployments import DeploymentSpec


@flow
def hello_world(name):
    print(f"Hello {name}!")


DeploymentSpec(
    flow=hello_world,
    name="inline-deployment",
    parameters={"name": "Marvin"},
    tags=["foo", "bar"],
)

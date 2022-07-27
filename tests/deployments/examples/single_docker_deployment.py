from prefect import Deployment, flow
from prefect.infrastructure import DockerContainer


@flow
def foo():
    pass


Deployment(
    name="hello-world-daily",
    flow=foo,
    infrastructure=DockerContainer(
        env={"PREFECT_API_URL": "http://localhost:4200", "HELLO": "world"}
    ),
)

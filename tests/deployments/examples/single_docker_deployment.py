from prefect import Deployment, flow
from prefect.flow_runners import DockerFlowRunner


@flow
def foo():
    pass


Deployment(
    name="hello-world-daily",
    flow=foo,
    flow_runner=DockerFlowRunner(
        env={"PREFECT_API_URL": "http://localhost:4200", "HELLO": "world"}
    ),
)

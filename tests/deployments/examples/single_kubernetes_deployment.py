from prefect import Deployment, flow
from prefect.flow_runners import KubernetesFlowRunner


@flow
def foo():
    pass


Deployment(
    name="hello-world-daily",
    flow=foo,
    flow_runner=KubernetesFlowRunner(),
)

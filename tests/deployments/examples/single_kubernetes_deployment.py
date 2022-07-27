from prefect import Deployment, flow
from prefect.infrastructure import KubernetesJob


@flow
def foo():
    pass


Deployment(
    name="hello-world-daily",
    flow=foo,
    infrastructure=KubernetesJob(),
)

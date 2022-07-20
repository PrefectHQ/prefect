from prefect import Deployment, flow
from prefect.infrastructure import KubernetesJob


@flow
def foo():
    pass


deployment = Deployment(flow=foo, infrastructure=KubernetesJob())

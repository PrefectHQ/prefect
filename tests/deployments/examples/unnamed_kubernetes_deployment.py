from prefect import Deployment, flow
from prefect.flow_runners import KubernetesFlowRunner


@flow
def foo():
    pass


deployment = Deployment(flow=foo, flow_runner=KubernetesFlowRunner())

from prefect import Deployment, flow
from prefect.flow_runners import KubernetesFlowRunner, SubprocessFlowRunner


@flow
def foo():
    pass


Deployment(name="hello-world-daily", flow=foo, flow_runner=KubernetesFlowRunner())
Deployment(name="hello-world-weekly", flow=foo, flow_runner=KubernetesFlowRunner())

Deployment(
    name="custom-boi",
    flow=foo,
    flow_runner=KubernetesFlowRunner(
        customizations=[
            {
                "op": "add",
                "path": "/metadata/labels/custom-label",
                "value": "hi",
            },
            {
                "op": "add",
                "path": "/spec/template/spec/containers/0/env/-",
                "value": {"name": "MY_ENV_VAR", "value": "sweet!"},
            },
        ]
    ),
)

Deployment(
    name="not-a-k8s",
    flow=foo,
    flow_runner=SubprocessFlowRunner(),
)

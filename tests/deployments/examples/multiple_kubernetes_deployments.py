from prefect import Deployment, flow
from prefect.infrastructure import KubernetesJob, Process


@flow
def foo():
    pass


Deployment(name="hello-world-daily", flow=foo, infrastructure=KubernetesJob())
Deployment(name="hello-world-weekly", flow=foo, infrastructure=KubernetesJob())

Deployment(
    name="custom-boi",
    flow=foo,
    infrastructure=KubernetesJob(
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
    infrastructure=Process(),
)

from prefect import Deployment, flow
from prefect.infrastructure import Process


@flow
def foo():
    pass


Deployment(name="hello-world-daily", flow=foo, infrastructure=Process())

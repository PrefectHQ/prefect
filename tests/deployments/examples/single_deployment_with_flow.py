from prefect import Deployment, flow


@flow
def foo():
    pass


deployment = Deployment(flow=foo)

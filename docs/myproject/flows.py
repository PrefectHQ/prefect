from prefect import flow


@flow
def my_flow():
    pass


@flow(name="Nestedflow")
def my_nested_flow(msg):
    pass

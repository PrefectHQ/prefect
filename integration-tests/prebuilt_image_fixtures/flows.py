from prefect import flow


@flow
def hello():
    return "hello"

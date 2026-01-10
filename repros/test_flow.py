from prefect import flow


@flow
def hello_world():
    print("Hello, World!")
    return 42

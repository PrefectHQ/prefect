from prefect import flow
from prefect.context import LoadingContext


@flow
def hello_world(name="world"):
    print(f"Hello {name}!")


assert LoadingContext.get() is not None

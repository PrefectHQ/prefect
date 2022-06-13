from prefect import flow
from prefect.context import get_object_registry


@flow
def hello_world(name="world"):
    print(f"Hello {name}!")


assert get_object_registry().code_execution_blocked

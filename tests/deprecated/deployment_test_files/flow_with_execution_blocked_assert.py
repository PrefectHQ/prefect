from prefect import flow
from prefect.context import PrefectObjectRegistry


@flow
def hello_world(name="world"):
    print(f"Hello {name}!")


assert PrefectObjectRegistry.get().block_code_execution

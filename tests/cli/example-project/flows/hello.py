from typing import Optional

from prefect import flow


@flow(name="An important name")
def my_flow(number: int, message: Optional[str] = None):
    pass

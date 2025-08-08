from typing import Literal, Optional

from prefect import flow


@flow(name="An important name")
def my_flow(number: int, message: Optional[str] = None):
    pass


@flow(name="Second important name")
def my_flow2(number: int, message: Optional[str] = None):
    pass


@flow(name="Third important name")
def my_flow3(var1: Literal["a", "b"], var2: Literal["c"]):
    pass

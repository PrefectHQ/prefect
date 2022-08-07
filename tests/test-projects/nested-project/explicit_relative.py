from prefect import flow

from .shared_libs.bar import bar
from .shared_libs.foo import foo


@flow
def foobar():
    return foo() + bar()

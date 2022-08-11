from shared_libs.bar import bar
from shared_libs.foo import foo

from prefect import flow


@flow
def foobar():
    return foo() + bar()

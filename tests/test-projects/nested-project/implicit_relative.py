from shared_libs.bar import bar
from shared_libs.foo import foo

import prefect


@prefect.flow
def foobar():
    return foo() + bar()

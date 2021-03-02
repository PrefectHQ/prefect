"""
Functions that exist for compatibility with different python versions. These should
only be used internally.
"""

import sys
from unittest.mock import call as _Call


# Provide `nullcontext`

if sys.version_info < (3, 7):

    from contextlib import contextmanager
    from typing import Iterator

    @contextmanager
    def nullcontext() -> Iterator[None]:
        yield


else:

    from contextlib import nullcontext  # noqa: F401


# Provide 3.8+ `call` with `.args` and `.kwargs`


def Call(call: _Call) -> _Call:

    if sys.version_info < (3, 8):
        # Properties were added in 3.8

        call.args = call.call_args[0]
        call.kwargs = call.call_args[1]

    return call

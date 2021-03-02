"""
Functions that exist for compatibility with different python versions. These should
only be used internally.
"""

import sys

# Provide `nullcontext`

if sys.version_info < (3, 7):

    from contextlib import contextmanager
    from typing import Iterator

    @contextmanager
    def nullcontext() -> Iterator[None]:
        yield


else:

    from contextlib import nullcontext  # noqa: F401


# Provide 3.6/3.7 `call` with `.args` and `.kwargs`


def Call(call):
    # Takes a `unittest.mock.call` and adds args/kwargs properties

    if sys.version_info < (3, 8):
        # Properties were added in 3.8
        call.args = call[1]
        call.kwargs = call[2]

    return call

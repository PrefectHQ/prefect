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

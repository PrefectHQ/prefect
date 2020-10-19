"""
Functions that exist for compatability with different python versions. These should
only be used internally.
"""

import sys


# Provide `nullcontext`

if sys.version_info < (3, 7):

    from contextlib import contextmanager

    @contextmanager
    def nullcontext():
        pass


else:

    from contextlib import nullcontext

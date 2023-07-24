try:
    from pydantic.v1.json import *  # noqa
except ImportError:
    from pydantic.json import *  # noqa

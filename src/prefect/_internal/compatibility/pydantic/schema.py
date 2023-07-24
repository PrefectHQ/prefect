try:
    from pydantic.v1.schema import *  # noqa
except ImportError:
    from pydantic.schema import *  # noqa

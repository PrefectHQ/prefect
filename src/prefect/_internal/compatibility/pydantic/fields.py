try:
    from pydantic.v1.fields import *  # noqa
except ImportError:
    from pydantic.fields import *  # noqa

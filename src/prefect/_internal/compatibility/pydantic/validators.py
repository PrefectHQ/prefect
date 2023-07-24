try:
    from pydantic.v1.validators import *  # noqa
except ImportError:
    from pydantic.validators import *  # noqa

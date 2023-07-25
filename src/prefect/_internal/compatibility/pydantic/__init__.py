try:
    from pydantic.v1 import *  # noqa
    from pydantic.v1 import ConfigError  # noqa
except ImportError:
    from pydantic import *  # noqa
    from pydantic import ConfigError  # noqa

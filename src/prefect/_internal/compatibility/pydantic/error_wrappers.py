try:
    from pydantic.v1.error_wrappers import ValidationError  # noqa
except ImportError:
    from pydantic.error_wrappers import ValidationError  # noqa

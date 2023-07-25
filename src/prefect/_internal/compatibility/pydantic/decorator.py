try:
    from pydantic.v1.decorator import ValidatedFunction  # noqa
except ImportError:
    from pydantic.decorator import ValidatedFunction  # noqa
